def migrate(cr, version):
    """Plants, channels and stores become records (1.4.0). The new columns of the transfers and their lines are
    created here, by SQL, so that Odoo finds them and does not mark every row of the database for computation
    (minutes and gigabytes on a production-size table); the post-migration fills them.

    plant_channel changes from a Selection to the Char code of the channel: its selection values (and their
    xml ids) are dropped so the registry does not try to keep them on a Char field."""
    for table in ("stock_picking", "stock_move"):
        cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS "plant_channel_id" integer' % table)
        cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS "plant_warehouse_id" integer' % table)
    # the stage every open request has today (state-driven) is kept aside: the reclassification of this version
    # recomputes it with the rules of the current code, and 1.7.0 restores it when it creates the first ticks
    cr.execute('ALTER TABLE stock_picking ADD COLUMN IF NOT EXISTS "plant_stage_legacy" varchar')
    cr.execute("UPDATE stock_picking SET plant_stage_legacy = plant_stage WHERE plant_request AND state NOT IN ('done', 'cancel') AND plant_stage_legacy IS NULL AND plant_stage IS NOT NULL")
    cr.execute("""DELETE FROM ir_model_data d USING ir_model_fields_selection s, ir_model_fields f
                  WHERE d.model = 'ir.model.fields.selection' AND d.res_id = s.id AND s.field_id = f.id
                    AND f.model IN ('stock.picking', 'stock.move') AND f.name = 'plant_channel'""")
    cr.execute("""DELETE FROM ir_model_fields_selection s USING ir_model_fields f
                  WHERE s.field_id = f.id AND f.model IN ('stock.picking', 'stock.move') AND f.name = 'plant_channel'""")
    cr.execute("UPDATE ir_model_fields SET ttype = 'char' WHERE model IN ('stock.picking', 'stock.move') AND name = 'plant_channel'")
