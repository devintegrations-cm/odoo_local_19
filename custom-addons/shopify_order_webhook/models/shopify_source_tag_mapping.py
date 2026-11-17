from odoo import models, fields


class ShopifySourceTagMapping(models.Model):
    _name = 'shopify.source.tag.mapping'
    _description = 'Shopify Order Source — Odoo CRM Tag Mapping'
    _rec_name = 'source_pattern'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
        index=True,
    )

    source_pattern = fields.Char(
        string='Source Pattern',
        required=True,
        help=(
            "Case-insensitive substring matched against the Shopify order "
            "'source_name' field (e.g. 'atria', 'web', 'shopify_draft_order'). "
            "The first record whose pattern is contained in source_name wins."
        ),
    )
    tag_id = fields.Many2one(
        'crm.tag',
        string='Sale Order Tag',
        required=True,
        help="Tag applied to the sale order when the pattern matches.",
    )
