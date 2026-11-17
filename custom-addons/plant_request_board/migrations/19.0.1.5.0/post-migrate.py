import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """The rows of the sheet become automatic (line × grams × grind from the plant fields of the products):

    1. the coffee lines (name, order, colour) and the plant fields of every product a legacy row listed are taken
       from those rows; the plain rows become inert (exception = False) and the kits keep working;
    2. every other product is classified from its name, exactly as the board read it live until 1.4.0, and left
       as automatic (Planta › Clasificar productos shows the proposal and lets the plant review it);
    3. the open order lines are read again from the fields."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    rows = env["plant.sheet.row"]._plant_bootstrap_from_rows()
    Template = env["product.template"].with_context(active_test=False, plant_skip_reclassify=True)
    pending = Template.search([("plant_kind_id", "=", False)])
    pending._plant_apply_guess()
    env["stock.move"]._plant_reclassify_open()
    lines = env["plant.coffee.line"].search([])
    _logger.info("plant_request_board 1.5.0: %s coffee lines (%s), %s products classified from the rows, %s from their names, %s kit rows kept",
                 len(lines), ", ".join(lines.mapped("name")), Template.search_count([("plant_manual", "=", True)]), len(pending),
                 len(rows.filtered(lambda r: r.parent_id or r.child_ids)))
