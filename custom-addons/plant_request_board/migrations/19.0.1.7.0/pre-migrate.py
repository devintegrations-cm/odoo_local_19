def migrate(cr, version):
    """1.7.0 adds a stored computed column to the transfers (plant_stage_manual_progress). It is created here, by
    SQL and empty, so that Odoo finds it and does not mark every transfer of the database for computation."""
    cr.execute('ALTER TABLE stock_picking ADD COLUMN IF NOT EXISTS "plant_stage_manual_progress" varchar')
    # the stage every open request has today is kept aside (unless 1.4.0 already did it in this run) and restored by
    # the post-migration once the ticks exist
    cr.execute('ALTER TABLE stock_picking ADD COLUMN IF NOT EXISTS "plant_stage_legacy" varchar')
    cr.execute("UPDATE stock_picking SET plant_stage_legacy = plant_stage WHERE plant_request AND state NOT IN ('done', 'cancel') AND plant_stage_legacy IS NULL AND plant_stage IS NOT NULL")
