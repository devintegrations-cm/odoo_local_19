from odoo import models, fields


class ShopifyPaymentJournalMapping(models.Model):
    _name = 'shopify.payment.journal.mapping'
    _description = 'Shopify Payment Method — Odoo Journal Mapping'
    _rec_name = 'shopify_gateway'
    _order = 'shopify_gateway'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
        index=True,
    )

    shopify_gateway = fields.Char(
        string='Shopify Payment ID',
        required=True,
        help=(
            "Gateway identifier from Shopify order payload "
            "'payment_gateway_names' (e.g. shopify_payments, paypal, manual)."
        ),
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Odoo Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help="Journal used to register inbound payments for this Shopify gateway.",
        check_company=True,
    )
