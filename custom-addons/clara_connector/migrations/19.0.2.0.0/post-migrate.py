import json
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

# the connector's groups of earlier versions -> the groups of clara_purchase_bridge
GROUP_MOVES = (
    ("clara_connector.group_clara_user", "clara_purchase_bridge.group_clara_reader"),
    ("clara_connector.group_clara_manager", "clara_purchase_bridge.group_clara_admin"),
)
OLD_SYNC_DATE = "clara_connector.clara_sync_from_date"   # the old flow advanced it on every sync: the date of the last one
NEW_LAST_SYNC = "clara_connector.last_sync_date"
REMOVED_PARAMS = (
    "clara_connector.auto_create_orders", "clara_connector.pilot_cardholders", "clara_connector.write_labels",
    "clara_connector.receipts_per_run", "clara_connector.orders_from_date", "clara_connector.schedule_mode",
    "clara_connector.weekly_max_batches", "clara_connector.allow_card_lock", "clara_connector.sync_lookback_days",
    "clara_connector.anthropic_api_key", "clara_connector.anthropic_workspace_id", "clara_connector.anthropic_model",
    "clara_connector.clara_sync_interval_hours", "clara_connector.clara_auto_create_expenses", "clara_connector.clara_auto_post_moves",
    "clara_connector.clara_journal_id", "clara_connector.clara_liability_account_id", "clara_connector.clara_default_expense_account_id",
    "clara_connector.clara_default_product_id", "clara_connector.clara_default_employee_id", OLD_SYNC_DATE,
)


def migrate(cr, version):
    """Groups, parameters and the data already in the database. No transaction or card is deleted: each one is
    rewritten from the payload it already holds, without the card number and without identity documents, so the
    dashboard fields (type, status, limit, comment, legalization, order link, reconciliation) are filled at once."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _move_groups(env)
    _parameters(env)
    _cards(env)
    _transactions(env)


def _move_groups(env):
    for old_xmlid, new_xmlid in GROUP_MOVES:
        old = env.ref(old_xmlid, raise_if_not_found=False)
        new = env.ref(new_xmlid, raise_if_not_found=False)
        if old and new and old != new:
            users_field = "user_ids" if "user_ids" in new._fields else "users"   # renamed in Odoo 19
            new.write({users_field: [(4, user.id) for user in old[users_field]]})
            _logger.info("Clara: %s user(s) moved from %s to %s", len(old[users_field]), old_xmlid, new_xmlid)
            # the access rules of earlier versions still point at the old group (Odoo only drops them at the end of the update)
            env["ir.model.access"].search([("group_id", "=", old.id)]).unlink()
            old.unlink()
    category = env.ref("clara_connector.module_category_clara", raise_if_not_found=False)
    if category:
        category.unlink()


def _parameters(env):
    icp = env["ir.config_parameter"]
    last = icp.get_param(OLD_SYNC_DATE)
    if last and not icp.get_param(NEW_LAST_SYNC):
        icp.set_param(NEW_LAST_SYNC, str(last)[:10])   # the next run asks Clara for what changed since the last old sync
    icp.search([("key", "in", REMOVED_PARAMS)]).unlink()


def _cards(env):
    """Cards of earlier versions kept the whole Clara payload (with the masked card number): their new fields are
    mapped from it before Odoo drops that column at the end of the update."""
    if not column_exists(env.cr, "clara_card", "raw_payload"):
        return
    Card = env["clara.card"]
    env.cr.execute("SELECT id, raw_payload FROM clara_card WHERE raw_payload IS NOT NULL")
    remapped = 0
    for card_id, raw in env.cr.fetchall():
        try:
            payload = json.loads(raw) or {}
        except ValueError:
            continue
        vals = Card._vals_from_payload(payload)
        vals.pop("clara_uuid", None)
        Card.browse(card_id).write(vals)
        remapped += 1
    env.cr.execute("UPDATE clara_card SET raw_payload = NULL")
    _logger.info("Clara: %s card(s) remapped from their payload", remapped)


def _transactions(env):
    """Every transaction is rewritten from its own payload: the card number leaves the stored payload, the comment
    keeps its full text and every computed field (type, legalization, order link, reconciliation) is refreshed."""
    Transaction = env["clara.transaction"]
    rewritten = 0
    for tx in Transaction.search([]):
        try:
            payload = json.loads(tx.raw_payload or "{}") or {}
        except ValueError:
            continue
        if not payload:
            continue
        vals = Transaction._vals_from_payload(payload)
        vals.pop("clara_uuid", None)
        tx.write(vals)
        rewritten += 1
    env.add_to_compute(Transaction._fields["name"], Transaction.search([]))
    env.flush_all()
    _logger.info("Clara: %s transaction(s) rewritten from their payload", rewritten)
