from odoo import api, fields, models

PREFIX = "purchase_cost_validator."


class PurchaseCostValidatorConfig(models.TransientModel):
    """The validator's own settings screen. Saves only its parameters, so it works even when the general settings
    page cannot be saved (for instance with point of sale sessions open)."""

    _name = "purchase.cost.validator.config"
    _description = "Configuración del validador de costos"

    reviewer_id = fields.Many2one("res.users", string="Revisor de compras", domain=[("share", "=", False)],
                                  help="Recibe el aviso (correo o bandeja de Odoo, según su preferencia) y una actividad cuando una recepción trae valores incoherentes. Sin revisor, se avisa a los administradores de compras.")
    hold_receipt = fields.Boolean(string="Retener la recepción hasta que el revisor la apruebe",
                                  help="Con desfase incoherente, solo el revisor o un administrador de inventario puede validar la recepción; así el costo dañado no entra. Apagado: la recepción pasa y solo se avisa.")
    start_date = fields.Datetime(string="Fecha de arranque", help="Solo se revisan las órdenes creadas desde esta fecha y sus recepciones. Lo anterior queda exactamente igual.")
    gross_factor = fields.Float(string="Desfase incoherente (veces)", help="Rojo cuando el precio por unidad es esta cantidad de veces mayor o menor que el costo del producto. 2 = más del doble o menos de la mitad.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        icp = self.env["ir.config_parameter"].sudo()
        uid = int(icp.get_param(PREFIX + "reviewer_user_id") or 0)
        res.update({
            "reviewer_id": self.env["res.users"].browse(uid).exists().id if uid else False,
            "hold_receipt": icp.get_param(PREFIX + "hold_receipt", "False") == "True",
            "gross_factor": float(icp.get_param(PREFIX + "gross_factor") or 2.0),
            "start_date": self.env["purchase.order.line"]._cost_check_start(),
        })
        return res

    def action_save(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PREFIX + "reviewer_user_id", str(self.reviewer_id.id or ""))
        icp.set_param(PREFIX + "hold_receipt", "True" if self.hold_receipt else "False")
        icp.set_param(PREFIX + "gross_factor", str(max(self.gross_factor or 2.0, 1.01)))
        icp.set_param(PREFIX + "start_date", fields.Datetime.to_string(self.start_date or fields.Datetime.now()))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Validador de costos", "message": "Configuración guardada.", "type": "success", "next": {"type": "ir.actions.act_window_close"}}}
