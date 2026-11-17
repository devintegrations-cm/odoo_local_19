import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """1.7.0: the open stages follow the preparation ticks instead of the reservation state of the transfer.
    Every open request keeps the stage it had: its ticks are created from its lines and, for Lista para
    despachar, created done; En alistamiento and Nueva hold their stage until a tick changes. Delivered and
    cancelled requests are untouched."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT id, plant_stage_legacy FROM stock_picking WHERE plant_stage_legacy IS NOT NULL")
    legacy = dict(cr.fetchall())
    open_requests = env["stock.picking"].search([("plant_request", "=", True), ("state", "not in", ("done", "cancel"))])
    open_requests._plant_init_checks_keeping_stage(legacy)
    cr.execute('ALTER TABLE stock_picking DROP COLUMN IF EXISTS "plant_stage_legacy"')
    stages = {}
    for pick in open_requests:
        stages[pick.plant_stage] = stages.get(pick.plant_stage, 0) + 1
    _logger.info("plant_request_board 1.7.0: %s open requests kept their stage (%s), %s ticks created", len(open_requests), stages, env["plant.request.check"].search_count([]))
