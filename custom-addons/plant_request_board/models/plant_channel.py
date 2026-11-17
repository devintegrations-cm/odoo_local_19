from odoo import api, fields, models

# The tabs of the plant's workbook a channel can feed (structure: each tab has its own columns and blocks).
SHEET_TABS = [("tiendas", "PEDIDOS TIENDAS"), ("otros", "OTROS PEDIDOS"), ("attenza", "ATTENZA"), ("none", "No suma en la hoja")]
FALLBACKS = [("none", "Solo por reglas"), ("internal", "Transferencias a otro almacén sin regla"), ("outgoing", "Entregas a clientes sin regla")]
# the rule fields: a change in any of them classifies the open requests again
RULE_FIELDS = ("warehouse_ids", "pricelist_ids", "team_ids", "partner_tag_ids", "partner_ids", "shopify", "sequence", "fallback", "active")


class PlantChannel(models.Model):
    """A channel of the plant board (Tiendas, Eventos, E-commerce, Attenza, Alianzas, Otros…) and the records that
    put a request in it. Rules are relations, never text: a renamed pricelist or partner keeps its channel.

    A request takes the first channel, in order of sequence, with a rule that matches it: its destination warehouse,
    the pricelist or the sales team of its sale order, a tag of its customer, its customer (or the company the
    customer belongs to), or the Shopify flag of the sale. Without a match it takes the channel marked as fallback
    for its kind of transfer (to another warehouse, or to a customer)."""

    _name = "plant.channel"
    _description = "Canal de la planta"
    _order = "sequence, id"

    name = fields.Char(string="Canal", required=True)
    code = fields.Char(string="Código", required=True, help="Clave técnica del canal, sin espacios (tiendas, eventos, ecommerce…). Es lo que guardan las solicitudes y lo que usan los filtros guardados.")
    sequence = fields.Integer(default=10, help="Orden de evaluación: la solicitud toma el primer canal cuyas reglas la reconocen.")
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color")
    sheet = fields.Selection(SHEET_TABS, string="Pestaña de la hoja", required=True, default="otros", help="Pestaña de la hoja de la planta donde suman las solicitudes de este canal.")
    fallback = fields.Selection(FALLBACKS, string="Canal por defecto", required=True, default="none", help="Qué solicitudes toman este canal cuando ninguna regla de ningún canal las reconoce.")
    warehouse_ids = fields.Many2many("stock.warehouse", "plant_channel_warehouse_rel", "channel_id", "warehouse_id", string="Almacenes destino", context={"active_test": False}, help="Transferencias de la planta hacia estos almacenes.")
    pricelist_ids = fields.Many2many("product.pricelist", "plant_channel_pricelist_rel", "channel_id", "pricelist_id", string="Listas de precios", context={"active_test": False}, help="Entregas de ventas con estas listas de precios.")
    team_ids = fields.Many2many("crm.team", "plant_channel_team_rel", "channel_id", "team_id", string="Equipos de venta", context={"active_test": False}, help="Entregas de ventas de estos equipos.")
    partner_tag_ids = fields.Many2many("res.partner.category", "plant_channel_partner_tag_rel", "channel_id", "category_id", string="Etiquetas de cliente", help="Entregas a clientes con alguna de estas etiquetas (propias o de su empresa).")
    partner_ids = fields.Many2many("res.partner", "plant_channel_partner_rel", "channel_id", "partner_id", string="Clientes", context={"active_test": False}, help="Entregas a estos clientes, a sus contactos y a las sucursales de su empresa (se compara el registro, no el nombre).")
    shopify = fields.Boolean(string="Pedidos de Shopify", help="Entregas de ventas marcadas por la integración de Shopify (campo is_shopify_order), si está instalada.")
    rule_summary = fields.Char(string="Reglas", compute="_compute_rule_summary")

    _code_uniq = models.Constraint("unique(code)", "Ya existe un canal con ese código.")

    @api.depends(*RULE_FIELDS)
    def _compute_rule_summary(self):
        labels = dict(FALLBACKS)
        for channel in self:
            parts = []
            for field, label in (("warehouse_ids", "almacenes"), ("pricelist_ids", "listas"), ("team_ids", "equipos"), ("partner_tag_ids", "etiquetas"), ("partner_ids", "clientes")):
                if channel[field]:
                    parts.append("%s %s" % (len(channel[field]), label))
            if channel.shopify:
                parts.append("Shopify")
            if channel.fallback != "none":
                parts.append(labels[channel.fallback].lower())
            channel.rule_summary = ", ".join(parts) or "—"

    @api.model
    def _plant_rules(self):
        """The active channels in order with their rule sets as ids, and the fallback channel of each kind of
        transfer. Loaded once per batch of requests."""
        rules, fallback = [], {}
        for channel in self.search([]):
            rules.append({
                "channel": channel,
                "warehouses": set(channel.warehouse_ids.ids), "pricelists": set(channel.pricelist_ids.ids), "teams": set(channel.team_ids.ids),
                "tags": set(channel.partner_tag_ids.ids), "partners": set(channel.partner_ids.ids), "shopify": channel.shopify,
            })
            if channel.fallback != "none" and channel.fallback not in fallback:
                fallback[channel.fallback] = channel
        return {"channels": rules, "fallback": fallback}

    @api.model
    def _plant_partner_ids(self, partner):
        """The partner, its parents up to the root and the company it belongs to: any of them in a channel's
        customers puts the request in that channel."""
        ids = set()
        current = partner
        while current and current.id not in ids:
            ids.add(current.id)
            current = current.parent_id
        if partner and partner.commercial_partner_id:
            ids.add(partner.commercial_partner_id.id)
        return ids

    @api.model_create_multi
    def create(self, vals_list):
        channels = super().create(vals_list)
        if not self.env.context.get("plant_skip_reclassify"):
            self.env["stock.picking"]._plant_reclassify_open()
        return channels

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & set(RULE_FIELDS) and not self.env.context.get("plant_skip_reclassify"):
            self.env["stock.picking"]._plant_reclassify_open()
        return res
