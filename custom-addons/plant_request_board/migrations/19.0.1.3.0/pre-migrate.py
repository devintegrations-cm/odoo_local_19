def migrate(cr, version):
    """plant_kind on the order lines becomes a Many2one to plant.kind. The column is created here, by SQL, so that
    Odoo finds it and does not mark every move of the database for computation (minutes and gigabytes on a
    production-size table); the post-migration fills it from the old column."""
    cr.execute('ALTER TABLE stock_move ADD COLUMN IF NOT EXISTS "plant_kind_id" integer')
