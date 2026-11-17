from odoo import SUPERUSER_ID, api

# The seeded rows are noupdate: bring existing databases to the workbook's colour convention once.
ROW_COLORS = {
    "row_t_omb_200": "#FFC000", "row_t_omb_340": "#FFC000", "row_t_omb_454": "#FFC000", "row_t_omb_prep": "#FFC000",
    "row_o_impacto_340": "#FFC000", "row_o_impacto_227": "#FFC000",
}
COLUMN_COLORS = {"col_tiendas_laureles": "#1C4587", "col_tiendas_spc": "#1C4587", "col_tiendas_sura": "#0B5394"}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, color in ROW_COLORS.items():
        row = env.ref("plant_request_board.%s" % xmlid, raise_if_not_found=False)
        if row and (row.color or "").upper() in ("", "#FFFFFF"):   # keep a colour the plant already changed
            row.color = color
    paz = env.ref("plant_request_board.row_o_lavado_30", raise_if_not_found=False)
    if paz and not paz.net_color:
        paz.net_color = "#B6D7A8"
    for xmlid, color in COLUMN_COLORS.items():
        col = env.ref("plant_request_board.%s" % xmlid, raise_if_not_found=False)
        if col and (col.header_color or "#2F5496").upper() == "#2F5496":
            col.header_color = color
