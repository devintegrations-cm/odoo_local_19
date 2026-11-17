from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Databases that already had the module: link the new workbook rows and columns once."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["plant.sheet.row"].search([]).action_link_products()
    env["plant.sheet.column"].search([]).action_link_warehouses()
