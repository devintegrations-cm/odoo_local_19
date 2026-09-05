from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    first_order = fields.Datetime(string='First order',
                                  compute='_update_date_order_trigger',
                                  store=True)

    # NOTA MIGRACION 19: el metodo de abajo se usa como compute de un campo
    # almacenado pero esta decorado como constraint, no como dependencia. Verificado
    # en Odoo 19: el valor se fija igual al crear el pedido y al escribir date_order,
    # que es el comportamiento actual en produccion. Se mantiene tal cual a proposito;
    # cambiar el decorador recalcularia pedidos historicos. Decision pendiente del usuario.
    @api.constrains('date_order')
    def _update_date_order_trigger(self):
        for order in self:
            if not order.first_order and order.date_order:
                order.first_order = fields.Datetime.now()
