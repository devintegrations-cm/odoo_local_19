from . import controllers
from . import models
from . import wizards

# Stored fields the module adds to transfers and moves, with the value every record has when it is NOT a plant request.
# The columns are created here, before Odoo's own installation, filled with SQL; otherwise Odoo marks every existing
# transfer and move to be computed one by one, which on a production-size database takes minutes and gigabytes of
# memory (the installation ends killed, with no error). Same types as the ORM would create, so nothing is altered later.
_PICKING_COLUMNS = (
    ("plant_request", "boolean", "false"),
    ("plant_warehouse_id", "integer", None),
    ("plant_store_id", "integer", None),
    ("plant_channel_id", "integer", None),
    ("plant_channel", "varchar", None),
    ("plant_counterparty", "varchar", None),
    ("plant_stage", "varchar", None),
    ("plant_stage_manual_progress", "varchar", None),
    ("plant_requested_by", "varchar", None),
    ("plant_briefing", "text", None),
    ("plant_briefing_state", "varchar", "'none'"),
    ("plant_briefing_date", "timestamp without time zone", None),
)
_MOVE_COLUMNS = (
    ("plant_request", "boolean", "false"),
    ("plant_warehouse_id", "integer", None),
    ("plant_channel_id", "integer", None),
    ("plant_channel", "varchar", None),
    ("plant_counterparty", "varchar", None),
    ("plant_stage", "varchar", None),
    ("plant_kind_id", "integer", None),
    ("plant_coffee_line", "varchar", None),
    ("plant_size", "varchar", None),
    ("plant_grind", "varchar", None),
    ("plant_kg", "numeric", "0.000"),
    ("plant_bags", "numeric", "0"),
)
_PICKING_COMPUTED = ("plant_request", "plant_warehouse_id", "plant_store_id", "plant_channel_id", "plant_channel", "plant_counterparty", "plant_stage", "plant_stage_manual_progress", "plant_requested_by")
_MOVE_COMPUTED = ("plant_request", "plant_warehouse_id", "plant_channel_id", "plant_channel", "plant_counterparty", "plant_stage", "plant_kind_id", "plant_coffee_line", "plant_size", "plant_grind", "plant_kg", "plant_bags")
_BATCH = 1000


def _add_columns(cr, table, columns):
    for name, sql_type, default in columns:
        if default is None:
            cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS "%s" %s' % (table, name, sql_type))
        else:
            # a constant default is recorded in the catalogue without rewriting the table; dropping the default afterwards
            # keeps the value of the existing rows and leaves the column as the ORM would have created it
            cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS "%s" %s DEFAULT %s' % (table, name, sql_type, default))
            cr.execute('ALTER TABLE %s ALTER COLUMN "%s" DROP DEFAULT' % (table, name))


def pre_init_hook(env):
    _add_columns(env.cr, "stock_picking", _PICKING_COLUMNS)
    _add_columns(env.cr, "stock_move", _MOVE_COLUMNS)


def _compute_plant_records(env):
    """Only a transfer that leaves a plant warehouse can be a plant request: compute those, and their moves, with the
    normal rules, in small batches. Everything else already has its final value from the pre-install step."""
    Picking, Move = env["stock.picking"], env["stock.move"]
    plants = Picking._plant_warehouses()
    if not plants:
        return
    env.cr.execute("SELECT p.id FROM stock_picking p JOIN stock_location l ON l.id = p.location_id WHERE l.warehouse_id IN %s ORDER BY p.id", (tuple(plants.ids),))
    ids = [row[0] for row in env.cr.fetchall()]
    for start in range(0, len(ids), _BATCH):
        picks = Picking.browse(ids[start:start + _BATCH])
        moves = Move.search([("picking_id", "in", picks.ids)])
        for name in _PICKING_COMPUTED:
            env.add_to_compute(Picking._fields[name], picks)
        for name in _MOVE_COMPUTED:
            env.add_to_compute(Move._fields[name], moves)
        env.flush_all()
        env.invalidate_all()


def post_init_hook(env):
    """Compute what leaves the plant, link the seeded rows and columns of the workbook to this database, take the
    coffee lines and the product fields from those rows, and classify every other product from its name."""
    _compute_plant_records(env)
    env["plant.sheet.row"].search([]).action_link_products()
    env["plant.sheet.column"].search([]).action_link_warehouses()
    env["plant.sheet.row"]._plant_bootstrap_from_rows()
    Template = env["product.template"].with_context(active_test=False, plant_skip_reclassify=True)
    Template.search([("plant_kind_id", "=", False)])._plant_apply_guess()
    env["stock.move"]._plant_reclassify_open()
