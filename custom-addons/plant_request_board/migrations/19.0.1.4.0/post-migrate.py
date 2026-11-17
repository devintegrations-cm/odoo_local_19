import logging
import re

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# The text settings of 1.3.0, with the defaults they had, moved once to the channel records seeded by 1.4.0:
# setting key → (channel code, rule field, model, field searched, exact or contains, default of 1.3.0)
LEGACY_RULES = {
    "plant_request_board.event_warehouse_codes": ("eventos", "warehouse_ids", "stock.warehouse", "code", "exact", "EVENT,EVE25,EVEME"),
    "plant_request_board.b2b_warehouse_codes": ("alianzas", "warehouse_ids", "stock.warehouse", "code", "exact", "COMER"),
    "plant_request_board.ecommerce_pricelists": ("ecommerce", "pricelist_ids", "product.pricelist", "name", "contains", "Pagina_Web"),
    "plant_request_board.attenza_pricelists": ("attenza", "pricelist_ids", "product.pricelist", "name", "contains", "Attenza"),
    "plant_request_board.ecommerce_partners": ("ecommerce", "partner_ids", "res.partner", "name", "contains", "ECOMMERCE SHOPIFY"),
    "plant_request_board.b2b_teams": ("alianzas", "team_ids", "crm.team", "name", "exact", "Comercial"),
    "plant_request_board.event_teams": ("eventos", "team_ids", "crm.team", "name", "contains", "EVENTO"),
    "plant_request_board.b2b_partner_tags": ("alianzas", "partner_tag_ids", "res.partner.category", "name", "exact", "Alianzas,Restaurantes,Hotel,Corporativo"),
}
LEGACY_SHEET = ("plant_request_board.sheet_channels", "tiendas=tiendas,eventos; otros=ecommerce,alianzas,otros; attenza=attenza")
LEGACY_PLANT = ("plant_request_board.plant_warehouse_code", "PLANT")


def _records(env, model, field, mode, raw):
    Model = env[model].sudo().with_context(active_test=False)
    found = Model
    for item in [x.strip() for x in (raw or "").split(",") if x.strip()]:
        found |= Model.search([(field, "=ilike" if mode == "exact" else "ilike", item)])
    return found


def _param(icp, key, default):
    value = icp.get_param(key)
    return default if value is False else value


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env["ir.config_parameter"].sudo()
    Channel = env["plant.channel"].with_context(plant_skip_reclassify=True)

    def channel(code):
        return Channel.search([("code", "=", code)], limit=1)

    # 1. the plant named by the old setting becomes a flagged warehouse
    cr.execute("UPDATE stock_warehouse SET plant_is_plant = true WHERE upper(code) = upper(%s)", (_param(icp, *LEGACY_PLANT).strip(),))
    # 2. channel and plant of every existing request, by SQL (nothing is recomputed)
    cr.execute("UPDATE stock_picking p SET plant_channel_id = c.id FROM plant_channel c WHERE p.plant_request AND p.plant_channel = c.code AND p.plant_channel_id IS NULL")
    cr.execute("UPDATE stock_picking p SET plant_warehouse_id = l.warehouse_id FROM stock_location l WHERE p.plant_request AND l.id = p.location_id AND p.plant_warehouse_id IS NULL")
    cr.execute("UPDATE stock_move m SET plant_channel_id = p.plant_channel_id, plant_warehouse_id = p.plant_warehouse_id FROM stock_picking p WHERE m.picking_id = p.id AND p.plant_request")
    # 3. the rules the text settings named, as records on the channels
    for key, (code, field, model, name_field, mode, default) in LEGACY_RULES.items():
        ch = channel(code)
        if not ch:
            continue
        found = _records(env, model, name_field, mode, _param(icp, key, default))
        if model == "res.partner":
            found = found.commercial_partner_id
        if found:
            ch.write({field: [(4, rec.id) for rec in found]})
        _logger.info("plant_request_board 1.4.0: channel %s ← %s %s from %s", code, len(found), field, key)
    # 4. the tab of the sheet each channel feeds, from the old setting
    for item in re.split(r"[;\n]", _param(icp, *LEGACY_SHEET)):
        tab, sep, codes = item.partition("=")
        tab = tab.strip().lower()
        if sep and tab in ("tiendas", "otros", "attenza"):
            for code in codes.split(","):
                ch = channel(code.strip().lower())
                if ch:
                    ch.sheet = tab
    # 5. the stores: destinations of store requests and warehouses of the PEDIDOS TIENDAS columns, unless a channel
    #    claims them (event and B2B warehouses) or they are plants
    cr.execute("""UPDATE stock_warehouse w SET plant_is_store = true
                  WHERE w.id IN (SELECT p.plant_store_id FROM stock_picking p WHERE p.plant_request AND p.plant_channel = 'tiendas' AND p.plant_store_id IS NOT NULL
                                 UNION SELECT r.warehouse_id FROM plant_sheet_column_warehouse_rel r JOIN plant_sheet_column c ON c.id = r.column_id WHERE c.sheet = 'tiendas')
                    AND w.id NOT IN (SELECT warehouse_id FROM plant_channel_warehouse_rel)
                    AND NOT COALESCE(w.plant_is_plant, false)""")
    # 6. the open requests take their channel again with the rules as records (done ones keep what they were)
    env["stock.picking"]._plant_reclassify_open()
