# -*- coding: utf-8 -*-
"""Soporte de una operacion de inventario: la remision firmada y su validacion."""

import base64
import json
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, html_escape

from ..services import line_matcher, support_rules, vision_adapter

_logger = logging.getLogger(__name__)

STATES = [
    ("draft", "Borrador"),
    ("validating", "Validando"),
    ("approved", "Aprobado"),
    ("warning", "Con observaciones"),
    ("rejected", "No paso las validaciones"),
]

LEVEL_LABELS = {
    support_rules.LEVEL_ERROR: ("Error", "text-danger"),
    support_rules.LEVEL_WARNING: ("Observacion", "text-warning"),
    support_rules.LEVEL_OK: ("Correcto", "text-success"),
}


class StockOperationSupport(models.Model):
    _name = "stock.operation.support"
    _description = "Soporte de operacion de inventario"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Referencia", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"),
    )
    picking_id = fields.Many2one(
        "stock.picking", string="Operacion", required=True, ondelete="cascade",
        index=True, tracking=True,
    )
    picking_code = fields.Selection(
        related="picking_id.picking_type_code", string="Tipo de operacion", store=True,
    )
    picking_state = fields.Selection(related="picking_id.state", string="Estado de la operacion")
    partner_id = fields.Many2one(
        related="picking_id.partner_id", string="Contacto", store=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Compania", required=True,
        default=lambda self: self.env.company,
    )

    # El comprobante es un adjunto de la operacion, no del soporte: las fotos
    # ya se adjuntan a las recepciones, y asi quedan a la vista de quien abra
    # la recepcion y no se guardan dos veces.
    attachment_id = fields.Many2one(
        "ir.attachment", string="Comprobante", copy=False, tracking=True,
        domain="[('res_model', '=', 'stock.picking'), ('res_id', '=', picking_id),"
               " '|', ('mimetype', '=like', 'image/%'), ('mimetype', '=', 'application/pdf')]",
        help="Foto o PDF adjunto a la operacion. Elija uno de los que ya tiene, "
             "o suba otro abajo: queda adjunto a la operacion.",
    )
    # Para subir un archivo nuevo desde el soporte. No se guarda aqui: al
    # guardar se crea el adjunto en la operacion y el Comprobante apunta a el.
    support_file = fields.Binary(
        string="Archivo", compute="_compute_support_file",
        inverse="_inverse_support_file",
        help="El archivo del comprobante. Para usar otro, subalo aqui (JPG, PNG, "
             "WEBP, GIF o PDF): queda adjunto a la operacion.",
    )
    support_filename = fields.Char(
        string="Nombre del archivo", compute="_compute_support_file",
        inverse="_inverse_support_file",
    )

    state = fields.Selection(
        STATES, string="Estado", default="draft", required=True, copy=False, tracking=True,
    )

    extracted_json = fields.Text(string="Datos leidos (JSON)", readonly=True, copy=False)
    validation_json = fields.Text(string="Validacion (JSON)", readonly=True, copy=False)
    validation_summary = fields.Html(
        string="Resumen de la validacion", readonly=True, copy=False, sanitize=False,
    )

    # Datos del documento. Se llenan con la lectura de la IA y se pueden
    # corregir a mano: lo capturado se conserva al revalidar.
    remission_ref = fields.Char(string="Numero del documento", tracking=True, copy=False)
    document_type = fields.Selection(
        [("remision", "Remision"), ("factura", "Factura electronica"),
         ("tiquete_pos", "Tiquete de caja (POS)"), ("otro", "Otro")],
        string="Tipo de documento", copy=False,
        help="Lo decide la IA al leer y se puede corregir. De esto depende que "
             "firmas se exigen: un tiquete de caja no trae ninguna.",
    )
    remission_date = fields.Date(string="Fecha de la remision", copy=False)
    sender_nit = fields.Char(string="NIT de quien entrega", copy=False)
    sender_name = fields.Char(string="Razon social de quien entrega", copy=False)
    receiver_nit = fields.Char(string="NIT de quien recibe", copy=False)
    receiver_name = fields.Char(string="Razon social de quien recibe", copy=False)

    signature_sender_ok = fields.Boolean(string="Firma de quien entrega", copy=False)
    signature_sender_name = fields.Char(string="Nombre de quien entrega", copy=False)
    signature_sender_confidence = fields.Float(
        string="Confianza (entrega)", digits=(3, 2), readonly=True, copy=False,
    )
    signature_receiver_ok = fields.Boolean(string="Firma de quien recibe", copy=False)
    signature_receiver_name = fields.Char(string="Nombre de quien recibe", copy=False)
    signature_receiver_confidence = fields.Float(
        string="Confianza (recibe)", digits=(3, 2), readonly=True, copy=False,
    )

    vision_confidence = fields.Float(
        string="Legibilidad", digits=(3, 2), readonly=True, copy=False,
        help="Que tan legible quedo el documento segun la IA, de 0 a 1.",
    )
    vision_provider = fields.Char(string="Lector", readonly=True, copy=False)

    line_ids = fields.One2many(
        "stock.operation.support.line", "support_id", string="Lineas del soporte", copy=True,
    )
    notes = fields.Text(string="Notas")

    # Ajustes que cambian que se muestra en el formulario.
    party_check_enabled = fields.Boolean(compute="_compute_checks_enabled")
    signature_check_enabled = fields.Boolean(compute="_compute_checks_enabled")

    # Misma restriccion de 17: conserva el nombre stock_operation_support_name_uniq.
    _name_uniq = models.Constraint(
        "UNIQUE (name)", "La referencia del soporte debe ser unica.",
    )

    # ------------------------------------------------------------------
    # Computados y CRUD
    # ------------------------------------------------------------------

    @api.depends("attachment_id")
    def _compute_support_file(self):
        for support in self:
            support.support_file = support.attachment_id.datas
            support.support_filename = support.attachment_id.name

    def _inverse_support_file(self):
        for support in self:
            if not support.support_file or (
                support.attachment_id and support.attachment_id.datas == support.support_file
            ):
                continue
            support.attachment_id = self.env["ir.attachment"].create({
                "name": support.support_filename or "comprobante.jpg",
                "datas": support.support_file,
                "res_model": "stock.picking",
                "res_id": support.picking_id.id,
            })

    @api.constrains("attachment_id", "picking_id")
    def _check_attachment_belongs_to_picking(self):
        for support in self.filtered("attachment_id"):
            attachment = support.attachment_id
            if attachment.res_model != "stock.picking" or attachment.res_id != support.picking_id.id:
                raise ValidationError(_(
                    "El comprobante de %s tiene que ser un adjunto de la operacion %s."
                ) % (support.name, support.picking_id.name))

    @api.depends("company_id")
    def _compute_checks_enabled(self):
        party = support_rules.party_check_enabled(self.env)
        signature = support_rules.signature_check_enabled(self.env)
        for support in self:
            support.party_check_enabled = party
            support.signature_check_enabled = signature

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", _("Nuevo")) == _("Nuevo"):
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "stock.operation.support"
                ) or _("Nuevo")
        return super().create(vals_list)

    def write(self, vals):
        # Otra foto es otro documento: lo leido de la anterior ya no aplica.
        if "attachment_id" in vals:
            replaced = self.filtered(
                lambda s: s.attachment_id and s.attachment_id.id != vals["attachment_id"])
            if replaced:
                replaced.line_ids.unlink()
                super(StockOperationSupport, replaced).write(self._document_reset_values())
        return super().write(vals)

    @api.model
    def _document_reset_values(self):
        return {
            "extracted_json": False,
            "vision_confidence": 0.0,
            "vision_provider": False,
            "remission_ref": False,
            "document_type": False,
            "remission_date": False,
            "sender_nit": False,
            "sender_name": False,
            "receiver_nit": False,
            "receiver_name": False,
            "signature_sender_ok": False,
            "signature_sender_name": False,
            "signature_sender_confidence": 0.0,
            "signature_receiver_ok": False,
            "signature_receiver_name": False,
            "signature_receiver_confidence": 0.0,
        }

    @api.onchange("signature_sender_ok")
    def _onchange_signature_sender_ok(self):
        """Marcar la casilla a mano es confirmar la firma mirando la foto."""
        self.signature_sender_confidence = 1.0 if self.signature_sender_ok else 0.0

    @api.onchange("signature_receiver_ok")
    def _onchange_signature_receiver_ok(self):
        self.signature_receiver_confidence = 1.0 if self.signature_receiver_ok else 0.0

    @api.onchange("picking_id")
    def _onchange_picking_id(self):
        """Propone la compania de la operacion."""
        if self.picking_id:
            self.company_id = self.picking_id.company_id

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def action_validate(self):
        """Corre las reglas sobre los datos del formulario.

        La foto se lee solo si todavia no hay una lectura buena, y esa lectura
        solo llena lo que este vacio: lo que una persona corrigio no se pisa.
        """
        for support in self:
            support._run_pipeline()
        return True

    def action_reread(self):
        """Vuelve a leer la foto y reemplaza los datos con lo que lea la IA.

        Lo unico que se conserva son las lineas emparejadas a mano.
        """
        for support in self:
            support._run_pipeline(reread=True)
        return True

    def _stored_reading(self):
        """La ultima lectura guardada, o un dict vacio."""
        self.ensure_one()
        try:
            return json.loads(self.extracted_json or "{}")
        except ValueError:
            return {}

    def _run_pipeline(self, reread=False):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_(
                "Elija o suba el comprobante antes de validar: la foto o el PDF "
                "de la remision, factura o tiquete."
            ))
        if self.state == "validating":
            raise UserError(_("El soporte ya se esta validando."))

        self.state = "validating"
        adapter = vision_adapter.get_vision_adapter(self.env)
        parsed = self._stored_reading()
        if reread or not parsed.get("available"):
            parsed = self._extract_data(adapter)
            self._apply_extracted_data(parsed, overwrite=reread)
        line_matcher.match_lines(self, adapter)

        findings = support_rules.run_rules(self, parsed)
        verdict = support_rules.verdict_from_findings(findings)
        self._apply_findings(findings, verdict)
        self._notify_picking(findings, verdict)
        self._auto_validate_picking()
        _logger.info("[SOS] %s: veredicto %s con %s hallazgos",
                     self.name, verdict, len(findings))
        return verdict

    def _extract_data(self, adapter):
        """Llama a la IA de vision. Nunca lanza excepcion hacia arriba."""
        self.ensure_one()
        try:
            file_bytes = base64.b64decode(self.attachment_id.datas or b"")
        except Exception:  # noqa: BLE001 - un adjunto corrupto no debe tumbar la validacion
            _logger.warning("[SOS] %s: no se pudo decodificar el comprobante.", self.name)
            return vision_adapter.degraded_result("odoo", "el comprobante no se pudo leer")

        file_bytes, filename = vision_adapter.prepare_image(file_bytes, self.attachment_id.name)
        _logger.info("[SOS] %s: leyendo el comprobante con %s", self.name, adapter.name)
        return adapter.extract(file_bytes, filename, self._vision_hint())

    def _vision_hint(self):
        """Contexto que ayuda a leer, sin decirle a la IA que resultado queremos."""
        self.ensure_one()
        sender, receiver = support_rules.parties_for(self.picking_id)
        moves = self.picking_id.move_ids.filtered(lambda m: m.state != "cancel")
        return {
            "expected_sender": sender["name"],
            "expected_receiver": receiver["name"],
            "expected_lines": [
                {"description": move.product_id.name,
                 "code": move.product_id.default_code or ""}
                for move in moves[:50]
            ],
        }

    def _apply_extracted_data(self, parsed, overwrite=False):
        """Vuelca lo leido al formulario.

        Con ``overwrite`` en False (la lectura automatica de Validar) solo se
        llena lo que este vacio y las lineas solo si no hay ninguna: si la IA
        se cayo y alguien capturo a mano, o corrigio un dato mal leido, eso
        manda. Con ``overwrite`` (el boton Volver a leer la foto) se reemplaza
        todo salvo los emparejamientos manuales.
        """
        self.ensure_one()
        self.extracted_json = json.dumps(parsed, ensure_ascii=False, indent=1, default=str)
        self.vision_confidence = parsed.get("confidence") or 0.0
        self.vision_provider = parsed.get("provider") or ""

        if not parsed.get("available"):
            # Servicio caido: se conserva lo que ya hubiera capturado el usuario.
            return

        values = {}
        sender = parsed.get("sender") or {}
        receiver = parsed.get("receiver") or {}
        signatures = parsed.get("signatures") or {}
        sender_signature = signatures.get("sender") or {}
        receiver_signature = signatures.get("receiver") or {}

        candidates = {
            "remission_ref": parsed.get("remission_ref"),
            "document_type": parsed.get("document_type"),
            "sender_nit": sender.get("nit"),
            "sender_name": sender.get("name"),
            "receiver_nit": receiver.get("nit"),
            "receiver_name": receiver.get("name"),
            "signature_sender_name": sender_signature.get("name"),
            "signature_receiver_name": receiver_signature.get("name"),
        }
        if parsed.get("issue_date"):
            candidates["remission_date"] = parsed["issue_date"]
        for field_name, value in candidates.items():
            if value and (overwrite or not self[field_name]):
                values[field_name] = value

        for key, signature in (("sender", sender_signature), ("receiver", receiver_signature)):
            ok_field = "signature_%s_ok" % key
            if overwrite or not self[ok_field]:
                values[ok_field] = bool(signature.get("present"))
                values["signature_%s_confidence" % key] = signature.get("confidence") or 0.0
        self.write(values)

        if overwrite or not self.line_ids:
            self._apply_lines(parsed.get("lines") or [])

    def _apply_lines(self, lines):
        """Reemplaza las lineas leidas, conservando lo que se hizo a mano.

        Se conservan el emparejamiento y el factor de unidad puestos a mano.

        Los manuales se reconocen por contenido (codigo, descripcion, cantidad)
        y no por posicion: reordenar el documento no debe mover un
        emparejamiento hecho a mano a otra linea.
        """
        self.ensure_one()
        manual = {}
        for line in self.line_ids.filtered(
            lambda l: l.match_method == "manual" or l.uom_status == "manual"
        ):
            manual[line._identity()] = {
                "match_method": line.match_method,
                "move_id": line.move_id.id,
                "uom_factor": line.uom_factor,
                "uom_status": line.uom_status,
                "uom_note": line.uom_note,
            }

        self.line_ids.unlink()
        values = []
        for index, line in enumerate(lines):
            identity = self.env["stock.operation.support.line"]._identity_of(
                line.get("code"), line.get("description"), line.get("quantity")
            )
            line_values = {
                "sequence": line.get("sequence") or index + 1,
                "description": line.get("description") or "",
                "code": line.get("code") or "",
                "quantity": line.get("quantity") or 0.0,
                "unit": line.get("unit") or "",
                "is_service": bool(line.get("is_service")),
            }
            previous = manual.get(identity)
            if previous and previous["match_method"] == "manual":
                line_values.update({
                    "move_id": previous["move_id"],
                    "match_method": "manual",
                    "match_confidence": 1.0,
                    "match_note": "Emparejado a mano; se conserva al revalidar.",
                })
            if previous and previous["uom_status"] == "manual":
                line_values.update({
                    "uom_factor": previous["uom_factor"],
                    "uom_status": "manual",
                    "uom_note": previous["uom_note"],
                })
            values.append((0, 0, line_values))
        if values:
            self.line_ids = values

    def _apply_findings(self, findings, verdict):
        self.ensure_one()
        payload = {
            "verdict": verdict,
            "findings": [finding.to_dict() for finding in findings],
        }
        self.write({
            "validation_json": json.dumps(payload, ensure_ascii=False, indent=1, default=str),
            "validation_summary": self._render_validation_summary(findings, verdict),
            "state": verdict,
        })

    def _render_validation_summary(self, findings, verdict):
        """HTML del resumen. Todo lo que viene del documento se escapa."""
        verdict_label = dict(STATES).get(verdict, verdict)
        rows = []
        order = {support_rules.LEVEL_ERROR: 0, support_rules.LEVEL_WARNING: 1,
                 support_rules.LEVEL_OK: 2}
        for finding in sorted(findings, key=lambda f: order.get(f.level, 3)):
            label, css = LEVEL_LABELS.get(finding.level, ("", ""))
            rows.append(
                "<tr><td class='%s'><b>%s</b></td><td><code>%s</code></td><td>%s</td></tr>"
                % (css, html_escape(label), html_escape(finding.code),
                   html_escape(finding.message_es))
            )
        return (
            "<p><b>Veredicto:</b> %s</p>"
            "<table class='table table-sm'>"
            "<thead><tr><th>Nivel</th><th>Codigo</th><th>Detalle</th></tr></thead>"
            "<tbody>%s</tbody></table>"
        ) % (html_escape(verdict_label), "".join(rows))

    def _notify_picking(self, findings, verdict):
        """Deja el veredicto en el chatter de la operacion.

        El modulo no bloquea nada: quien valida la operacion ve el aviso y
        decide. Por eso el mensaje tiene que ser legible de un vistazo.
        """
        self.ensure_one()
        problems = [f for f in findings
                    if f.level in (support_rules.LEVEL_ERROR, support_rules.LEVEL_WARNING)]
        verdict_label = dict(STATES).get(verdict, verdict)
        # Markup: Odoo 17 escapa un str en message_post y el chatter mostraria
        # las etiquetas como texto. Markup % (...) escapa solo los valores.
        if problems:
            detail = Markup("").join(
                Markup("<li>%s</li>") % finding.message_es for finding in problems[:10]
            )
            body = Markup("<p>Soporte <b>%s</b>: %s.</p><ul>%s</ul>") % (
                self.name, verdict_label, detail)
        else:
            body = Markup(
                "<p>Soporte <b>%s</b>: %s. El comprobante respalda la operacion.</p>"
            ) % (self.name, verdict_label)
        self.picking_id.message_post(body=body)
        self.message_post(body=body)

    # ------------------------------------------------------------------
    # Validacion automatica de la recepcion
    # ------------------------------------------------------------------

    def _exact_match_reason(self):
        """Por que la recepcion NO se puede validar sola, o "" si se puede.

        Solo se valida sola una recepcion lista cuyo soporte quedo aprobado y
        cuadra exacto: la tolerancia de cantidades sirve para no marcar error,
        no para mover inventario sin que nadie lo mire.
        """
        self.ensure_one()
        picking = self.picking_id
        if not support_rules.auto_validate_enabled(self.env):
            return "la validacion automatica esta apagada en Ajustes"
        if picking.picking_type_code != "incoming":
            return "solo se validan solas las recepciones"
        if picking.state != "assigned":
            return "la operacion no esta lista (estado %s)" % picking.state
        if self.state != "approved":
            return "el soporte no quedo aprobado"
        moves = picking.move_ids.filtered(lambda m: m.state != "cancel")
        if moves.filtered(lambda m: m.product_id.tracking != "none"):
            return "hay productos con lote o numero de serie"
        if self.line_ids.filtered(lambda l: l.uom_status in ("unknown", "ai_unverified")):
            return "hay unidades sin conversion confirmada"
        for move in moves:
            lines = self.line_ids.filtered(lambda l: l.move_id == move)
            document_qty = sum(lines.mapped("quantity_converted"))
            if not lines or float_compare(
                document_qty, move.product_uom_qty,
                precision_rounding=move.product_uom.rounding,
            ):
                return "%s no cuadra exacto con lo pedido" % move.product_id.display_name
        return ""

    def _auto_validate_picking(self):
        """Valida la recepcion si el soporte coincide exactamente con lo pedido.

        Cualquier cosa que Odoo pida al validar (un asistente, un dato que
        falta) deja la recepcion como estaba y el motivo en el chatter: este
        paso nunca hace fallar la validacion del soporte.
        """
        self.ensure_one()
        picking = self.picking_id
        reason = self._exact_match_reason()
        if reason:
            if self.state == "approved" and picking.state == "assigned":
                _logger.info("[SOS] %s: %s no se valida sola: %s", self.name, picking.name, reason)
            return False
        try:
            with self.env.cr.savepoint():
                for move in picking.move_ids.filtered(lambda m: m.state != "cancel"):
                    if float_compare(move.quantity, move.product_uom_qty,
                                     precision_rounding=move.product_uom.rounding):
                        move.quantity = move.product_uom_qty
                    move.picked = True
                result = picking.button_validate()
                if result is not True:
                    # Un asistente (devoluciones parciales, SMS...) espera a una persona.
                    raise UserError(_("Odoo pidio confirmar algo antes de validar."))
        except UserError as error:
            message = Markup(
                "<p>El soporte <b>%s</b> cuadra exacto, pero la recepcion no se pudo "
                "validar sola: %s Validela a mano.</p>"
            ) % (self.name, str(error.args[0] if error.args else error))
            picking.message_post(body=message)
            self.message_post(body=message)
            _logger.warning("[SOS] %s: no se pudo validar %s: %s", self.name, picking.name, error)
            return False
        message = Markup(
            "<p>Recepcion validada automaticamente: el soporte <b>%s</b> (remision %s) "
            "coincide exactamente con lo pedido.</p>"
        ) % (self.name, self.remission_ref or "-")
        picking.message_post(body=message)
        self.message_post(body=message)
        _logger.info("[SOS] %s: %s validada automaticamente", self.name, picking.name)
        return True

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_reset_to_draft(self):
        for support in self:
            # Los datos del documento se quedan: volver a borrador es para
            # cambiar la foto o la operacion, y cambiar la foto ya los limpia.
            support.write({
                "state": "draft",
                "validation_json": False,
                "validation_summary": False,
            })
        return True

    def action_open_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.picking_id.id,
            "view_mode": "form",
        }
