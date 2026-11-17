from odoo import SUPERUSER_ID, api

REMOVED_PARAMS = (
    "clara_purchase_bridge.reviewer_user_id",
    "clara_purchase_bridge.order_user_id",
    "clara_purchase_bridge.accounting_partner_email",
    "clara_purchase_bridge.description_area",
    "clara_purchase_bridge.store_code_prefix",
    "clara_purchase_bridge.travel_keyword",
    "clara_purchase_bridge.amount_tolerance",
    "clara_purchase_bridge.vat_rounding_allowance",
)


def migrate(cr, version):
    """The parameters of the order flow (reviewer, bot user, accounting contact, Expansión rules, tolerances) are
    deleted: no setting of this version reads them. The reviewer parameter was a noupdate record, so the data
    file cannot remove it."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.config_parameter"].search([("key", "in", REMOVED_PARAMS)]).unlink()
