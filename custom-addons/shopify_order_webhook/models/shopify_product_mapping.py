import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ShopifyProductMapping(models.Model):
    _name = 'shopify.product.mapping'
    _description = 'Mapeo de productos Shopify → Odoo'
    _order = 'shopify_title, shopify_variant_title'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company,
    )
    shopify_product_id = fields.Char(string='ID producto Shopify', readonly=True)
    shopify_variant_id = fields.Char(
        string='ID variante Shopify', readonly=True, index=True,
    )
    shopify_title = fields.Char(string='Producto Shopify', readonly=True)
    shopify_variant_title = fields.Char(string='Variante', readonly=True)
    shopify_sku = fields.Char(string='SKU', readonly=True, index=True)
    shopify_price = fields.Float(string='Precio Shopify', readonly=True)
    shopify_status = fields.Char(string='Estado Shopify', readonly=True)

    product_id = fields.Many2one(
        'product.product', string='Producto Odoo',
        domain="[('company_id', 'in', [False, company_id])]",
        help="Producto de Odoo al que se mapea esta variante de Shopify. "
             "Cuando está definido, los pedidos de Shopify con esta variante "
             "(o SKU) usan este producto en la línea de venta.",
    )

    state = fields.Selection(
        selection=[('unmapped', 'Sin mapear'), ('mapped', 'Mapeado')],
        string='Estado', compute='_compute_state', store=True,
    )

    # 19: reemplaza ``_sql_constraints``. Mismo nombre en la base
    # (``shopify_product_mapping_shopify_variant_company_uniq``) y misma
    # definición que en 17, para que la actualización no la recree.
    _shopify_variant_company_uniq = models.Constraint(
        'unique(shopify_variant_id, company_id)',
        'La variante de Shopify ya está registrada para esta compañía.',
    )

    @api.depends('product_id')
    def _compute_state(self):
        for rec in self:
            rec.state = 'mapped' if rec.product_id else 'unmapped'

    def action_sync_from_shopify(self):
        """Pull the Shopify catalog and upsert one mapping row per variant.

        Triggered from the list header (``self`` may be empty). Keeps any
        existing ``product_id`` mapping untouched, only refreshing the
        Shopify-side fields.
        """
        company = self.env.company
        variants = company._shopify_fetch_products()

        created = updated = 0
        for v in variants:
            vid = v.get('variant_id')
            if not vid:
                continue
            vals = {
                'company_id':            company.id,
                'shopify_product_id':    v.get('product_id'),
                'shopify_variant_id':    vid,
                'shopify_title':         v.get('title'),
                'shopify_variant_title': v.get('variant_title'),
                'shopify_sku':           v.get('sku'),
                'shopify_price':         v.get('price') or 0.0,
                'shopify_status':        v.get('status'),
            }
            rec = self.search([
                ('shopify_variant_id', '=', vid),
                ('company_id', '=', company.id),
            ], limit=1)
            if rec:
                rec.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1

        _logger.info("Shopify products sync (company=%s): %s nuevos, %s "
                     "actualizados.", company.name, created, updated)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_clear_mapping(self):
        """Remove the Odoo product link on the selected rows."""
        self.write({'product_id': False})
