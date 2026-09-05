from odoo import api, fields, models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    first_waitress = fields.Char(string='First waitress',
                                  compute='_update_date_order_trigger_waitress',
                                  store=True)

    @api.constrains('employee_id')
    def _update_date_order_trigger_waitress(self):
        for order in self:
            if not order.first_waitress and order.employee_id:
                order.first_waitress = order.employee_id.name
