def migrate(cr, version):
    """1.5.0: the CAFE tab is gone and the rows of the sheet come from the products.

    The seeded rows of the CAFE tab (green and roasted coffee blocks) are removed with their xml ids, and the
    selection values of the dropped tab and blocks are dropped before the registry loads, so Odoo does not try to
    apply an ondelete policy on them."""
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'plant_sheet_row'")
    if not cr.fetchone():   # a database still at 1.0.0 has no rows yet: nothing to clean, the data files load without the CAFE rows
        return
    cr.execute("DELETE FROM ir_model_data WHERE module = 'plant_request_board' AND model = 'plant.sheet.row' AND res_id IN (SELECT id FROM plant_sheet_row WHERE sheet = 'cafe')")
    cr.execute("DELETE FROM plant_sheet_row_product_rel WHERE row_id IN (SELECT id FROM plant_sheet_row WHERE sheet = 'cafe')")
    cr.execute("UPDATE plant_sheet_row SET parent_id = NULL WHERE parent_id IN (SELECT id FROM plant_sheet_row WHERE sheet = 'cafe')")
    cr.execute("DELETE FROM plant_sheet_row WHERE sheet = 'cafe'")
    cr.execute("DELETE FROM ir_model_data WHERE module = 'plant_request_board' AND model = 'plant.sheet.column' AND res_id IN (SELECT id FROM plant_sheet_column WHERE sheet = 'cafe')")
    cr.execute("DELETE FROM plant_sheet_column WHERE sheet = 'cafe'")
    for model, field, values in (("plant.sheet.row", "sheet", ("cafe",)), ("plant.sheet.column", "sheet", ("cafe",)), ("plant.sheet.row", "block", ("verde", "tostado"))):
        cr.execute("""DELETE FROM ir_model_data d USING ir_model_fields_selection s, ir_model_fields f
                      WHERE d.model = 'ir.model.fields.selection' AND d.res_id = s.id AND s.field_id = f.id
                        AND f.model = %s AND f.name = %s AND s.value IN %s""", (model, field, values))
        cr.execute("""DELETE FROM ir_model_fields_selection s USING ir_model_fields f
                      WHERE s.field_id = f.id AND f.model = %s AND f.name = %s AND s.value IN %s""", (model, field, values))
