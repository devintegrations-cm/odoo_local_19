import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# words the plant asked for after reviewing production: packaging rolls, "empaque", infusions and paper are supplies
SUPPLY_WORDS = ("ROLLO", "EMPAQUE", "INFUSION", "PAPEL")


def migrate(cr, version):
    """1.6.0: a fifth kind (green coffee, seeded by the data file), new supply words, the automatic products
    classified again with both, and no AI queue without an Anthropic key."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    supply = env.ref("plant_request_board.kind_supply", raise_if_not_found=False)
    if supply:
        words = supply._words(supply.keywords)
        missing = [w for w in SUPPLY_WORDS if w not in words]
        if missing:
            supply.keywords = ",".join([w for w in (supply.keywords or "").split(",") if w.strip()] + missing)   # write() classifies the automatic products again
        else:
            env["product.template"]._plant_reclassify_auto()
    else:
        env["product.template"]._plant_reclassify_auto()
    if not env["stock.picking"]._plant_ai_enabled():
        cr.execute("UPDATE stock_picking SET plant_briefing_state = 'none' WHERE plant_briefing_state = 'pending'")
    green = env.ref("plant_request_board.kind_green", raise_if_not_found=False)
    _logger.info("plant_request_board 1.6.0: %s products of kind green coffee, AI briefing %s",
                 env["product.template"].with_context(active_test=False).search_count([("plant_kind_id", "=", green.id)]) if green else 0,
                 "enabled" if env["stock.picking"]._plant_ai_enabled() else "disabled (no key)")
