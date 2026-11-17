# -*- coding: utf-8 -*-
"""Una linea de la remision, con el movimiento de inventario al que corresponde."""

from odoo import api, fields, models

from ..services import line_matcher

MATCH_METHODS = [
    ("code", "Por codigo"),
    ("description", "Por descripcion"),
    ("ai", "Por IA"),
    ("manual", "A mano"),
    ("none", "Sin emparejar"),
]

# Como se paso la unidad del papel a la unidad del movimiento.
UOM_STATUSES = [
    ("same", "Misma unidad"),
    ("converted", "Convertida por Odoo"),
    ("ai", "Convertida por IA, con respaldo"),
    ("ai_unverified", "Convertida por IA, sin respaldo"),
    ("manual", "Factor puesto a mano"),
    ("unknown", "Sin conversion"),
]


class StockOperationSupportLine(models.Model):
    _name = "stock.operation.support.line"
    _description = "Linea del soporte de operacion"
    _order = "support_id, sequence, id"

    support_id = fields.Many2one(
        "stock.operation.support", string="Soporte", required=True,
        ondelete="cascade", index=True,
    )
    sequence = fields.Integer(string="Secuencia", default=10)

    # Lo que dice el papel.
    description = fields.Char(string="Descripcion en el soporte")
    code = fields.Char(string="Codigo en el soporte")
    quantity = fields.Float(
        string="Cantidad en el soporte", digits="Product Unit",
    )
    unit = fields.Char(string="Unidad en el soporte")
    is_service = fields.Boolean(
        string="Es servicio",
        help="Envio, domicilio, flete, reintegro: no es mercancia, no se empareja "
             "ni se compara.",
    )

    # De la unidad del papel a la del movimiento: cuantas unidades de la
    # operacion vale una unidad del soporte (caja x 24 -> 24; kg a g -> 1000).
    uom_factor = fields.Float(
        string="Factor de unidad", default=1.0, digits=(16, 6),
        help="Cuantas unidades de la operacion equivalen a una unidad del "
             "soporte. Si lo cambia a mano, se conserva al revalidar.",
    )
    uom_status = fields.Selection(UOM_STATUSES, string="Conversion", default="same")
    uom_note = fields.Char(string="Nota de la conversion")
    quantity_converted = fields.Float(
        string="Cantidad en unidad de la operacion", compute="_compute_picking_quantity",
        digits="Product Unit", store=True,
    )

    # Lo que dice el sistema.
    move_id = fields.Many2one(
        "stock.move", string="Movimiento de la operacion",
        domain="[('picking_id', '=', parent.picking_id)]", ondelete="set null",
    )
    product_id = fields.Many2one(
        related="move_id.product_id", string="Producto", store=True,
    )
    picking_quantity = fields.Float(
        string="Cantidad en la operacion", compute="_compute_picking_quantity",
        digits="Product Unit", store=True,
    )
    quantity_basis = fields.Char(
        string="Base de comparacion", compute="_compute_picking_quantity", store=True,
        help="Si la cantidad de la operacion es la registrada o la esperada.",
    )
    quantity_diff = fields.Float(
        string="Diferencia", compute="_compute_picking_quantity",
        digits="Product Unit", store=True,
        help="Cantidad del soporte menos cantidad de la operacion.",
    )

    match_method = fields.Selection(
        MATCH_METHODS, string="Metodo de emparejamiento", default="none", required=True,
    )
    match_confidence = fields.Float(string="Confianza", digits=(3, 2))
    match_note = fields.Char(string="Nota del emparejamiento")

    @api.depends("move_id", "move_id.quantity", "move_id.product_uom_qty",
                 "move_id.picked", "move_id.picking_id.state", "quantity", "uom_factor")
    def _compute_picking_quantity(self):
        from ..services.support_rules import expected_quantity
        for line in self:
            line.quantity_converted = (line.quantity or 0.0) * (line.uom_factor or 0.0)
            if not line.move_id:
                line.picking_quantity = 0.0
                line.quantity_basis = ""
                line.quantity_diff = 0.0
                continue
            quantity, basis = expected_quantity(line.move_id)
            line.picking_quantity = quantity
            line.quantity_basis = basis
            line.quantity_diff = line.quantity_converted - quantity

    @api.onchange("move_id")
    def _onchange_move_id(self):
        """Emparejar a mano marca la linea como manual y la protege al revalidar."""
        for line in self:
            if line.move_id and line.match_method != "manual":
                line.match_method = "manual"
                line.match_confidence = 1.0
                line.match_note = "Emparejado a mano; se conserva al revalidar."
            elif not line.move_id and line.match_method == "manual":
                line.match_method = "none"
                line.match_confidence = 0.0
                line.match_note = ""

    @api.onchange("uom_factor")
    def _onchange_uom_factor(self):
        """Corregir el factor a mano lo deja fijo, como un emparejamiento manual."""
        for line in self:
            if line.uom_status != "manual":
                line.uom_status = "manual"
                line.uom_note = "Factor ajustado a mano; se conserva al revalidar."

    @api.model
    def _identity_of(self, code, description, quantity):
        """Identidad por contenido, para reconocer una linea aunque cambie de sitio."""
        return (
            line_matcher.normalize_code(code),
            line_matcher.normalize_text(description),
            round(float(quantity or 0.0), 4),
        )

    def _identity(self):
        self.ensure_one()
        return self._identity_of(self.code, self.description, self.quantity)
