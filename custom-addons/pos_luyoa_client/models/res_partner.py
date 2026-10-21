# -*- coding: utf-8 -*-
import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.mail import single_email_re
from odoo.tools.sql import escape_psql

_logger = logging.getLogger(__name__)

# Timeout del HTTP a Luyoa. Sin timeout, un hang del servicio colgaría un
# worker entero mientras el cajero espera en el popup.
LUYOA_TIMEOUT = 15

POS_ACCESS_GROUPS = ("point_of_sale.group_pos_user", "base.group_system")

# Identificador de cliente de Luyoa (customerUID): mismo charset que pide el
# API (^ [A-Za-z0-9_-] $) y largo mínimo para no confundir basura escaneada
# con un UID. El UID real de ejemplo mide 21 caracteres.
UID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")

# El QR de la tarjeta de lealtad (Apple/Google Wallet) apunta a la web del
# cliente, p.ej. https://demo.luyoa.com/c/sFpY-5uqfH6gPzIKWgbmR — el UID es
# el segmento tras /c/.
URL_CARDS_RE = re.compile(r"/c/([A-Za-z0-9_-]{10,})(?:[/?#]|$)")


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Dato técnico, sin vista: no se muestra al usuario. Se guarda al asignar
    # o crear desde el POS y desde ahí identifica al cliente directamente.
    luyoa_customer_uid = fields.Char(
        string="Luyoa Customer UID",
        copy=False,
        index=True,
        help=(
            "Identificador del cliente en Luyoa, guardado al asignarlo desde "
            "el POS. Permite reidentificar al cliente al próximo escaneo sin "
            "depender del correo o el teléfono."
        ),
    )

    # Una tarjeta Luyoa = un contacto. Los NULL no chocan entre sí.
    _luyoa_customer_uid_unique = models.Constraint(
        "UNIQUE(luyoa_customer_uid)",
        "Esta tarjeta Luyoa ya está vinculada a otro contacto.",
    )

    # ── Guardias ──────────────────────────────────────────────────────────────

    @api.model
    def _pos_luyoa_guard(self):
        """Los métodos RPC solo para usuarios de POS/administración: cualquiera
        que pueda abrir el POS puede gastar el token del negocio."""
        if not any(self.env.user.has_group(g) for g in POS_ACCESS_GROUPS):
            raise AccessError(_("Esta acción está reservada a usuarios del Punto de Venta."))

    # ── Extracción del customerUID del texto escaneado ────────────────────────

    @api.model
    def _pos_luyoa_extract_uid(self, text):
        """Devuelve el customerUID a partir del texto del QR escaneado, o
        False si no se reconoce.

        El QR de la tarjeta (Apple/Google Wallet) trae la URL
        (https://…/c/<uid>); como último recurso se acepta un UID suelto
        (si el QR lo codifica directamente).
        """
        text = (text or "").strip()
        if not text:
            return False
        if UID_RE.match(text):
            return text
        match = URL_CARDS_RE.search(text)
        if match:
            return match.group(1)
        last = text.rstrip("/").rsplit("/", 1)[-1]
        if UID_RE.match(last):
            return last
        return False

    # ── Configuración del punto de venta ──────────────────────────────────────

    @api.model
    def _pos_luyoa_config(self, config_id):
        """pos.config con sudo: las credenciales solo las lee el responsable
        del POS (groups en el campo) y el cajero no debe verlas, pero el
        servidor sí las necesita para consultar a Luyoa en su nombre."""
        return self.env["pos.config"].sudo().browse(config_id).exists()

    @api.model
    def _pos_luyoa_config_error(self, config):
        """Dict de estado si falta configuración; False si está completa."""
        if not config or not config.luyoa_client_enabled:
            return {"status": "config_error",
                    "detail": _("Luyoa no está habilitado en este punto de venta. "
                                "Avise al administrador.")}
        missing = []
        if not config.luyoa_base_url:
            missing.append(_("URL del API"))
        if not config.luyoa_integration_uid:
            missing.append(_("Integration UID"))
        if not config.luyoa_business_uid:
            missing.append(_("Business UID"))
        if not config.luyoa_api_token:
            missing.append(_("token"))
        if missing:
            _logger.warning("pos_luyoa_client: pos.config %s sin configurar: %s",
                            config.id, ", ".join(missing))
            return {"status": "config_error",
                    "detail": _("Luyoa no está configurado en este punto de venta (falta: %s). "
                                "Avise al administrador.", ", ".join(missing))}
        return False

    # ── GET /customer/:customerUID ────────────────────────────────────────────

    @api.model
    def _pos_luyoa_http_error(self, status_code):
        """(status, mensaje para el cajero) según el código HTTP de Luyoa.

        El mensaje es siempre el nuestro: el ``error`` que manda Luyoa
        ("Unauthorized", "Customer not found"…) va al log, no al cajero.
        """
        if status_code == 401:
            return "unauthorized", _(
                "Luyoa rechazó las credenciales de este punto de venta. "
                "Avise al administrador para que revise la configuración de Luyoa.")
        if status_code == 403:
            return "forbidden", _(
                "La integración con Luyoa no tiene permiso para consultar clientes. "
                "Avise al administrador.")
        if status_code == 404:
            return "customer_not_found", _(
                "Este QR no corresponde a un cliente de Luyoa. Pida al cliente que "
                "abra su tarjeta Luyoa y vuelva a escanear.")
        if status_code == 429:
            return "unexpected_response", _(
                "Luyoa está recibiendo demasiadas consultas. Espere unos segundos y reintente.")
        if status_code >= 500:
            return "unexpected_response", _(
                "El servicio de Luyoa no está disponible en este momento. "
                "Reintente en unos segundos.")
        return "unexpected_response", _(
            "Luyoa respondió con un error inesperado (código %s). Reintente; si "
            "persiste, avise al administrador.", status_code)

    @api.model
    def _pos_luyoa_get_customer(self, config, customer_uid):
        """Consulta el cliente en Luyoa.

        Devuelve ``(data, None)`` con el payload del 200, o
        ``(None, {"status": ..., "detail": ...})`` con el error clasificado.
        El log lleva solo datos técnicos (customerUID, código HTTP, error de
        Luyoa): nunca credenciales ni datos personales del cliente.

        OJO: el parámetro NO se llama ``uid`` — dentro de un ``except``,
        ``_()`` deduce el idioma del frame y una local llamada ``uid`` se
        interpreta como el usuario de la sesión (Odoo 19, translate.py
        ``_get_lang``), lo que revienta al iterar el string como IDs.
        """
        url = "%s/customer/%s" % (config.luyoa_base_url.rstrip("/"), customer_uid)
        headers = {
            "accept": "application/json",
            "X-Integration-UID": config.luyoa_integration_uid,
            "X-Business-UID": config.luyoa_business_uid,
            "Authorization": "Bearer %s" % config.luyoa_api_token,
        }
        try:
            response = requests.get(url, headers=headers, timeout=LUYOA_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as exc:
            _logger.warning("pos_luyoa_client: customer %s → sin respuesta (%s) de %s",
                            customer_uid, exc.__class__.__name__, config.luyoa_base_url)
            return None, {
                "status": "connection_error",
                "detail": _("No hay conexión con Luyoa. Revise el internet de la tienda "
                            "y reintente."),
            }
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            _logger.warning("pos_luyoa_client: customer %s → HTTP %s con respuesta no JSON",
                            customer_uid, response.status_code)
            return None, {
                "status": "unexpected_response",
                "detail": _("Luyoa devolvió una respuesta que no se pudo leer. Reintente."),
            }
        if response.status_code == 200 and payload.get("success"):
            _logger.debug("pos_luyoa_client: customer %s → HTTP 200", customer_uid)
            return payload, None
        status, detail = self._pos_luyoa_http_error(response.status_code)
        _logger.warning("pos_luyoa_client: customer %s → HTTP %s (%s), error de Luyoa: %s",
                        customer_uid, response.status_code, status,
                        str(payload.get("error") or "-")[:200])
        return None, {"status": status, "detail": detail}

    # ── Búsqueda del partner en Odoo ──────────────────────────────────────────

    @api.model
    def _pos_luyoa_find_partner(self, customer, config):
        """Busca el contacto de Odoo del cliente de Luyoa.

        Reglas, en orden (la primera que encuentra algo decide):

        1. ``uid``: el customerUID ya guardado en un contacto. Directo.
        2. ``email``: mismo correo (sin distinguir mayúsculas).
        3. ``name_phone``: mismo nombre completo Y mismo teléfono.

        Solo nombre o solo teléfono NO alcanzan: dos personas pueden
        compartirlos, y asignar a la equivocada liga su tarjeta para siempre.
        Si el contacto encontrado por 2 o 3 ya tiene OTRO customerUID, es
        ``uid_conflict``: no se asigna ni se crea un duplicado.

        Devuelve ``(partners, match_by)``; más de un contacto = ambiguo.
        """
        # active_test off: los contactos archivados deben aparecer para
        # poder avisar "está ARCHIVADO" en vez de fingir que no existe.
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        # `card_uid` (no `uid`): una local llamada `uid` en cualquier frame
        # donde haya un `_()` posterior rompe la deducción de idioma de Odoo.
        card_uid = customer.get("uid") or ""
        email = self._pos_luyoa_clean_email(customer.get("email"))
        phone_digits = self._pos_luyoa_phone_digits(customer.get("phone"))
        full_name = " ".join(
            part for part in ((customer.get("first_name") or "").strip(),
                              (customer.get("last_name") or "").strip()) if part
        )
        # Contactos compartidos o de la compañía del POS: uno de otra
        # compañía no se podría cargar en la orden.
        company_domain = [("company_id", "in", [False, config.company_id.id])]

        if card_uid:
            partners = Partner.search([("luyoa_customer_uid", "=", card_uid)], limit=2)
            if partners:
                return partners, "uid"
        # escape_psql: `_` y `%` del correo/nombre son literales, no comodines.
        if email:
            partners = Partner.search(
                company_domain + [("email", "=ilike", escape_psql(email))], limit=2)
            if partners:
                return self._pos_luyoa_check_conflict(partners, card_uid, "email")
        if full_name and len(phone_digits) >= 7:
            # ILIKE %dígitos%: cubre "+525512345678" contra "5512345678" de
            # Luyoa. Un teléfono guardado con espacios no calza (ver ROADMAP).
            partners = Partner.search(company_domain + [
                ("name", "=ilike", escape_psql(full_name)),
                ("phone", "ilike", phone_digits),
            ], limit=2)
            if partners:
                return self._pos_luyoa_check_conflict(partners, card_uid, "name_phone")
        return self.env["res.partner"], False

    @api.model
    def _pos_luyoa_check_conflict(self, partners, card_uid, match_by):
        """Un único contacto ya ligado a OTRA tarjeta Luyoa no es este
        cliente (o tiene dos tarjetas): se informa, no se asigna."""
        if len(partners) == 1 and partners.luyoa_customer_uid \
                and partners.luyoa_customer_uid != card_uid:
            return partners, "uid_conflict"
        return partners, match_by

    @api.model
    def _pos_luyoa_phone_digits(self, phone):
        """Solo dígitos del teléfono; cadena vacía si no hay dígitos."""
        return re.sub(r"\D", "", phone or "")

    @api.model
    def _pos_luyoa_clean_email(self, mail):
        """Correo sin espacios si es válido; cadena vacía si no."""
        mail = (mail or "").strip()
        return mail if mail and single_email_re.match(mail) else ""

    # ── Payload para el popup ─────────────────────────────────────────────────

    @api.model
    def _pos_luyoa_customer_payload(self, customer):
        """Resumen del cliente de Luyoa que ve el cajero (sin rewards: la
        asignación no depende de ellos)."""
        return {
            "uid": customer.get("uid") or "",
            "first_name": (customer.get("first_name") or "").strip(),
            "last_name": (customer.get("last_name") or "").strip(),
            "email": self._pos_luyoa_clean_email(customer.get("email")),
            "phone": (customer.get("phone") or "").strip(),
            "total_balance": customer.get("total_balance"),
            "current_balance": customer.get("current_balance"),
        }

    # ── Común a las dos fases: configuración + consulta a Luyoa ──────────────

    @api.model
    def _pos_luyoa_resolve(self, text, config_id):
        """Valida la configuración, extrae el customerUID y consulta Luyoa.

        Devuelve ``(config, customer, None)`` o ``(None, None, error)``.
        """
        self._pos_luyoa_guard()
        config = self._pos_luyoa_config(config_id)
        error = self._pos_luyoa_config_error(config)
        if error:
            return None, None, error
        # Local `customer_uid` (no `uid`): ver la nota en _pos_luyoa_get_customer.
        customer_uid = self._pos_luyoa_extract_uid(text)
        if not customer_uid:
            return None, None, {
                "status": "invalid_uid",
                "detail": _("No se reconoció el código escaneado. Escanee el QR de la "
                            "tarjeta Luyoa del cliente."),
            }
        payload, error = self._pos_luyoa_get_customer(config, customer_uid)
        if error:
            return None, None, error
        raw = payload.get("data") or {}
        customer = {
            "uid": customer_uid,
            "first_name": (raw.get("firstName") or "").strip(),
            "last_name": (raw.get("lastName") or "").strip(),
            "email": self._pos_luyoa_clean_email(raw.get("email")),
            "phone": (raw.get("phoneNumber") or "").strip(),
            "total_balance": raw.get("totalBalance"),
            "current_balance": raw.get("currentBalance"),
        }
        if not (customer["first_name"] or customer["last_name"]):
            _logger.warning("pos_luyoa_client: customer %s → HTTP 200 sin nombre", customer_uid)
            return None, None, {
                "status": "unexpected_response",
                "detail": _("Luyoa encontró el cliente pero su ficha no tiene nombre. "
                            "Pida al cliente que complete sus datos en Luyoa."),
            }
        return config, customer, None

    @api.model
    def _pos_luyoa_conflict_error(self, partner):
        return {
            "status": "uid_conflict",
            "detail": _("El contacto %s de Odoo ya está vinculado a otra tarjeta Luyoa. "
                        "No se asignó para no mezclar clientes; revíselo en Contactos.",
                        partner.display_name),
        }

    # ── Fase 1 del popup: consultar y clasificar (no escribe nada) ────────────

    @api.model
    def pos_luyoa_lookup(self, text, config_id):
        config, customer, error = self._pos_luyoa_resolve(text, config_id)
        if error:
            return error
        partners, match_by = self._pos_luyoa_find_partner(customer, config)
        _logger.info("pos_luyoa_client: customer %s → %s contacto(s) en Odoo, regla=%s",
                     customer["uid"], len(partners), match_by or "ninguna")
        result = {
            "status": "",
            "luyoa": self._pos_luyoa_customer_payload(customer),
            "partner": None,
            "candidates": [],
            "match_by": match_by or "",
            "detail": "",
        }
        if len(partners) > 1:
            result["status"] = "ambiguous"
            result["candidates"] = [
                {"id": p.id, "name": p.display_name, "email": p.email or "", "active": p.active}
                for p in partners
            ]
            result["detail"] = _("Hay más de un contacto en Odoo con estos datos. "
                                 "Unifíquelos en Contactos y vuelva a escanear.")
            return result
        if not partners:
            result["status"] = "not_in_odoo"
            return result
        partner = partners[0]
        result["partner"] = {
            "id": partner.id,
            "name": partner.display_name,
            "email": partner.email or "",
            "phone": partner.phone or "",
        }
        if match_by == "uid_conflict":
            result.update(self._pos_luyoa_conflict_error(partner))
            return result
        if not partner.active:
            result["status"] = "archived"
            result["detail"] = _("El cliente existe en Odoo pero está archivado. "
                                 "Pida al administrador que lo reactive en Contactos.")
            return result
        result["status"] = "found"
        return result

    # ── Fase 2 del popup: escribir (crear / asignar) ──────────────────────────

    @api.model
    def pos_luyoa_assign(self, text, config_id, action="assign"):
        """Re-resuelve el cliente contra Luyoa (misma fuente de verdad que la
        fase 1, sin confiar en el payload del popup) y escribe: asignación
        (guarda el UID) o creación con los datos básicos."""
        self._pos_luyoa_guard()
        if action not in ("assign", "create"):
            return {"status": "invalid", "detail": _("Acción no reconocida: %s", action)}
        config, customer, error = self._pos_luyoa_resolve(text, config_id)
        if error:
            return error
        customer_uid = customer["uid"]
        partners, match_by = self._pos_luyoa_find_partner(customer, config)
        if len(partners) > 1:
            return {"status": "ambiguous",
                    "detail": _("Hay más de un contacto en Odoo con estos datos. "
                                "Unifíquelos en Contactos y vuelva a escanear.")}
        if match_by == "uid_conflict":
            return self._pos_luyoa_conflict_error(partners)
        try:
            if partners:
                if not partners.active:
                    return {"status": "archived",
                            "detail": _("El cliente existe en Odoo pero está archivado. "
                                        "Pida al administrador que lo reactive en Contactos.")}
                # Con action == "create" también: el contacto apareció entre
                # la consulta y la confirmación; asignar en vez de duplicar.
                return self._pos_luyoa_assigned(partners, customer_uid)
            if action == "assign":
                return {"status": "not_in_odoo",
                        "detail": _("El contacto ya no está en Odoo. Escanee de nuevo.")}
            vals = {
                "name": re.sub(r"\s+", " ",
                               ("%s %s" % (customer["first_name"], customer["last_name"])).strip()),
                "email": customer["email"] or False,
                "phone": customer["phone"] or False,
                "luyoa_customer_uid": customer_uid,
            }
            # Savepoint: si algo falla (create, mensaje, campos calculados)
            # se revierte todo en vez de dejar el contacto a medias.
            with self.env.cr.savepoint():
                partner = self.create(vals)
                partner.message_post(body=_(
                    "Cliente creado desde el POS con datos de Luyoa — %(cajero)s, %(fecha)s",
                    cajero=self.env.user.name, fecha=fields.Date.context_today(self),
                ))
            _logger.info("pos_luyoa_client: customer %s → contacto %s creado",
                         customer_uid, partner.id)
            return {"status": "created", "partner_id": partner.id, "name": partner.display_name}
        except AccessError:
            _logger.warning("pos_luyoa_client: usuario %s sin permiso para %s (customer %s)",
                            self.env.uid, action, customer_uid)
            return {"status": "permission_error",
                    "detail": _("Su usuario no tiene permiso para crear contactos. "
                                "Pida el permiso al administrador.")}
        except Exception:  # noqa: BLE001 — el POS necesita un dict, no un traceback
            _logger.exception("pos_luyoa_client: fallo al %s customer %s", action, customer_uid)
            return {"status": "unexpected_response",
                    "detail": _("No se pudo guardar el cliente. Reintente; si persiste, "
                                "avise al administrador.")}

    @api.model
    def _pos_luyoa_assigned(self, partner, customer_uid):
        """Resultado de asignación; guarda el UID de Luyoa en el contacto si
        aún no lo tenía, para identificarlo directo en los próximos escaneos."""
        if not partner.luyoa_customer_uid:
            partner.sudo().write({"luyoa_customer_uid": customer_uid})
            _logger.info("pos_luyoa_client: customer %s → vinculado al contacto %s",
                         customer_uid, partner.id)
        return {"status": "assigned", "partner_id": partner.id, "name": partner.display_name}
