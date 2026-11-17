# -*- coding: utf-8 -*-
"""El boton "Agregar soporte de operacion" y el contador en la operacion."""

from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    support_ids = fields.One2many(
        "stock.operation.support", "picking_id", string="Soportes de la operacion",
    )
    support_count = fields.Integer(
        string="Soportes", compute="_compute_support_count",
    )
    support_state = fields.Selection(
        [
            ("none", "Sin soporte"),
            ("draft", "Sin validar"),
            ("approved", "Soporte aprobado"),
            ("warning", "Soporte con observaciones"),
            ("rejected", "Soporte con errores"),
        ],
        string="Estado del soporte", compute="_compute_support_count",
        help="Resume los soportes de la operacion. Es informativo: no impide "
             "validar la operacion.",
    )

    @api.depends("support_ids.state")
    def _compute_support_count(self):
        """El estado lo da el soporte mas reciente.

        Si una remision salio rechazada y luego se subio la foto buena, manda
        la buena: el operario no puede borrar la vieja, y la cabecera no debe
        quedarse diciendo "con errores" para siempre.
        """
        for picking in self:
            supports = picking.support_ids
            picking.support_count = len(supports)
            if not supports:
                picking.support_state = "none"
                continue
            latest = max(supports, key=lambda support: support._origin.id or 0)
            picking.support_state = (
                latest.state if latest.state in ("approved", "warning", "rejected")
                else "draft"
            )

    def _latest_support_attachment(self):
        """La foto o PDF mas reciente adjunto a la operacion, para proponerlo."""
        self.ensure_one()
        return self.env["ir.attachment"].search([
            ("res_model", "=", "stock.picking"), ("res_id", "=", self.id),
            "|", ("mimetype", "=like", "image/%"), ("mimetype", "=", "application/pdf"),
        ], order="create_date desc, id desc", limit=1)

    def action_add_operation_support(self):
        """Abre el formulario de un soporte nuevo, con la ultima foto propuesta."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar soporte de operacion"),
            "res_model": "stock.operation.support",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_picking_id": self.id,
                "default_company_id": self.company_id.id,
                "default_attachment_id": self._latest_support_attachment().id,
            },
        }

    def action_view_operation_supports(self):
        """Smart button: los soportes ya cargados en esta operacion."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Soportes de %s") % self.name,
            "res_model": "stock.operation.support",
            "context": {
                "default_picking_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }
        if len(self.support_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.support_ids.id})
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("picking_id", "=", self.id)],
            })
        return action
