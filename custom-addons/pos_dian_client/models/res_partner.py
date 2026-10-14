# -*- coding: utf-8 -*-
import json
import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.mail import single_email_re

_logger = logging.getLogger(__name__)

# Timeout del HTTP a Edipo. Sin timeout, un hang del servicio colgaría un worker
# entero mientras el cajero espera en el popup.
EDIPO_TIMEOUT = 20

# Códigos l10n_co_document_code que son NIT con dígito de verificación colombiano.
# 'vat' (NIF) queda fuera del selector: mapea al mismo tipo DIAN 6 que 'rut'.
NIT_DOC_CODES = ("rut", "vat")
SELECTOR_HIDE_CODES = ("vat",)

POS_ACCESS_GROUPS = ("point_of_sale.group_pos_user", "base.group_system")

# Largo máximo del número consultado: ningún documento colombiano pasa de 15
# dígitos y Edipo responde con un error de validación a los más largos.
MAX_DOC_LENGTH = 15

# Correos de relleno que devuelve la DIAN (vistos en respuestas reales de
# Edipo: sininformacion@…, SINCORREO@GMAIL.COM, sincorreo@sincorreo.com).
PLACEHOLDER_EMAIL_PREFIXES = ("sininformacion", "sincorreo")


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── Guardias ──────────────────────────────────────────────────────────────

    @api.model
    def _pos_dian_guard(self):
        """Los métodos RPC solo para usuarios de POS/administración: cualquiera
        que pueda abrir el POS puede gastar el token de la compañía."""
        if not any(self.env.user.has_group(g) for g in POS_ACCESS_GROUPS):
            raise AccessError(_("Esta acción está reservada a usuarios del Punto de Venta."))

    # ── Catálogo de tipos de documento para el popup ──────────────────────────

    @api.model
    def pos_dian_client_doc_types(self):
        # Público sin guion bajo: Odoo 19 bloquea por RPC los métodos privados
        # ("Private methods cannot be called remotely") y el popup lo llama vía
        # orm.call.
        # No se filtra por country_id=CO: en los datos de l10n_co varios tipos
        # (vat, passport, foreign_id_card, external_id) quedan sin país y el
        # código l10n_co ya es colombiano por definición.
        self._pos_dian_guard()
        types = self.env["l10n_latam.identification.type"].sudo().search(
            [
                ("l10n_co_document_code", "!=", False),
                ("active", "=", True),
            ],
            order="sequence, id",
        )
        return [
            {
                "id": doc_type.id,
                "code": doc_type.l10n_co_document_code,
                "name": doc_type.display_name or doc_type.name,
                "is_nit": doc_type.l10n_co_document_code in NIT_DOC_CODES,
            }
            for doc_type in types
            if doc_type.l10n_co_document_code not in SELECTOR_HIDE_CODES
        ]

    # ── Dígito de verificación DIAN (Orden Administrativa 4 de 1989) ─────────

    @api.model
    def _pos_dian_nit_dv(self, base):
        """DV módulo 11: pesos 3,7,13,17,19,23,29,37,41,... de derecha a
        izquierda; residuo 0 o 1 se queda, resto es 11 − residuo.
        Verificado con 900123456-8 y 901234567-7."""
        digits = [int(ch) for ch in base if ch.isdigit()]
        if not digits:
            return False
        weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        total = sum(digit * weight for digit, weight in zip(reversed(digits), weights))
        residue = total % 11
        if residue < 2:
            return str(residue)
        return str(11 - residue)

    # ── Correo: formato y marcadores de relleno ──────────────────────────────

    @api.model
    def _pos_dian_clean_email(self, mail):
        """Devuelve el correo sin espacios si es válido y no es un marcador
        de relleno; si no, cadena vacía."""
        mail = (mail or "").strip()
        if not mail or not single_email_re.match(mail):
            return ""
        if mail.lower().startswith(PLACEHOLDER_EMAIL_PREFIXES):
            return ""
        return mail

    # ── Resolución del documento (tipo + variantes de almacenamiento) ────────

    @api.model
    def _pos_dian_resolve(self, doc_code, number, dv=False):
        """Normaliza la entrada y prepara variantes de búsqueda.

        Devuelve dict con latam_type, jorels_type_id, query_number, vat_expected
        o ``error`` (dict de estado listo para devolver).
        """
        latam_type = self.env["l10n_latam.identification.type"].sudo().search(
            [("l10n_co_document_code", "=", doc_code)], limit=1
        )
        if not latam_type:
            return {"error": {"status": "invalid", "detail": _("Tipo de documento desconocido: %s", doc_code)}}
        jorels_type = self._get_type_document_identification_id(latam_type)
        if not jorels_type:
            return {"error": {
                "status": "invalid",
                "detail": _("El tipo %s no está mapeado con la DIAN (Jorels).", latam_type.display_name),
            }}
        number = (number or "").strip()
        if not number:
            return {"error": {"status": "invalid", "detail": _("Digite el número de documento.")}}
        is_nit = doc_code in NIT_DOC_CODES
        if is_nit:
            dv = (dv or "").strip()
            if "-" in number:
                # Ojo: nunca usar `_` como descartable aquí: sombrearía la
                # función de traducción `_()` en todo el método.
                base, _sep, dv_in = number.rpartition("-")
                dv = dv or dv_in
            else:
                base = number
            base = "".join(ch for ch in base if ch.isdigit())
            # NIT con DV pegado (regla 2026-10-13): 10 dígitos, empresa (empieza
            # por 8 o 9), sin DV digitado aparte y el último dígito = DV correcto
            # de los 9 previos → se interpreta como base+DV. Una CC de 10 dígitos
            # empieza por 1, así que no colisiona.
            if (not dv and len(base) == 10 and base[0] in ("8", "9")
                    and self._pos_dian_nit_dv(base[:9]) == base[9]):
                base = base[:9]
            if len(base) < 7:
                return {"error": {"status": "invalid", "detail": _("El NIT debe tener al menos 7 dígitos.")}}
            if len(base) > MAX_DOC_LENGTH:
                return {"error": {"status": "invalid", "detail": _("El número de documento es demasiado largo.")}}
            dv_expected = self._pos_dian_nit_dv(base)
            if dv and dv != dv_expected:
                return {"error": {
                    "status": "invalid",
                    "detail": _("El dígito de verificación no concuerda; el correcto es %s.", dv_expected),
                }}
            query_number = base
            variants = [base, "%s%s" % (base, dv_expected)]
            vat_expected = "%s-%s" % (base, dv_expected)
        else:
            query_number = self._edi_sanitize_vat(number, jorels_type.id)
            if not query_number:
                return {"error": {"status": "invalid", "detail": _("Digite el número de documento.")}}
            if len(query_number) > MAX_DOC_LENGTH:
                return {"error": {"status": "invalid", "detail": _("El número de documento es demasiado largo.")}}
            variants = [query_number]
            vat_expected = query_number
        return {
            "latam_type": latam_type,
            "jorels_type_id": jorels_type.id,
            "query_number": query_number,
            "vat_expected": vat_expected,
            "is_nit": is_nit,
            "edi_variants": list({*variants, query_number}),
            "vat_variants": list({*variants, vat_expected, query_number}),
        }

    @api.model
    def _pos_dian_find_candidates(self, resolved):
        """Búsqueda tolerante a cómo esté guardado el documento: NIT con/sin DV,
        con o sin guion, partner sin tipo de identificación asignado y registros
        archivados. Agrupa por empresa comercial para no contar duplicados
        empresa-contacto.

        Devuelve ``(matching, others)``: solo cuentan los que tienen el mismo
        tipo DIAN o no tienen tipo; los que coinciden por número con OTRO tipo
        (p.ej. CC frente a un NIT) se devuelven aparte para avisar sin escribir.
        """
        domain = ["|",
                  ("edi_sanitize_vat", "in", resolved["edi_variants"]),
                  ("vat", "in", resolved["vat_variants"])]
        found = self.with_context(active_test=False).search(domain)
        # El número consultado debe coincidir dígito a dígito (el search por
        # vat "in" ya es exacto; se revalida para el caso de variantes vacías).
        found = found.filtered(lambda p: p.edi_sanitize_vat in resolved["edi_variants"]
                               or (p.vat or "").strip() in resolved["vat_variants"])
        grouped = {}
        for partner in found:
            key = partner.commercial_partner_id.id
            current = grouped.get(key)
            if current is None or (partner.active and not current.active):
                grouped[key] = partner
        all_candidates = list(grouped.values())
        matching = [
            p for p in all_candidates
            if not p.type_document_identification_id
            or p.type_document_identification_id.id == resolved["jorels_type_id"]
        ]
        others = [p for p in all_candidates if p not in matching]
        return matching, others

    @api.model
    def _pos_dian_type_mismatch_detail(self, other):
        tipo = other.type_document_identification_id.display_name or _("otro tipo")
        return _("Existe en Odoo como %s; consúltelo con ese tipo o corríjalo en Contactos.") % tipo

    # ── Lectura de estado del existente para la FE ────────────────────────────

    @api.model
    def _pos_dian_readiness(self, partner, resolved, dian_name=False, dian_email=False):
        """Clasifica un partner existente contra lo que Jorels exige al emitir.

        Returns (missing[list[str]], fillable[dict], diff[dict]) — ``fillable``
        son campos vacíos que se completan con los mismos defaults de creación
        (decisión 2026-10-13: el bloqueo no sirve operativamente en caja, se
        completa y se sigue; los valores no vacíos jamás se pisan). ``missing``
        queda solo para lo que no se puede completar desde acá.
        """
        self._pos_dian_ensure_jorels_listings()
        company = self.env.company
        missing = []
        fillable = {}
        has_email = bool(partner.email_edi or (company.ei_ignore_edi_email_check and partner.email))
        if not has_email:
            if dian_email:
                fillable["email_edi"] = dian_email
            else:
                missing.append(_("el correo electrónico de facturación (complételo en Contactos)"))
        if not partner.l10n_latam_identification_type_id:
            fillable["l10n_latam_identification_type_id"] = resolved["latam_type"].id
        # Único caso permitido de reescritura del vat: NIT guardado sin DV o
        # sin guion (mismos dígitos) → se normaliza a base-DV. El vat no vacío
        # de otros tipos jamás se reescribe (hallazgo 4, 2026-10-13).
        if (partner.vat and partner.vat != resolved["vat_expected"] and resolved["is_nit"]
                and "".join(ch for ch in partner.vat if ch.isdigit()) in resolved["edi_variants"]):
            fillable["vat"] = resolved["vat_expected"]
        # Municipio: Jorels acepta municipality_id o el postal (desde zip).
        is_co = (partner.country_id or company.country_id).code == "CO"
        if is_co and not (partner.municipality_id or partner.postal_municipality_id):
            if company.municipality_id:
                fillable["municipality_id"] = company.municipality_id.id
            else:
                missing.append(_(
                    "el municipio: configure Municipio de la compañía "
                    "(Ajustes › Empresas › Actualizar Informacion › Facturación electrónica )"))
        if not partner.type_regime_id:
            fillable["type_regime_id"] = 2
        if not partner.type_liability_id:
            fillable["type_liability_id"] = 29
        diff = {
            "name": bool(dian_name and partner.name and partner.name.strip().casefold() != dian_name.strip().casefold()),
            "email": bool(dian_email and partner.email and partner.email.strip().casefold() != dian_email.strip().casefold()),
        }
        return missing, fillable, diff

    # ── Consulta del adquirente a la DIAN vía Edipo (Jorels) ─────────────────

    @api.model
    def _pos_dian_edipo_acquirer(self, jorels_type_id, query_number):
        """POST a `edipo.jorels.com/acquirer`.

        Devuelve ``(data, None)`` con el JSON del adquirente si la DIAN lo
        confirma, o ``(None, {"status": ..., "detail": ...})`` con el error
        clasificado. Reimplementado a propósito de ``fetch_dian_acquirer_data``
        del vendor porque ese método no trae timeout y corre con `response` sin
        proteger. Las sondas con el token local (2026-10-13) devolvieron
        `{"message": "Unauthenticated."}` **con HTTP 200**: por eso la
        clasificación es por cuerpo, no por status_code, hasta ver el payload
        real de "no encontrado" y "encontrado" con un token válido.
        """
        company = self.env.company
        api_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("jorels.edipo.api_url", "https://edipo.jorels.com")
        )
        url = "%s/acquirer/%s/%s" % (api_url.rstrip("/"), jorels_type_id, query_number)
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        params = {"token": company.api_key}
        response = None
        try:
            response = requests.post(url, json.dumps({}), headers=headers, params=params, timeout=EDIPO_TIMEOUT)
            data = response.json()
        except (requests.Timeout, requests.ConnectionError) as exc:
            # Solo la clase del error: el texto de las excepciones de `requests`
            # puede traer la URL con `?token=…` y eso no debe llegar al log.
            _logger.info("pos_dian_client: fallo de red %s consultando %s",
                         exc.__class__.__name__, url)
            return None, {
                "status": "connection_error",
                "detail": _("La DIAN no respondió (%s). Reintente en unos segundos.", exc.__class__.__name__),
            }
        except ValueError:
            code = response.status_code if response is not None else "?"
            _logger.info("pos_dian_client: respuesta no JSON de Edipo (HTTP %s) para %s", code, url)
            return None, {
                "status": "connection_error",
                "detail": _("El servicio de facturación devolvió una respuesta inválida (HTTP %s). Reintente.", code),
            }

        if not isinstance(data, dict):
            return None, {
                "status": "unexpected_response",
                "detail": _("Respuesta inesperada del servicio de facturación."),
            }
        message = data.get("message")
        name = data.get("name")
        email = data.get("email")
        if message in ("Unauthenticated.", "") and not (name or email):
            return None, {
                "status": "config_error",
                "detail": _("El token de Edipo no es válido o no está autorizado. "
                            "Revise el valor guardado en Ajustes › Facturación electrónica."),
            }
        if name or email:
            # Confirmado por la DIAN (payload con datos del adquirente).
            return data, None
        if data.get("errors"):
            # Error de validación de Edipo (p.ej. número con caracteres o
            # largo inválido): llega con `message` + `errors` y no es un
            # "no registrado".
            _logger.info("pos_dian_client: Edipo rechazó la consulta: %s", data.get("errors"))
            return None, {
                "status": "unexpected_response",
                "detail": _("El servicio no aceptó la consulta. Revise el tipo y el número digitados."),
            }
        if message:
            # Formato real de "no registrado" (2026-10-13): message con name y
            # email nulos. Edipo no usa `detail` para esto.
            _logger.info("pos_dian_client: adquirente %s/%s no confirmado", jorels_type_id, query_number)
            return None, {"status": "not_registered", "detail": message}
        if "detail" in data:
            # Un `detail` SIEMPRE es error del servicio/forma, jamás
            # "no registrado" (evita cerrar clientes válidos).
            _logger.info("pos_dian_client: detail de Edipo no clasificado: %s", data["detail"])
            if isinstance(data["detail"], list):
                # 422 de validación: el detalle crudo no le sirve al cajero.
                return None, {
                    "status": "unexpected_response",
                    "detail": _("El servicio no aceptó la consulta. Revise el tipo y el número digitados."),
                }
            return None, {
                "status": "unexpected_response",
                "detail": _("El servicio devolvió un error (%s). Reintente.", data["detail"]),
            }
        return None, {
            "status": "unexpected_response",
            "detail": _("Respuesta inesperada del servicio de facturación."),
        }

    # ── Fase 1 del popup: consultar y clasificar (no escribe nada) ────────────

    @api.model
    def pos_dian_lookup(self, doc_code, number, dv=False):
        self._pos_dian_guard()
        company = self.env.company
        if not company.ei_enable:
            return {"status": "config_error",
                    "detail": _("La facturación electrónica no está habilitada para esta compañía.")}
        if not company.api_key:
            return {"status": "config_error",
                    "detail": _("No está configurado el token de Edipo (api_key) de la compañía.")}

        resolved = self._pos_dian_resolve(doc_code, number, dv)
        if resolved.get("error"):
            return resolved["error"]
        if resolved["query_number"] == "222222222222":
            return {"status": "invalid",
                    "detail": _("Ese es el documento genérico de consumidor final. Use el botón Cliente.")}

        data, error = self._pos_dian_edipo_acquirer(resolved["jorels_type_id"], resolved["query_number"])
        if error:
            return error

        dian_name = (data.get("name") or "").strip()
        dian_email = self._pos_dian_clean_email(data.get("email"))
        result = {
            "status": "found",
            "dian": {"name": dian_name, "email": dian_email},
            "vat_expected": resolved["vat_expected"],
            "partner": None,
            "missing": [],
            "fillable": {},
            "diff": {"name": False, "email": False},
            "candidates": [],
            "detail": "",
        }

        try:
            candidates, others = self._pos_dian_find_candidates(resolved)
        except AccessError as access_exc:
            _logger.info("pos_dian_client: sin permiso de lectura sobre contactos: %s", access_exc)
            return {"status": "permission_error",
                    "detail": _("Su usuario no puede leer contactos. Solicite los permisos "
                                "necesarios al administrador.")}
        if others and not candidates:
            # El número existe en Odoo pero con otro tipo de documento (p.ej.
            # CC frente a NIT): no se escribe nada, solo se avisa.
            result["status"] = "type_mismatch"
            result["partner"] = {
                "id": others[0].id,
                "name": others[0].display_name,
                "vat": others[0].vat or "",
            }
            result["detail"] = self._pos_dian_type_mismatch_detail(others[0])
            return result
        if len(candidates) > 1:
            result["status"] = "ambiguous"
            result["candidates"] = [
                {"id": p.id, "name": p.display_name, "vat": p.vat or "", "active": p.active}
                for p in candidates
            ]
            result["detail"] = _("Hay más de un contacto con este documento. "
                                 "Asígnelo o corríjalo primero en Contactos.")
            return result

        if not candidates:
            if not dian_name:
                result["status"] = "unexpected_response"
                result["detail"] = _("La DIAN confirmó el documento pero no devolvió nombre; "
                                     "no se puede crear el cliente.")
                return result
            result["status"] = "needs_email" if not dian_email else "create_ok"
            return result

        partner = candidates[0]
        result["partner"] = {
            "id": partner.id,
            "name": partner.display_name,
            "vat": partner.vat or "",
            "email": partner.email or "",
            "email_edi": partner.email_edi or "",
        }
        if not partner.active:
            result["status"] = "archived"
            result["detail"] = _("El cliente existe en Odoo pero está ARCHIVADO. "
                                 "Reactívelo en Contactos antes de facturarle.")
            return result
        missing, fillable, diff = self._pos_dian_readiness(partner, resolved, dian_name, dian_email)
        result["missing"] = missing
        result["fillable"] = fillable
        result["diff"] = diff
        if missing:
            result["status"] = "incomplete"
            result["detail"] = _("El cliente existe en Odoo pero le falta: %s.") % "; ".join(missing)
        return result

    # ── Fase 2 del popup: escribir (crear / actualizar / asignar) ─────────────

    @api.model
    def pos_dian_confirm(self, doc_code, number, dv=False, action="assign",
                         dian_name=False, dian_email=False, email=False, replace=False):
        """Escribe con la misma resolución de la fase 1, pero **sin** volver a
        llamar a la DIAN: los valores de la DIAN viajan desde el popup y se
        revalidan aquí (formatos, largos, dominio de escritura)."""
        self._pos_dian_guard()
        resolved = self._pos_dian_resolve(doc_code, number, dv)
        if resolved.get("error"):
            return resolved["error"]
        # El correo de la DIAN ya llega filtrado de la fase 1; se revalida por
        # si el popup mandara otro. El digitado por el cajero debe ser válido.
        dian_email = self._pos_dian_clean_email(dian_email)
        email = (email or "").strip()
        if email and not single_email_re.match(email):
            return {"status": "invalid", "detail": _("El correo %s no tiene un formato válido.", email)}

        try:
            candidates, others = self._pos_dian_find_candidates(resolved)
            if others and not candidates:
                return {"status": "type_mismatch",
                        "detail": self._pos_dian_type_mismatch_detail(others[0])}
            active_candidates = [p for p in candidates if p.active]

            if action == "create":
                if active_candidates:
                    partner = active_candidates[0]
                    missing, _fillable, _diff = self._pos_dian_readiness(
                        partner, resolved, dian_name, dian_email)
                    if missing:
                        return {"status": "incomplete", "detail": _("El cliente existe en Odoo pero le falta: %s.")
                                % "; ".join(missing)}
                    return {"status": "assigned", "partner_id": partner.id, "name": partner.display_name}
                name = (dian_name or "").strip()
                if not name:
                    return {"status": "invalid", "detail": _("Sin nombre no se puede crear el cliente.")}
                mail = dian_email or email
                if not mail:
                    return {"status": "needs_email", "detail": _("Escriba el correo del cliente para continuar.")}
                # Savepoint: si algo falla (create, mensaje, campos calculados)
                # se revierte todo en vez de dejar el contacto a medias.
                with self.env.cr.savepoint():
                    partner = self.create(self._pos_dian_create_vals(resolved, name, mail))
                    partner.message_post(body=_(
                        "Cliente creado desde el POS tras validación DIAN — %(cajero)s, %(fecha)s",
                        cajero=self.env.user.name, fecha=fields.Date.context_today(self),
                    ))
                _logger.info("pos_dian_client: cliente %s (%s) creado con datos de la DIAN",
                             partner.id, partner.vat)
                return {"status": "created", "partner_id": partner.id, "name": partner.display_name}

            if action in ("assign", "update"):
                if len(active_candidates) != 1:
                    return {"status": "ambiguous",
                            "detail": _("El documento no resuelve un único cliente activo; "
                                        "revíselo en Contactos.")}
                partner = active_candidates[0]
                if action == "assign":
                    missing, _f, _d = self._pos_dian_readiness(partner, resolved, dian_name, dian_email)
                    if missing:
                        return {"status": "incomplete",
                                "detail": _("El cliente existe en Odoo pero le falta: %s.") % "; ".join(missing)}
                    return {"status": "assigned", "partner_id": partner.id, "name": partner.display_name}
                # update: solo campos vacíos, y nombre/correo SOLO con replace
                _missing, fillable, _diff = self._pos_dian_readiness(partner, resolved, dian_name, dian_email)
                vals = {}
                for fname, fvalue in fillable.items():
                    vals[fname] = fvalue
                if replace:
                    if dian_name:
                        # El nombre de la DIAN se guarda tal cual (solo se
                        # colapsan espacios dobles): reordenarlo sería adivinar.
                        vals["name"] = re.sub(r"\s+", " ", dian_name).strip()
                    if dian_email or email:
                        vals["email"] = dian_email or email
                        vals.setdefault("email_edi", dian_email or email)
                if vals:
                    with self.env.cr.savepoint():
                        partner.write(vals)
                return {"status": "updated", "partner_id": partner.id, "name": partner.display_name}
        except AccessError as access_exc:
            _logger.info("pos_dian_client: sin permisos para %s: %s", action, access_exc)
            return {"status": "permission_error",
                    "detail": _("Su usuario no puede crear o editar contactos. Solicite el permiso "
                                "de creación de contactos al administrador.")}
        except Exception as exc:  # noqa: BLE001 — el POS necesita un dict, no un traceback
            _logger.exception("pos_dian_client: fallo al confirmar %s", action)
            return {"status": "unexpected_response",
                    "detail": _("No se pudo registrar el cliente: %s") % exc}
        return {"status": "invalid", "detail": _("Acción no reconocida: %s", action)}

    # ── Valores de creación (defaults fiscales como usa Jorels) ───────────────

    @api.model
    def _pos_dian_ensure_jorels_listings(self):
        for model_name in ("type_regimes", "type_liabilities"):
            model = self.env["l10n_co_edi_jorels.%s" % model_name]
            if not model.search_count([]):
                self.env["res.company"].init_csv_data(
                    "l10n_co_edi_jorels.l10n_co_edi_jorels.%s" % model_name
                )

    @api.model
    def _pos_dian_create_vals(self, resolved, name, mail):
        self._pos_dian_ensure_jorels_listings()
        company = self.env.company
        country = self.env.ref("base.co", raise_if_not_found=False)
        vals = {
            # El nombre llega de la DIAN en cualquier orden: se guarda tal cual
            # (solo colapsando espacios dobles); reordenarlo sería adivinar y el
            # cajero lo confirma con el cliente en el popup.
            "name": re.sub(r"\s+", " ", name).strip(),
            "vat": resolved["vat_expected"],
            "l10n_latam_identification_type_id": resolved["latam_type"].id,
            "country_id": country.id if country else False,
            "is_company": bool(resolved["is_nit"]),
            # Defaults de creación (verificados contra el CSV del vendor):
            # type_regime_id 2 = "No responsable de IVA",
            # type_liability_id 29 = "No aplica – Otros", municipio de la compañía.
            "type_regime_id": 2,
            "type_liability_id": 29,
            "municipality_id": company.municipality_id.id,
            "email": mail,
            "email_edi": mail,
        }
        return vals
