from odoo import SUPERUSER_ID, api

# the scheduled actions of earlier versions: three interval crons and the weekly run that booked purchase orders
REMOVED_CRONS = (
    "clara_connector.ir_cron_clara_sync_transactions",
    "clara_connector.ir_cron_clara_sync_cards",
    "clara_connector.ir_cron_clara_process_orders",
    "clara_connector.ir_cron_clara_weekly_run",
)


def migrate(cr, version):
    """2.0.0: read-only connector. Every view of the module is dropped here and recreated by the data files: the old
    ones name fields and buttons this version removes (order creation, labels, card lock, expenses), and Odoo
    validates each base view together with its inherited views before the files reload them. The crons of the
    order flow are deleted (the data file creates the single weekly sync). Transactions and cards are not touched."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    views = env["ir.model.data"].search([("module", "=", "clara_connector"), ("model", "=", "ir.ui.view")])
    env["ir.ui.view"].browse(views.mapped("res_id")).exists().unlink()
    for xmlid in REMOVED_CRONS:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if cron:
            cron.unlink()
    # clara.card.periodicity was a Selection and is a Char now: the reflected selection values of the old field would
    # make Odoo's end-of-update cleanup fail (it applies selection "ondelete" rules to a Char), so they go here
    cr.execute("""DELETE FROM ir_model_data WHERE module = 'clara_connector' AND model = 'ir.model.fields.selection'
                  AND name LIKE 'selection__clara_card__periodicity__%'""")
    cr.execute("""DELETE FROM ir_model_fields_selection WHERE field_id IN
                  (SELECT id FROM ir_model_fields WHERE model = 'clara.card' AND name = 'periodicity')""")
