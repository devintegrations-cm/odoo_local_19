from odoo import SUPERUSER_ID, api

REMOVED_VIEWS = (
    "clara_purchase_bridge.res_config_settings_view_form_inherit_clara",   # the settings of the order flow
    "clara_purchase_bridge.purchase_order_form_inherit_clara",             # named the national id field; recreated by the data file
    "clara_purchase_bridge.purchase_order_tree_inherit_clara",
    "clara_purchase_bridge.purchase_order_search_inherit_clara",
)


def migrate(cr, version):
    """2.0.0: the module no longer books orders. The views of the order flow go before Odoo validates the purchase
    views with them (they name fields this version removes); the data file recreates the ones that stay. The
    unique index that kept one live order per transaction, and the full constraint of versions before 1.3.0, are
    dropped: nothing in the module creates orders any more. No order and no transaction is touched."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in REMOVED_VIEWS:
        view = env.ref(xmlid, raise_if_not_found=False)
        if view:
            view.unlink()
    cr.execute("DROP INDEX IF EXISTS purchase_order_clara_transaction_uuid_live_uniq")
    cr.execute("ALTER TABLE purchase_order DROP CONSTRAINT IF EXISTS purchase_order_clara_transaction_uuid_unique")
    cr.execute("DELETE FROM ir_model_constraint WHERE name = 'purchase_order_clara_transaction_uuid_unique'")
