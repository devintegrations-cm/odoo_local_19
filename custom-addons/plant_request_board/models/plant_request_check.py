from odoo import api, fields, models


class PlantRequestCheck(models.Model):
    """A tick of the plant on one line of a request: coffee by line × presentation (Paz 200 en grano, Paz
    Preparación 2.5, a ready product) and supplies by product, built from the order lines and kept in step with
    them. A visual guide for the preparation only: it never touches quantities, moves or stock. Who ticked and
    when are kept; the request's stage follows the ticks."""

    _name = "plant.request.check"
    _description = "Chuleo de alistamiento de una solicitud"
    _order = "picking_id, sequence, id"

    picking_id = fields.Many2one("stock.picking", string="Solicitud", required=True, ondelete="cascade", index=True)
    key = fields.Char(string="Clave", required=True, index=True, help="Fila de la hoja (línea × gramos × molienda) o producto al que corresponde el chuleo.")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Línea", required=True)
    kind_code = fields.Char(string="Tipo")
    qty_text = fields.Char(string="Cantidad", help="Lo pedido en esta línea: bolsas, unidades o kg de café a granel.")
    move_ids = fields.Many2many("stock.move", "plant_request_check_move_rel", "check_id", "move_id", string="Líneas del pedido")
    done = fields.Boolean(string="Alistado")
    done_by = fields.Many2one("res.users", string="Alistó", readonly=True)
    done_date = fields.Datetime(string="Alistado el", readonly=True)

    def write(self, vals):
        if "done" in vals:
            vals = dict(vals, done_by=self.env.uid if vals["done"] else False, done_date=fields.Datetime.now() if vals["done"] else False)
        res = super().write(vals)
        if "done" in vals and not self.env.context.get("plant_skip_notify"):
            self.picking_id._plant_notify_update()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("done"):
                vals.setdefault("done_by", self.env.uid)
                vals.setdefault("done_date", fields.Datetime.now())
        return super().create(vals_list)

    def action_toggle(self):
        for check in self:
            check.done = not check.done
        return True
