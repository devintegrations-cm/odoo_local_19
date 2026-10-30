# -*- coding: utf-8 -*-
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import dian_catalog, dian_xml_parser

_logger = logging.getLogger(__name__)

# Eventos RADIAN de receptor (factura de proveedor recibida): acuse de recibo,
# recibo del bien y aceptacion expresa (DECISIONS.md #72). El reclamo (031) y la
# aceptacion tacita (034) los genera contabilidad a mano, segun el caso.
SPRADIAN_SUPPLIER_EVENT_CODES = ("030", "032", "033")


class AccountMove(models.Model):
    _inherit = "account.move"

    # OJO: no confundir con ei_uuid de l10n_co_edi_jorels, que guarda el CUFE de
    # las facturas que NOSOTROS emitimos. Este campo es el CUFE del documento que
    # el proveedor recibio de la DIAN.
    cufe = fields.Char(
        string="CUFE del proveedor",
        size=96,
        index=True,
        copy=False,
        help="Codigo Unico de Factura Electronica del documento emitido por el proveedor.",
    )
    # Solo para los grupos del portal (DECISIONS.md #63): un "leer todos los
    # campos" de otro modulo no debe calcular este one2many.
    spr_request_ids = fields.One2many(
        "supplier.payment.request", "move_id", string="Solicitudes de pago",
        groups="supplier_invoice_portal.group_spr_validator",
    )
    # Enlace del formulario de la factura para verificar el CUFE en el catalogo
    # de la DIAN (DECISIONS.md #55). Misma URL que la consulta automatica.
    spr_cufe_dian_url = fields.Char(
        string="Consultar en la DIAN", compute="_compute_spr_cufe_dian_url"
    )
    # Visibilidad del boton "Generar eventos RADIAN" (DECISIONS.md #72). No
    # almacenado: depende de los eventos de Jorels, que no pueden ir en
    # depends sin depender del modulo.
    spr_radian_can_generate = fields.Boolean(
        string="Puede generar eventos RADIAN",
        compute="_compute_spr_radian_can_generate",
    )

    @api.depends("cufe")
    def _compute_spr_cufe_dian_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("spr.dian_catalog_url")
        for move in self:
            move.spr_cufe_dian_url = (
                dian_catalog.catalog_search_url(base_url, move.cufe) if move.cufe else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("cufe"):
                vals["cufe"] = dian_xml_parser.normalize_cufe(vals["cufe"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("cufe"):
            vals = dict(vals, cufe=dian_xml_parser.normalize_cufe(vals["cufe"]))
        return super().write(vals)

    @api.constrains("cufe", "company_id", "state", "move_type")
    def _check_cufe_unique(self):
        """El CUFE identifica un documento DIAN: no puede repetirse en compras.

        Se acota a facturas de proveedor no canceladas para no chocar con
        modulos de facturacion electronica de salida.
        """
        for move in self:
            if not move.cufe or move.move_type not in ("in_invoice", "in_refund"):
                continue
            if move.state == "cancel":
                continue
            duplicate = self.search(
                [
                    ("id", "!=", move.id),
                    ("cufe", "=", move.cufe),
                    ("company_id", "=", move.company_id.id),
                    ("move_type", "in", ("in_invoice", "in_refund")),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("El CUFE %s ya esta registrado en la factura %s.")
                    % (move.cufe, duplicate.name or duplicate.id)
                )

    @api.constrains("cufe")
    def _check_cufe_format(self):
        for move in self:
            if move.cufe and not dian_xml_parser.is_valid_cufe(move.cufe):
                raise ValidationError(
                    _("El CUFE debe tener exactamente 96 caracteres hexadecimales.")
                )

    def unlink(self):
        """Si se borra la factura borrador, la solicitud vuelve a quedar lista
        para generar otra."""
        requests = self.env["supplier.payment.request"].sudo().search(
            [("move_id", "in", self.ids)]
        )
        result = super().unlink()
        if requests:
            requests.write({"move_id": False, "state": "approved"})
            for request in requests:
                request.message_post(body=_(
                    "La factura borrador fue eliminada; la solicitud vuelve a 'Aprobada'."
                ))
        return result

    def _spr_radian_model(self):
        """Modelo de eventos RADIAN de Jorels, o None si el modulo no esta.

        Se resuelve en runtime porque el modulo no depende de
        l10n_co_edi_jorels: sin el, el boton no sale y la accion lo explica.
        """
        return self.env.get("l10n_co_edi_jorels.radian")

    def _spr_is_supplier_bill_journal(self):
        """True si el diario de la factura esta habilitado para RADIAN de
        receptor (DECISIONS.md #72).

        El documento soporte se excluye aunque el diario este marcado: la
        resolucion se le puede poner despues de marcarlo.
        """
        self.ensure_one()
        journal = self.journal_id
        return bool(
            journal
            and journal.type == "purchase"
            and journal.spr_radian_enabled
            and not journal._spr_is_support_document_journal()
        )

    def _spr_radian_blocking_reason(self):
        """Motivo por el que la factura no puede generar sus eventos RADIAN
        de receptor, o False si puede (DECISIONS.md #72). Lo usan el compute del
        boton y la accion, que vuelve a validar en el servidor."""
        self.ensure_one()
        Radian = self._spr_radian_model()
        if Radian is None:
            return _("Los eventos RADIAN requieren el modulo de facturacion "
                     "electronica (l10n_co_edi_jorels), que no esta instalado.")
        if self.move_type != "in_invoice":
            # Los eventos 030-033 son de la factura: la nota credito del
            # proveedor no los lleva.
            return _("Los eventos RADIAN de receptor (030, 032, 033) son de las "
                     "facturas de proveedor; este documento no lo es.")
        if self.state != "posted":
            return _("La factura debe estar publicada para generar los eventos RADIAN.")
        if not self._spr_is_supplier_bill_journal():
            return _("El diario %s no esta habilitado para eventos RADIAN de receptor. "
                     "Se habilita marcando 'Eventos RADIAN de receptor' en la "
                     "configuracion del diario (no aplica a diarios de documento "
                     "soporte).") % self.journal_id.display_name
        if not self.invoice_date:
            return _("La factura no tiene fecha de factura.")
        if not self.cufe:
            # ei_uuid no sirve de condicion: en documento soporte Jorels guarda
            # ahi el CUDS que emitimos nosotros, no el CUFE del proveedor.
            return _("La factura no tiene el CUFE del proveedor: sin el, la DIAN "
                     "no acepta los eventos RADIAN.")
        if Radian.sudo().search_count([("move_id", "=", self.id)]):
            return _("La factura ya tiene eventos RADIAN; los que falten se "
                     "gestionan desde los eventos de facturacion electronica.")
        return False

    @api.depends("state", "move_type", "journal_id", "journal_id.spr_radian_enabled",
                 "cufe", "invoice_date")
    def _compute_spr_radian_can_generate(self):
        for move in self:
            # Las facturas nuevas (onchange) no tienen id ni estan publicadas.
            move.spr_radian_can_generate = bool(
                move._origin.id and not move._origin._spr_radian_blocking_reason()
            )

    def _spr_radian_missing_requirements(self):
        """Lista de datos que Jorels exige para enviar un evento y que hoy
        fallan tarde, con el evento ya numerado (``radian.py``:
        ``get_json_request`` y ``validate_dian_generic``).

        Los campos se leen por ``_fields``: si una version de Jorels no trae
        alguno, cuenta como faltante en vez de romper.
        """
        self.ensure_one()
        company = self.company_id
        user = self.env.user

        def value(record, field_name):
            return record[field_name] if field_name in record._fields else False

        missing = []
        if not value(company, "ei_enable"):
            missing.append(_("Facturacion electronica activa en la compania %s")
                           % company.name)
        if not value(company, "api_key"):
            missing.append(_("Token de Edipo (api_key) de la compania %s") % company.name)
        if not value(company, "is_not_test") and not value(company, "test_set_id"):
            missing.append(_("TestSetId de la compania %s (ambiente de pruebas)")
                           % company.name)
        for field_name, label in (
            ("type_document_identification_id", _("tipo de documento")),
            ("vat", _("numero de documento (NIF)")),
            ("first_name", _("nombre")),
            ("surname", _("apellido")),
            ("function", _("cargo")),
        ):
            if not value(user, field_name):
                missing.append(_("%(label)s del usuario firmante %(user)s")
                               % {"label": label, "user": user.name})
        # Jorels deja a los usuarios nuevos con el NIT generico de consumidor
        # final: pasa como "con documento", pero el evento saldria firmado con
        # una identificacion ficticia.
        vat_digits = "".join(char for char in (value(user, "vat") or "") if char.isdigit())
        if vat_digits and set(vat_digits) == {"2"}:
            missing.append(_("numero de documento real del usuario firmante %s (tiene el "
                             "generico de consumidor final %s)") % (user.name, vat_digits))
        return missing

    @api.model
    def _spr_is_edipo_unreachable(self, exc):
        """True si el fallo es que Edipo no respondio (caido, sin red, timeout).

        Jorels atrapa el error de conexion de ``requests.post`` y sigue con
        ``response`` sin asignar (``radian.py``, ``validate_dian_generic``): lo
        que llega es un UserError en ingles ("cannot access local variable
        'response'...") que envuelve un UnboundLocalError. Se mira la cadena de
        excepciones y no el texto, que cambia con el idioma.
        """
        seen = set()
        while exc is not None and id(exc) not in seen:
            seen.add(id(exc))
            if isinstance(exc, (requests.RequestException, UnboundLocalError)):
                return True
            exc = exc.__cause__ or exc.__context__
        return False

    def _spr_send_radian_event(self, code):
        """Crea, publica y valida un evento RADIAN de receptor; devuelve su
        nombre. Lanza excepcion si la DIAN no lo acepta: quien llama lo
        envuelve en un savepoint para revertir solo este evento."""
        self.ensure_one()
        company = self.company_id
        event = self.env["l10n_co_edi_jorels.events"].sudo().search(
            [("code", "=", code)], limit=1)
        if not event:
            raise UserError(_("El evento RADIAN %s no esta en el catalogo de Jorels.") % code)
        # sudo: el radian de Jorels exige su grupo de facturacion electronica y
        # contabilidad no siempre lo tiene. El firmante sigue siendo user_id.
        # company_id explicito: Jorels toma token y ambiente de la compania del
        # evento, y los prechequeos se hicieron con la de la factura.
        radian = self._spr_radian_model().sudo().create({
            "move_id": self.id,
            "event_id": event.id,
            "type": "supplier",
            "user_id": self.env.user.id,
            "company_id": company.id,
            "note": _("Generado desde la factura de proveedor."),
        })
        radian.action_post()
        if company.enable_validate_state:
            # Con el estado intermedio "Validacion DIAN" Jorels no valida al
            # publicar (radian.py, action_post): se valida aqui.
            radian.validate_dian()
        if company.is_not_test and not radian.edi_is_valid:
            # Con ei_always_validate Jorels no lanza, solo deja el error en el
            # chatter del evento; sin esto se seguiria con los siguientes.
            detail = " ".join(
                part for part in (radian.edi_status_message, radian.edi_errors_messages)
                if part and part not in ("None", "[]")
            )
            raise UserError(_("La DIAN no valido el evento %(name)s. %(detail)s") % {
                "name": radian.name, "detail": detail,
            })
        # En habilitacion (no is_not_test) Jorels devuelve el zip_key sin
        # is_valid: el evento queda enviado en habilitacion y se acepta.
        return radian.name

    def action_spr_generate_radian_events(self):
        """Genera y valida los eventos RADIAN de receptor de una factura de
        proveedor: acuse de recibo (030), recibo del bien (032) y aceptacion
        expresa (033), en ese orden (DECISIONS.md #72).

        Cada evento va en su propio savepoint: si uno falla se revierte solo
        ese y no se intentan los siguientes (032 exige 030, 033 exige 032).
        Tras un fallo parcial no se lanza error, porque el rollback borraria
        eventos que la DIAN ya acepto; el resultado va al chatter y a una
        notificacion.
        """
        self.ensure_one()
        # No basta con que el boton este visible: se valida otra vez.
        reason = self._spr_radian_blocking_reason()
        if reason:
            raise UserError(reason)
        missing = self._spr_radian_missing_requirements()
        if missing:
            raise UserError(_("No se pueden enviar los eventos RADIAN. Falta:\n%s")
                            % "\n".join("- %s" % item for item in missing))

        # Jorels lee el CUFE de la factura en ei_uuid; el portal lo guarda en
        # cufe. Se puentea para que el evento lo encuentre.
        if not self.ei_uuid:
            self.sudo().ei_uuid = self.cufe

        validated, error = [], False
        for code in SPRADIAN_SUPPLIER_EVENT_CODES:
            try:
                with self.env.cr.savepoint():
                    validated.append(self._spr_send_radian_event(code))
            except Exception as exc:  # noqa: BLE001 - se informa y se conservan los validados
                _logger.exception("[SPR] Factura %s: fallo el evento RADIAN %s.",
                                  self.display_name, code)
                if self._spr_is_edipo_unreachable(exc):
                    detail = _("No hubo respuesta del servicio de facturacion electronica "
                               "(Edipo); el evento %s no se registro. Revise la conexion y "
                               "vuelva a intentar") % code
                else:
                    detail = exc.args[0] if exc.args else exc
                error = _("Fallo el evento %(code)s: %(error)s") % {
                    "code": code, "error": detail,
                }
                break

        done = ", ".join(validated) or _("ninguno")
        if error and not validated:
            # Nada quedo registrado: la factura sigue sin eventos y el mismo
            # boton sirve para reintentar.
            message = _(
                "No se registro ningun evento RADIAN. %s. Corrija la causa y vuelva a "
                "pulsar 'Generar eventos RADIAN'."
            ) % error
        elif error:
            message = _(
                "Eventos RADIAN de receptor validados: %(done)s. %(error)s. Los eventos "
                "ya validados se conservan; corrija la causa y genere los que faltan "
                "desde los eventos de facturacion electronica."
            ) % {"done": done, "error": error}
        else:
            message = _(
                "Eventos RADIAN de receptor generados y validados: acuse (030), recibo "
                "del bien (032) y aceptacion expresa (033): %s."
            ) % done
        self.message_post(body=message)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Eventos RADIAN"),
                "message": message,
                "type": "warning" if error else "success",
                "sticky": bool(error),
                # Recarga el formulario para ocultar el boton y ver los eventos.
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
