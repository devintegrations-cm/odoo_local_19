def migrate(cr, version):
    """Carry the kind of every line over to the plant.kind records seeded by this version, then drop the old column."""
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'stock_move' AND column_name = 'plant_kind'")
    if cr.fetchone():   # production dropped this column in 17.0.1.3.0, with the kinds already carried over: nothing to copy there
        cr.execute("UPDATE stock_move m SET plant_kind_id = k.id FROM plant_kind k WHERE m.plant_kind = k.code AND m.plant_kind_id IS NULL")
    cr.execute('ALTER TABLE stock_move DROP COLUMN IF EXISTS "plant_kind"')
    cr.execute('ALTER TABLE plant_production_plan DROP COLUMN IF EXISTS "plant_kind"')
