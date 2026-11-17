from odoo import models, fields


class ShopifyOrderSimulation(models.TransientModel):
    _name = 'shopify.order.simulation'
    _description = 'Resultado de la simulación de órdenes de Shopify'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        readonly=True,
    )

    result_html = fields.Html(
        string='Resultado',
        readonly=True,
        sanitize=False,
    )
