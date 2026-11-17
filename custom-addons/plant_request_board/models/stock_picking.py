import json
import logging
import os
import re
from datetime import timedelta
from functools import partial

import requests
from markupsafe import Markup, escape

import odoo
from odoo import _, api, fields, models
from odoo.modules.registry import Registry
from odoo.tools import float_compare, float_is_zero, html2plaintext
from odoo.tools.image import image_data_uri
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Only structure lives here: how a weight is read from a name and the stages. Everything the plant reads, or that
# is matched against the database, is configuration: the plants and stores (flags on stock.warehouse), the channels
# and their rules (plant.channel), the kinds of line (plant.kind) and the Planta settings (read through _plant_get).
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
BATCH = 1000

PLANT_STAGES = [
    ("new", "Nueva"),
    ("preparing", "En alistamiento"),
    ("ready", "Lista para despachar"),
    ("delivered", "Entregada"),
    ("cancelled", "Cancelada"),
]
# the open stages follow the preparation ticks (none / some / all); delivered and cancelled follow the transfer
OPEN_STAGE_ORDER = {"new": 0, "preparing": 1, "ready": 2}
OPEN_STAGES = tuple(OPEN_STAGE_ORDER)
PENDING_STAGES = ("new", "preparing")   # what the plant still has to prepare: the active sheet and the roasting plan

BRIEFING_STATES = [("none", "Sin análisis"), ("pending", "Pendiente"), ("done", "Listo"), ("error", "Error")]


class StockPicking(models.Model):
    """A request to the plant is a transfer that leaves a plant warehouse: to a store (internal) or to a customer."""

    _inherit = "stock.picking"

    plant_request = fields.Boolean(string="Solicitud a planta", compute="_compute_plant_request", store=True, index=True)
    plant_warehouse_id = fields.Many2one("stock.warehouse", string="Planta", compute="_compute_plant_request", store=True, index=True, help="Planta de la que sale la solicitud.")
    plant_store_id = fields.Many2one("stock.warehouse", string="Tienda", compute="_compute_plant_request", store=True, index=True, help="Almacén que recibe la transferencia.")
    plant_channel_id = fields.Many2one("plant.channel", string="Canal", compute="_compute_plant_request", store=True, index=True, ondelete="restrict")
    plant_channel = fields.Char(string="Código del canal", compute="_compute_plant_request", store=True, index=True)
    plant_counterparty = fields.Char(string="Tienda / cliente", compute="_compute_plant_request", store=True, index=True)
    plant_stage = fields.Selection(PLANT_STAGES, string="Etapa en planta", compute="_compute_plant_stage", store=True, readonly=False, index=True, help="Nueva, En alistamiento (primer chuleo) y Lista para despachar (todos los chuleos) siguen los chuleos; se pueden fijar a mano hasta que los chuleos cambien. Entregada y Cancelada siguen la transferencia.")
    plant_stage_manual_progress = fields.Char(compute="_compute_plant_stage", store=True, readonly=False, help="Avance de los chuleos cuando la etapa se fijó a mano; la etapa manual vale mientras ese avance no cambie.")
    plant_check_ids = fields.One2many("plant.request.check", "picking_id", string="Chuleos de alistamiento")
    plant_check_count = fields.Integer(string="Líneas por alistar", compute="_compute_plant_progress")
    plant_check_done = fields.Integer(string="Líneas alistadas", compute="_compute_plant_progress")
    plant_progress = fields.Float(string="Avance", compute="_compute_plant_progress", digits=(5, 0), help="Porcentaje de líneas chuleadas.")
    plant_requested_by = fields.Char(string="Solicitada por", compute="_compute_plant_request", store=True)
    plant_days_waiting = fields.Float(string="Días esperando", compute="_compute_plant_days", digits=(6, 1))
    plant_line_count = fields.Integer(string="Líneas", compute="_compute_plant_totals")
    plant_coffee_kg = fields.Float(string="Café (kg)", compute="_compute_plant_totals", digits=(10, 2))
    plant_pack_units = fields.Float(string="Otras unidades", compute="_compute_plant_totals", digits=(10, 0))
    plant_briefing = fields.Html(string="Análisis para planta", copy=False, readonly=True, sanitize=True)
    plant_briefing_state = fields.Selection(BRIEFING_STATES, string="Estado del análisis", default="none", copy=False, readonly=True)
    plant_briefing_date = fields.Datetime(string="Analizada", copy=False, readonly=True)
    plant_store_comment = fields.Text(string="Comentario de la tienda", compute="_compute_plant_store_comment")
    plant_green_alert_html = fields.Html(string="Café verde", compute="_compute_plant_green_alert", sanitize=False, help="Por línea de café, el café verde que esta solicitud necesita y el que queda después de ella, contando las solicitudes anteriores por fecha.")
    plant_green_status = fields.Selection([("green", "Alcanza"), ("yellow", "Por debajo del mínimo"), ("red", "Falta café verde")], string="Alerta de café verde", compute="_compute_plant_green_alert")
    plant_card_html = fields.Html(string="Detalle del pedido", compute="_compute_plant_card", sanitize=False)

    # --- what is a request ---------------------------------------------------------
    @api.model
    def _plant_warehouses(self):
        """The plants: every warehouse flagged in Inventario › Ajustes › Planta (or on the warehouse itself)."""
        return self.env["stock.warehouse"].sudo().search([("plant_is_plant", "=", True)])

    @api.model
    def _plant_channel_rules(self):
        return self.env["plant.channel"].sudo()._plant_rules()

    def _plant_classify(self, plants, rules):
        """(plant, channel, counterparty, destination warehouse) of one transfer; the plant is empty when the
        transfer is not a request. Read from the locations, never from the operation type: whatever leaves a
        location of a plant towards another warehouse (a store's own internal transfer or receipt included) or
        towards a customer is a request. Deterministic: the records of the transfer against the records of the
        rules."""
        self.ensure_one()
        Warehouse, Channel = self.env["stock.warehouse"], self.env["plant.channel"]
        src_wh = self.location_id.warehouse_id
        if not src_wh or src_wh not in plants:
            return Warehouse, Channel, False, Warehouse
        dst = self.location_dest_id
        dst_wh = dst.warehouse_id
        if dst_wh and dst_wh != src_wh:
            kind = "internal"
        elif dst.usage == "customer":
            kind = "outgoing"
        else:
            return Warehouse, Channel, False, Warehouse
        sale = self.sale_id if "sale_id" in self._fields else False
        partner = self.partner_id
        partner_ids = Channel._plant_partner_ids(partner)
        tag_ids = set(partner.category_id.ids) | set(partner.commercial_partner_id.category_id.ids)
        pricelist_id = sale.pricelist_id.id if sale else False
        team_id = sale.team_id.id if sale else False
        shopify = bool(sale and "is_shopify_order" in sale._fields and sale.is_shopify_order)
        for rule in rules["channels"]:
            if ((dst_wh and dst_wh.id in rule["warehouses"]) or (pricelist_id and pricelist_id in rule["pricelists"]) or (team_id and team_id in rule["teams"])
                    or (tag_ids & rule["tags"]) or (partner_ids & rule["partners"]) or (shopify and rule["shopify"])):
                channel = rule["channel"]
                break
        else:
            channel = rules["fallback"].get(kind, Channel)
        if kind == "internal":
            return src_wh, channel, dst_wh.name, dst_wh
        commercial = partner.commercial_partner_id or partner
        return src_wh, channel, commercial.name or partner.name or self.name, Warehouse

    @api.depends("location_id", "location_id.warehouse_id", "location_dest_id", "location_dest_id.warehouse_id", "location_dest_id.usage", "create_uid", "partner_id", "sale_id", "sale_id.pricelist_id", "sale_id.team_id")
    def _compute_plant_request(self):
        plants = self._plant_warehouses()
        rules = self._plant_channel_rules()
        for pick in self:
            plant, channel, counterparty, store = pick._plant_classify(plants, rules)
            pick.plant_request = bool(plant)
            pick.plant_warehouse_id = plant
            pick.plant_channel_id = channel
            pick.plant_channel = channel.code or False
            pick.plant_counterparty = counterparty
            pick.plant_store_id = store
            sale = pick.sale_id if "sale_id" in pick._fields else False
            pick.plant_requested_by = ((sale.user_id.name if sale and sale.user_id else "") or pick.create_uid.name or "") if plant else False

    def _plant_mark_stores(self):
        """A warehouse that receives a request without matching any channel rule is a store: it gets its column
        in PEDIDOS TIENDAS at once, with no configuration."""
        stores = self.filtered(lambda p: p.plant_request and p.plant_store_id and p.plant_channel_id.fallback == "internal" and not p.plant_store_id.plant_is_store).mapped("plant_store_id")
        if stores:
            stores.sudo().write({"plant_is_store": True})

    @api.model
    def _plant_recompute(self, domain):
        """Classify the transfers of the domain again, in batches; their lines and everything that depends on the
        result (stage, card, totals, kinds) follow."""
        names = [f.name for f in self._fields.values() if f.compute == "_compute_plant_request"]
        picks = self.sudo().search(domain, order="id")
        for start in range(0, len(picks), BATCH):
            batch = picks[start:start + BATCH]
            for name in names:
                self.env.add_to_compute(self._fields[name], batch)
            batch.modified(names)
            self.env.flush_all()
        picks.filtered("plant_request")._plant_mark_stores()
        picks._plant_sync_checks()

    @api.model
    def _plant_recompute_for_warehouses(self, warehouses):
        """A warehouse became, or stopped being, a plant: every transfer that leaves it is classified again."""
        self._plant_recompute(["|", ("plant_warehouse_id", "in", warehouses.ids), ("location_id.warehouse_id", "in", warehouses.ids)])

    @api.model
    def _plant_reclassify_open(self):
        """The channel rules changed: the open requests take their channel again; delivered and cancelled ones
        keep what they were."""
        plants = self._plant_warehouses()
        if plants:
            self._plant_recompute([("location_id.warehouse_id", "in", plants.ids), ("state", "not in", ("done", "cancel"))])

    def _plant_progress_key(self):
        self.ensure_one()
        checks = self.plant_check_ids
        return "%s/%s" % (len(checks.filtered("done")), len(checks))

    @api.depends("state", "plant_request", "plant_check_ids", "plant_check_ids.done")
    def _compute_plant_stage(self):
        for pick in self:
            if not pick.plant_request:
                pick.plant_stage = False
                pick.plant_stage_manual_progress = False
                continue
            if pick.state in ("done", "cancel"):
                pick.plant_stage = "delivered" if pick.state == "done" else "cancelled"
                pick.plant_stage_manual_progress = False
                continue
            progress = pick._plant_progress_key()
            if pick.plant_stage in OPEN_STAGE_ORDER and pick.plant_stage_manual_progress == progress:
                continue   # fixed by hand and the ticks did not change since: respected
            checks = pick.plant_check_ids
            done = checks.filtered("done")
            pick.plant_stage = "ready" if checks and len(done) == len(checks) else "preparing" if done else "new"
            pick.plant_stage_manual_progress = False

    @api.depends("plant_check_ids.done")
    def _compute_plant_progress(self):
        for pick in self:
            total = len(pick.plant_check_ids)
            done = len(pick.plant_check_ids.filtered("done"))
            pick.plant_check_count = total
            pick.plant_check_done = done
            pick.plant_progress = round(100.0 * done / total) if total else 0.0

    # --- the preparation ticks: one per line × presentation, from the order lines, never touching them ----------
    def _plant_sync_checks(self):
        """Create, rename or drop the ticks so they match the open lines of the request: coffee by the row of
        the sheet (line × grams × grind, bulk as "Preparación"), everything else by master product. Ticks keep
        their state when their lines stay."""
        Check = self.env["plant.request.check"].sudo()
        Sheet = self.env["plant.sheet"]
        settings = Sheet._row_settings()
        line_rules = self._plant_line_rules()
        for pick in self:
            if not pick.plant_request:
                pick.plant_check_ids.sudo().unlink()
                continue
            wanted = {}
            for mv in pick.move_ids.filtered(lambda m: m.state != "cancel"):
                vals = mv.product_id.product_tmpl_id._plant_values(line_rules["parser"])
                key = Sheet._row_key(vals, settings)
                if key:
                    row = Sheet._row_vals(vals, settings)
                    name, sequence = row["name"], row["sequence"]
                else:
                    key = "product:%s" % vals["master"].id
                    name, sequence = self._plant_short_name(vals["master"].name, line_rules), 10 ** 9 + vals["master"].id
                w = wanted.setdefault(key, {"name": name, "sequence": sequence, "kind_code": vals["kind"], "moves": [], "units": 0.0, "grams": 0.0})
                w["moves"].append(mv.id)
                if vals["kind"] == "prepare":
                    w["grams"] += self._plant_grams(mv)
                else:
                    w["units"] += mv.product_uom_qty
            existing = {c.key: c for c in pick.plant_check_ids}
            by_move = {m: c for c in pick.plant_check_ids for m in c.move_ids.ids}
            kept = Check
            for key, w in wanted.items():
                amount = ("%g kg" % (w["grams"] / 1000.0)) if w["kind_code"] == "prepare" else ("%g" % w["units"])
                vals = {"key": key, "name": w["name"], "sequence": w["sequence"], "kind_code": w["kind_code"], "qty_text": amount, "move_ids": [(6, 0, w["moves"])]}
                check = existing.get(key) or next((by_move[m] for m in w["moves"] if m in by_move and by_move[m] not in kept), None)   # a renamed line keeps its tick
                if check:
                    changed = {k: v for k, v in vals.items() if k != "move_ids" and check[k] != v}
                    if set(check.move_ids.ids) != set(w["moves"]):
                        changed["move_ids"] = vals["move_ids"]
                    if changed:
                        check.write(changed)
                    kept |= check
                else:
                    kept |= Check.create(dict(vals, picking_id=pick.id))
            (pick.plant_check_ids - kept).sudo().unlink()
        return True

    def _plant_init_checks_keeping_stage(self, legacy=None):
        """First ticks of requests whose stage predates the ticks (databases before 1.7.0): the stage every
        request had is kept (the snapshot the migrations took, else the current one). Lista para despachar gets
        every tick done; En alistamiento and Nueva keep their stage until a tick changes (the manual hold)."""
        legacy = legacy or {}
        open_requests = self.filtered(lambda p: p.plant_request and p.state not in ("done", "cancel"))
        stages = {}
        for pick in open_requests:
            stage = legacy.get(pick.id) or pick.plant_stage
            stages[pick.id] = stage if stage in OPEN_STAGE_ORDER else "new"
        open_requests.with_context(plant_skip_notify=True)._plant_sync_checks()
        for pick in open_requests:
            stage = stages[pick.id]
            if stage == "ready":
                pick.plant_check_ids.filtered(lambda c: not c.done).sudo().with_context(plant_skip_notify=True).write({"done": True})
            pick.with_context(plant_auto_stage=True).write({"plant_stage": stage, "plant_stage_manual_progress": pick._plant_progress_key()})
        return True

    def _plant_notify_update(self):
        """Tell the plant users' browsers that a request changed (tick, stage, delivery): their views reload."""
        plant_users = self.env["res.users"].sudo().browse(list(self._plant_users())).exists()
        targets = plant_users.partner_id or self._plant_channel().channel_member_ids.partner_id
        for pick in self:
            payload = {"picking_id": pick.id, "name": pick.name, "stage": pick.plant_stage, "progress": pick.plant_progress}
            for partner in targets:
                self.env["bus.bus"]._sendone(partner, "plant_request_board/update", payload)
        return True

    def _plant_validation_issues(self):
        """What stands between the request and a direct validation: the open lines without a quantity (they would
        be delivered in full) and the lines whose demand exceeds the stock at the source location."""
        self.ensure_one()
        missing, shortages = [], []
        for mv in self.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
            rounding = mv.product_uom.rounding
            if float_is_zero(mv.quantity, precision_rounding=rounding) and not float_is_zero(mv.product_uom_qty, precision_rounding=rounding):
                missing.append(mv)
            available = mv.product_id.with_context(location=self.location_id.id).qty_available
            if mv.product_id.uom_id != mv.product_uom:
                available = mv.product_id.uom_id._compute_quantity(available, mv.product_uom)
            demand = mv.quantity if not float_is_zero(mv.quantity, precision_rounding=rounding) else mv.product_uom_qty
            if float_compare(demand, available, precision_rounding=rounding) > 0:
                shortages.append((mv, demand, available))
        return {"missing": missing, "shortages": shortages}

    @api.model
    def _plant_qty_text(self, move, qty):
        unit = (move.product_uom.name or "").strip().lower()
        if unit.startswith(("g", "gram")) and abs(qty) >= 1000:
            return "%g kg" % (qty / 1000.0)
        return "%g %s" % (qty, move.product_uom.name or "")

    def action_plant_validate(self):
        """"Validar entrega" from the card, the list or the form: the standard validation of the transfer, with
        the user's own rights, a note in the chatter, and the stage follows (Entregada). It validates at once
        only when every tick is done or every open line has its quantity, and nothing is short; otherwise it asks
        for an explicit confirmation listing the lines that would be delivered in full and the shortages."""
        self.ensure_one()
        if hasattr(self, "check_access"):
            self.check_access("write")
        else:
            self.check_access_rights("write")
            self.check_access_rule("write")
        if not self.plant_request or self.state in ("done", "cancel"):
            raise UserError(_("Solo se valida una solicitud a planta que no esté entregada ni cancelada."))
        issues = self._plant_validation_issues()
        ticks_done = bool(self.plant_check_ids) and all(self.plant_check_ids.mapped("done"))
        if (issues["missing"] and not ticks_done or issues["shortages"]) and not self.env.context.get("plant_validate_confirmed"):
            return self.env["plant.validate.wizard"]._open_for(self, issues)
        if self.state == "draft":
            self.action_confirm()
        for mv in issues["missing"]:
            if mv.state not in ("done", "cancel"):
                mv.quantity = mv.product_uom_qty
        res = self.button_validate()
        if isinstance(res, dict):
            return res
        if self.state == "done":
            body = _("Entrega validada desde Planta por %s: %s líneas, alistamiento %s %%.") % (self.env.user.name, len(self.move_ids), int(self.plant_progress))
            if issues["missing"]:
                body += " " + _("Entregadas completas sin cantidad previa: %s.") % ", ".join(mv.product_id.display_name for mv in issues["missing"])
            if issues["shortages"]:
                body += " " + _("Sin stock suficiente al validar: %s.") % "; ".join("%s (%s pedido, %s en stock)" % (mv.product_id.display_name, self._plant_qty_text(mv, demand), self._plant_qty_text(mv, available)) for mv, demand, available in issues["shortages"])
            self._plant_post_note(body)
            self._plant_notify_update()
        return True

    def _plant_post_note(self, body):
        """An internal note on the transfer. A plant user without an e-mail address must still be able to deliver:
        the note is then signed by OdooBot (the body names the user)."""
        try:
            self.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")
        except UserError:
            root = self.env.ref("base.partner_root")
            self.sudo().message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note", author_id=root.id, email_from=root.email_formatted or "odoobot@example.com")

    def _compute_plant_green_alert(self):
        """The green coffee alert of each pending request, from the cumulative allocation of its plant."""
        pending = self.filtered(lambda p: p.plant_request and p.plant_stage in ("new", "preparing") and p.state not in ("done", "cancel"))
        for pick in self - pending:
            pick.plant_green_alert_html = False
            pick.plant_green_status = False
        Line = self.env["plant.coffee.line"]
        for plant in pending.plant_warehouse_id:
            allocation = Line._plant_green_allocation(plant_id=plant.id)
            by_pick = {r["picking_id"]: r for r in allocation["requests"]}
            for pick in pending.filtered(lambda p: p.plant_warehouse_id == plant):
                req = by_pick.get(pick.id)
                if not req or not req["alerts"]:
                    pick.plant_green_alert_html = False
                    pick.plant_green_status = False
                    continue
                rows = Markup("").join(
                    Markup("<div class='plant-green plant-green-%s' title='%s'><i class='fa fa-leaf'></i> <b>%s</b>: tostar %s kg → %s kg verde · %s</div>") % (
                        a["status"], escape(a["message"]), escape(a["line"]), "%.1f" % a["to_roast_kg"], "%.1f" % a["green_needed_kg"],
                        ("faltan %.1f kg" % -a["remaining_kg"]) if a["status"] == "red" else ("quedan %.1f kg" % a["remaining_kg"]))
                    for a in req["alerts"])
                pick.plant_green_alert_html = Markup("<div class='plant-green-box'>%s</div>") % rows
                pick.plant_green_status = req["status"]

    @api.depends("create_date", "date_done", "state")
    def _compute_plant_days(self):
        now = fields.Datetime.now()
        for pick in self:
            start = pick.create_date or now
            end = pick.date_done if pick.state == "done" and pick.date_done else now
            pick.plant_days_waiting = round((end - start).total_seconds() / 86400.0, 1)

    @api.depends("move_ids.product_uom_qty", "move_ids.product_id", "move_ids.product_uom", "move_ids.plant_kind_id")
    def _compute_plant_totals(self):
        rules = self._plant_line_rules()
        for pick in self:
            coffee_g = 0.0
            units = 0.0
            for mv in pick.move_ids:
                if self._plant_is_coffee_bulk(mv, rules):
                    coffee_g += self._plant_grams(mv)
                else:
                    units += mv.product_uom_qty
            pick.plant_line_count = len(pick.move_ids)
            pick.plant_coffee_kg = coffee_g / 1000.0
            pick.plant_pack_units = units

    @api.model
    def _plant_grams(self, move):
        """Quantity of the line in grams, from the unit's name (works the same on every Odoo version)."""
        unit = (move.product_uom.name or "").strip().lower()
        if unit.startswith(("kg", "kilo")):
            return move.product_uom_qty * 1000.0
        if unit.startswith(("g", "gram")):
            return move.product_uom_qty
        return move.product_uom_qty

    def _compute_plant_store_comment(self):
        """The last comment written on each transfer, read with one query for the whole batch."""
        last = {}
        for msg in self.env["mail.message"].sudo().search([("model", "=", "stock.picking"), ("res_id", "in", self.ids), ("message_type", "=", "comment"), ("body", "!=", False)], order="date desc, id desc"):
            last.setdefault(msg.res_id, msg)
        for pick in self:
            msg = last.get(pick.id)
            text = html2plaintext(msg.body).strip() if msg else ""
            pick.plant_store_comment = text or False

    # --- what each line is: the plant fields of the product -----------------------------------------
    @api.model
    def _plant_line_rules(self):
        """What describing a batch of lines needs, loaded once: the plant.kind records, the classifier rules (for
        products nobody classified yet) and the card settings."""
        Settings = self.env["res.config.settings"]
        return {
            "kinds": self.env["plant.kind"]._by_code(),
            "parser": self.env["product.template"]._plant_parser_rules(),
            "grind_text": {code: label.lower() for code, label in self.env["product.template"]._fields["plant_grind"].selection},
            "short_words": Settings._plant_get_pairs("plant_short_words"),
            "card_rows": Settings._plant_get_int("plant_card_rows"),
        }

    @api.model
    def _plant_is_coffee_bulk(self, move, rules):
        return move.product_id.product_tmpl_id._plant_values(rules["parser"])["kind"] == "prepare"

    @api.model
    def _plant_describe(self, product, rules):
        """kind code + attributes for the plant: line (Paz, Punk…), grind (en grano / molido) and size, read from
        the product's plant fields (of its master product when it has one)."""
        vals = product.product_tmpl_id._plant_values(rules["parser"])
        return {"kind": vals["kind"], "line": vals["line_name"], "grind": rules["grind_text"].get(vals["grind"], ""), "size": self.env["product.template"]._plant_size_text(vals["grams"]), "values": vals}

    @api.model
    def _plant_short_name(self, name, rules=None):
        """Readable short name for a supply: "Bolsa 454 g Libre en grano (cód. barras)"."""
        out = (name or "").upper()
        for word, text in (rules or self._plant_line_rules())["short_words"]:
            out = re.sub(r"\b" + re.escape(word) + r"\b", lambda _m, t=text: t, out)
        words = []
        for w in out.split():
            words.append(w if (w.islower() or not w.isupper() or len(w) <= 2 and w not in ("DE", "Y")) else w.capitalize())
        return " ".join(words).replace(" De ", " de ").replace(" Y ", " y ").replace(" Para ", " para ").replace(" X ", " x ")

    @api.model
    def _plant_line_label(self, move, desc):
        """Short text for a card line: "PAZ 15 kg", "PAZ 340 g en grano ×36", "Vaso azul 9 oz ×1000"."""
        qty = move.product_uom_qty
        if desc["kind"] == "prepare":
            grams = self._plant_grams(move)
            amount = ("%g kg" % (grams / 1000.0)) if grams >= 1000 else ("%g g" % grams)
            return (desc["line"] or move.product_id.name.title()) + " " + amount
        parts = [desc["line"] or move.product_id.name.title(), desc["size"], desc["grind"]]
        return " ".join(x for x in parts if x) + " ×%g" % qty if desc["kind"] in ("packed", "ready") else move.product_id.name.title() + " ×%g" % qty

    @api.depends("move_ids.product_uom_qty", "move_ids.product_id", "move_ids.product_uom", "move_ids.plant_kind_id", "move_ids.product_id.product_tmpl_id.plant_coffee_summary")
    def _compute_plant_card(self):
        rules = self._plant_line_rules()
        limit = rules["card_rows"]
        for pick in self:
            groups = {code: [] for code in rules["kinds"]}
            for mv in pick.move_ids:
                desc = self._plant_describe(mv.product_id, rules)
                sheet = mv.product_id.product_tmpl_id.plant_coffee_summary or ""
                rows = groups.setdefault(desc["kind"], [])
                if desc["kind"] == "prepare":
                    grams = self._plant_grams(mv)
                    rows.append((grams, desc["line"] or mv.product_id.name.title(), ("%g kg" % (grams / 1000.0)) if grams >= 1000 else ("%g g" % grams), sheet))
                elif desc["kind"] in ("packed", "ready"):
                    text = " ".join(x for x in (desc["line"] or self._plant_short_name(mv.product_id.name, rules), desc["size"], desc["grind"]) if x)
                    rows.append((mv.product_uom_qty, text, "%g" % mv.product_uom_qty, sheet))
                else:
                    rows.append((mv.product_uom_qty, self._plant_short_name(mv.product_id.name, rules), "%g" % mv.product_uom_qty, ""))
            html = Markup("")
            for code, kind in rules["kinds"].items():
                rows = sorted(groups[code], key=lambda r: (-r[0], r[1]))
                if not rows:
                    continue
                title = Markup("<div class='plant-group-title'><i class='fa %s' title='%s'></i> %s <span class='plant-count'>%s</span></div>") % (kind.icon or "fa-tag", kind.name, kind.name, len(rows))
                shown = rows[:limit]
                body = Markup("<table class='plant-lines'>%s</table>") % Markup("").join(
                    Markup("<tr><td class='plant-qty'>%s</td><td class='plant-name'><span>%s</span>%s</td></tr>") % (
                        r[2], escape(r[1]), Markup("<div class='plant-sheet'>%s</div>") % escape(r[3]) if r[3] else Markup("")) for r in shown)
                if len(rows) > limit:
                    body += Markup("<div class='plant-more'>+%s más en el detalle</div>") % (len(rows) - limit)
                html += Markup("<div class='plant-group plant-%s'>%s%s</div>") % (code, title, body)
            pick.plant_card_html = Markup("<div class='plant-card'>%s</div>") % html if html else False


    # --- who is plant staff (their own transfers do not ring) ---------------------------
    @api.model_create_multi
    def create(self, vals_list):
        picks = super().create(vals_list)
        requests_ = picks.filtered("plant_request")
        if requests_:
            requests_._plant_mark_stores()
            requests_._plant_sync_checks()
            requests_.write({"plant_briefing_state": "pending" if self._plant_ai_enabled() else "none"})
            # deliveries born from a sale order get their lines right after the picking is created: notify after commit
            self.env.cr.postcommit.add(partial(self._plant_notify_after_commit, self.env.cr.dbname, requests_.ids))
        return picks

    def write(self, vals):
        if "plant_stage" in vals and not self.env.context.get("plant_auto_stage"):
            if vals["plant_stage"] in ("delivered", "cancelled"):
                raise UserError(_("Entregada y Cancelada siguen la transferencia: usa «Validar entrega» o cancela la transferencia."))
            if vals["plant_stage"] not in OPEN_STAGE_ORDER:
                raise UserError(_("Etapa desconocida."))
        before = {pick.id: (pick.plant_request, pick.plant_stage) for pick in self} if not self.env.context.get("plant_auto_stage") else {}
        res = super().write(vals)
        if vals.keys() & {"location_id", "location_dest_id"}:
            self.filtered("plant_request")._plant_mark_stores()
        if "plant_stage" in vals and not self.env.context.get("plant_auto_stage"):
            for pick in self.filtered(lambda p: p.plant_request and p.state not in ("done", "cancel")):
                pick.with_context(plant_auto_stage=True).plant_stage_manual_progress = pick._plant_progress_key()   # fixed by hand: holds until the ticks change
        if "move_ids" in vals or (before and any(before[p.id][0] != p.plant_request for p in self)):
            self._plant_sync_checks()
        if before:
            changed = self.filtered(lambda p: p.plant_request and before[p.id][1] != p.plant_stage)
            if changed:
                changed._plant_notify_update()
        return res

    @staticmethod
    def _plant_notify_after_commit(dbname, ids):
        registry = Registry(dbname)   # odoo.registry() was removed in 19; Registry(db) works on every version
        with registry.cursor() as cr:
            env = api.Environment(cr, odoo.SUPERUSER_ID, {})
            env["stock.picking"].browse(ids).exists().filtered("plant_request")._plant_notify_odoo()

    # --- Odoo notifications: Discuss channel + browser ring for the plant users ---------------
    def _plant_channel(self):
        raw = str(self.env["res.config.settings"]._plant_get("plant_channel_id") or "")
        return self.env["discuss.channel"].sudo().browse(int(raw)) if raw.isdigit() else self.env["discuss.channel"].sudo()

    def _plant_notification_payload(self, test=False):
        self.ensure_one()
        return {
            "picking_id": self.id, "name": self.name, "store": self.plant_counterparty or "", "channel": self.plant_channel_id.name or "", "test": test,
            "summary": "%s · %s líneas · %s kg de café · %s unidades · pedida por %s" % (self.name, self.plant_line_count, ("%g" % self.plant_coffee_kg), ("%g" % self.plant_pack_units), self.plant_requested_by or ""),
        }

    def _plant_notify_odoo(self, test=False):
        """Announce the request in the Discuss channel and ring the plant users' browsers through the bus."""
        channel = self._plant_channel()
        plant_users = self.env["res.users"].sudo().browse(list(self._plant_users())).exists()
        for pick in self:
            if pick.create_uid.id in plant_users.ids and not test:
                continue
            payload = pick._plant_notification_payload(test)
            if channel.exists():
                body = Markup("<b>%s</b> (%s) pidió <a href='#' data-oe-model='stock.picking' data-oe-id='%s'>%s</a>: %s líneas, %s kg de café, %s unidades.") % (
                    pick.plant_counterparty or "", pick.plant_channel_id.name or "", pick.id, pick.name, pick.plant_line_count, "%g" % pick.plant_coffee_kg, "%g" % pick.plant_pack_units)
                if pick.plant_card_html:
                    body += pick.plant_card_html
                channel.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_comment", author_id=self.env.ref("base.partner_root").id)
            targets = plant_users.partner_id or channel.channel_member_ids.partner_id
            for partner in targets:   # _sendone exists in every version; _sendmany was dropped in 19
                self.env["bus.bus"]._sendone(partner, "plant_request_board/new", payload)
        return True

    def action_plant_test_notification(self):
        """Ring the current user's browser (settings button)."""
        pick = self.search([("plant_request", "=", True)], limit=1, order="create_date desc")
        payload = pick._plant_notification_payload(test=True) if pick else {"picking_id": False, "name": "", "store": "", "test": True, "summary": "Prueba de sonido y notificación de planta"}
        self.env["bus.bus"]._sendone(self.env.user.partner_id, "plant_request_board/new", payload)
        return True

    def _plant_users(self):
        return self.env["res.config.settings"]._plant_staff_ids()

    # --- the delivery note (PDF, one page per request) -----------------------------------------------
    def _plant_delivery_address(self):
        """Lines of the delivery address: the store's warehouse (its contact) for a transfer, the delivery contact
        of the transfer otherwise: name, street, apartment, city / state / zip, country, phone."""
        self.ensure_one()
        partner = self.partner_id
        store = self.plant_store_id
        if store and not partner:
            partner = store.partner_id
        lines = []
        if store:
            lines.append(store.name)
        if partner and partner.name and partner.name not in lines:
            lines.append(partner.name)
        if partner:
            lines += [x for x in (partner.street, partner.street2) if x]
            locality = ", ".join(x for x in (partner.city, partner.state_id.name, partner.zip) if x)
            if locality:
                lines.append(locality)
            if partner.country_id:
                lines.append(partner.country_id.name)
            phones = " / ".join(x for x in (partner.phone, partner.mobile if "mobile" in partner._fields else False) if x)   # Odoo 19 has no mobile field
            if phones:
                lines.append(_("Tel: %s") % phones)
        return lines

    @api.model
    def _plant_note_layout(self, row_count):
        """How the lines fit in one letter page: font size and number of columns by the number of rows (lines and
        kind headers). Measured with wkhtmltopdf on US Letter with 8 mm margins."""
        if row_count <= 24:
            return {"name": "normal", "columns": 1, "font": "10px", "compact": False}
        if row_count <= 44:
            return {"name": "dense", "columns": 1, "font": "8px", "compact": False}
        if row_count <= 100:
            return {"name": "columns", "columns": 2, "font": "7.5px", "compact": True}
        return {"name": "columns3", "columns": 3, "font": "6.5px", "compact": True}

    def _plant_delivery_note_data(self):
        """Everything the delivery note prints, computed here so the template only lays it out: the lines grouped
        by kind in the plant's order (coffee first, supplies last), separate totals (kg of coffee, bags, ready
        units, supply units), references, address, branding, the layout that fits one page."""
        self.ensure_one()
        rules = self._plant_line_rules()
        company = self.company_id or self.env.company
        groups = {code: {"name": kind.name, "sequence": kind.sequence, "code": code, "lines": []} for code, kind in rules["kinds"].items()}
        totals = {"coffee_kg": 0.0, "coffee_bags": 0.0, "ready_units": 0.0, "supply_units": 0.0}
        moves = self.move_ids.filtered(lambda m: m.state != "cancel") or self.move_ids   # a cancelled request still prints what was asked
        for mv in moves.sorted(lambda m: (m.plant_kind_id.sequence, m.plant_coffee_line or "", m.product_id.display_name)):
            desc = self._plant_describe(mv.product_id, rules)
            kind = desc["kind"]
            coffee = kind in ("prepare", "packed")
            line_kg = mv.plant_kg if (coffee and mv.plant_request) else 0.0
            groups.setdefault(kind, {"name": kind, "sequence": 99, "code": kind, "lines": []})["lines"].append({
                "code": mv.product_id.default_code or "", "name": mv.product_id.name, "line": desc["line"], "size": desc["size"], "grind": desc["grind"],
                "qty": ("%g" % mv.product_uom_qty), "uom": mv.product_uom.name, "kg": ("%.3f" % line_kg) if coffee else "—", "coffee": coffee,
            })
            if coffee:
                totals["coffee_kg"] += line_kg
                if kind == "packed":
                    totals["coffee_bags"] += mv.product_uom_qty
            elif kind == "ready":
                totals["ready_units"] += mv.product_uom_qty
            else:
                totals["supply_units"] += mv.product_uom_qty   # supplies (and anything else) in their own unit, never kg
        ordered_groups = sorted((g for g in groups.values() if g["lines"]), key=lambda g: g["sequence"])
        rows = []
        for g in ordered_groups:
            rows.append({"header": "%s (%s)" % (g["name"], len(g["lines"]))})
            rows.extend(g["lines"])
        layout = self._plant_note_layout(len(rows))
        size = -(-len(rows) // layout["columns"])   # rows per column, rounded up
        chunks = [rows[i:i + size] for i in range(0, len(rows), size)] or [[]]
        sale = self.sale_id if "sale_id" in self._fields else False
        external_ref = (sale.client_order_ref if sale and sale.client_order_ref else "") or (self.origin if self.origin and (not sale or self.origin != sale.name) else "")
        date = self.scheduled_date or self.create_date
        return {
            "company": company.name, "logo": image_data_uri(company.logo) if company.logo else False,
            "color": company.primary_color or "#2F5496", "color2": company.secondary_color or "#8EA9DB",
            "date": fields.Datetime.context_timestamp(self, date).strftime("%Y-%m-%d %H:%M") if date else "",
            "printed": fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime("%Y-%m-%d %H:%M"),
            "store": self.plant_store_id.name if self.plant_store_id and self.plant_store_id.name != self.plant_counterparty else "",
            "sale": sale.name if sale else "", "external_ref": external_ref, "stage": dict(self._fields["plant_stage"].selection).get(self.plant_stage, ""),
            "cancelled": self.state == "cancel",
            "groups": ordered_groups, "rows": rows, "chunks": chunks, "layout": layout, "dense": layout["name"] != "normal",
            "line_count": len(moves), "kg": "%.3f" % totals["coffee_kg"], "bags": "%g" % totals["coffee_bags"], "ready_units": "%g" % totals["ready_units"], "supply_units": "%g" % totals["supply_units"],
            "units": "%g" % (totals["coffee_bags"] + totals["ready_units"] + totals["supply_units"]),
            "address": self._plant_delivery_address(), "note": self.note or "", "store_comment": self.plant_store_comment or "",
        }

    def action_plant_print_delivery_note(self):
        # config=False: the note has its own layout, so Odoo must not ask to configure the document layout first
        return self.env.ref("plant_request_board.action_report_plant_delivery_note").report_action(self, config=False)

    # --- briefing: facts from Odoo, words from the model -----------------------------------
    @api.model
    def _plant_anthropic_key(self):
        """The Anthropic key lives outside the database: the environment variable PLANT_ANTHROPIC_API_KEY, else the
        option plant_anthropic_api_key of the server's odoo.conf. Never in ir.config_parameter."""
        return (os.environ.get("PLANT_ANTHROPIC_API_KEY") or odoo.tools.config.get("plant_anthropic_api_key") or "").strip()

    @api.model
    def _plant_ai_enabled(self):
        """The AI briefing runs only with an Anthropic key on the server; without one the cron stays silent and
        the requests are not queued (the facts table is still available on demand with the button)."""
        return bool(self._plant_anthropic_key())

    def _plant_facts(self):
        """Everything the briefing may say, computed from the database. Never from the model."""
        self.ensure_one()
        src = self.location_id
        days = self.env["res.config.settings"]._plant_get_int("plant_history_days")
        since = fields.Datetime.now() - timedelta(days=days)
        history = self.env["stock.move"]._read_group(
            [("picking_id.plant_request", "=", True), ("picking_id.plant_counterparty", "=", self.plant_counterparty), ("picking_id.state", "=", "done"),
             ("picking_id.date_done", ">=", since), ("product_id", "in", self.move_ids.product_id.ids)],
            ["product_id"], ["__count", "product_uom_qty:sum"])
        hist = {product.id: (count, qty / count) for product, count, qty in history if count}
        lines = []
        rules = self._plant_line_rules()
        for mv in self.move_ids:
            desc = self._plant_describe(mv.product_id, rules)
            kind = rules["kinds"].get(desc["kind"])
            avail = mv.product_id.with_context(location=src.id).qty_available
            avail_uom = mv.product_id.uom_id._compute_quantity(avail, mv.product_uom) if mv.product_id.uom_id != mv.product_uom else avail
            times, avg = hist.get(mv.product_id.id, (0, 0.0))
            flags = []
            if mv.state not in ("done", "cancel") and avail_uom < mv.product_uom_qty:
                flags.append("faltante")
            if times == 0:
                flags.append("nuevo para esta tienda")
            elif avg and mv.product_uom_qty > 2 * avg:
                flags.append("más del doble de lo usual")
            elif avg and mv.product_uom_qty < avg / 2:
                flags.append("menos de la mitad de lo usual")
            lines.append({
                "product": mv.product_id.display_name, "requested": mv.product_uom_qty, "delivered": mv.quantity, "uom": mv.product_uom.name,
                "available_at_plant": round(avail_uom, 2), "usual_qty": round(avg, 2), "times_requested": times, "flags": flags,
                "coffee": self._plant_is_coffee_bulk(mv, rules), "state": mv.state,
                "kind": kind.name if kind else desc["kind"], "line": desc["line"], "grind": desc["grind"], "size": desc["size"],
                "coffee_sheet": mv.product_id.product_tmpl_id.plant_coffee_summary or "",
            })
        return {
            "request": self.name, "store": self.plant_counterparty, "channel": self.plant_channel_id.name or "", "requested_by": self.plant_requested_by, "created": fields.Datetime.to_string(self.create_date),
            "scheduled": fields.Datetime.to_string(self.scheduled_date) if self.scheduled_date else None, "stage": dict(PLANT_STAGES).get(self.plant_stage),
            "line_count": self.plant_line_count, "coffee_kg": round(self.plant_coffee_kg, 2), "pack_units": self.plant_pack_units, "history_days": days,
            "store_comment": self.plant_store_comment or "", "store_comment_note": "written by the store user who created the request; @mentions are plant staff the store is calling, not authors",
            "lines": lines,
        }

    @api.model
    def _plant_facts_html(self, facts):
        rows = []
        for ln in facts["lines"]:
            flag = ", ".join(ln["flags"])
            cls = ' class="text-danger"' if "faltante" in ln["flags"] else (' class="text-warning"' if flag else "")
            rows.append(Markup("<tr%s><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td><td>%s</td></tr>") % (
                Markup(cls), escape(ln["product"]), _fmt(ln["requested"]) + " " + escape(ln["uom"]), _fmt(ln["delivered"]), _fmt(ln["available_at_plant"]),
                (_fmt(ln["usual_qty"]) + " ×" + str(ln["times_requested"])) if ln["times_requested"] else "—", escape(flag)))
        shortages = sum(1 for ln in facts["lines"] if "faltante" in ln["flags"])
        head = Markup("<p><b>%s</b> · %s · %s líneas · %s kg de café · %s unidades de empaque%s</p>") % (
            escape(facts["store"]), escape(facts["stage"] or ""), facts["line_count"], _fmt(facts["coffee_kg"]), _fmt(facts["pack_units"]),
            Markup(" · <span class='text-danger'>%s con faltante en planta</span>") % shortages if shortages else "")
        comment = Markup("<p><i>Tienda: %s</i></p>") % escape(facts["store_comment"]) if facts["store_comment"] else Markup("")
        table = Markup("<table class='table table-sm'><thead><tr><th>Producto</th><th class='text-end'>Pedido</th><th class='text-end'>Entregado</th><th class='text-end'>Disponible en planta</th><th class='text-end'>Usual (%s d)</th><th>Señal</th></tr></thead><tbody>%s</tbody></table>") % (
            facts.get("history_days", ""), Markup("").join(rows))
        return head + comment + table

    @api.model
    def _plant_narrative(self, facts):
        """Short briefing in Spanish written by the model from the facts only. Empty when no key is configured or the call fails."""
        key = self._plant_anthropic_key()
        if not key:
            return ""
        model = self.env["res.config.settings"]._plant_get("plant_anthropic_model").strip()
        system = ("Eres el asistente de la planta de producción de Libertario Coffee Roasters. Recibes los hechos de una solicitud de una tienda, "
                  "calculados por Odoo. Escribe un resumen de 3 a 5 frases en español, tono de colega, para quien alista el pedido: qué café hay que "
                  "alistar o tostar, qué empaque, qué falta en planta, y qué cantidades se salen de lo usual de esa tienda. Usa solo los hechos dados; "
                  "no inventes cantidades ni productos. El comentario (store_comment) lo escribió la tienda; las personas @mencionadas son de planta y no lo escribieron. "
                  "Si la tienda pide algo puntual, menciónalo como pedido de la tienda. Sin saludos ni listas.")
        body = {"model": model, "max_tokens": 400, "system": system, "messages": [{"role": "user", "content": json.dumps(facts, ensure_ascii=False)}]}
        try:
            resp = requests.post(ANTHROPIC_URL, json=body, headers={"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}, timeout=40)
            resp.raise_for_status()
            return "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text").strip()
        except (requests.RequestException, ValueError) as e:  # noqa: BLE001
            _logger.warning("Plant briefing model call failed for %s: %s", self, e)
            return ""

    def action_plant_briefing(self):
        for pick in self.filtered("plant_request"):
            try:
                facts = pick._plant_facts()
                narrative = pick._plant_narrative(facts)
                html = (Markup("<p>%s</p>") % escape(narrative) if narrative else Markup("")) + self._plant_facts_html(facts)
                pick.write({"plant_briefing": html, "plant_briefing_state": "done", "plant_briefing_date": fields.Datetime.now()})
            except Exception as e:  # noqa: BLE001
                _logger.exception("Plant briefing failed for %s", pick)
                pick.write({"plant_briefing_state": "error", "plant_briefing": Markup("<p>No se pudo analizar: %s</p>") % escape(str(e)[:200])})
        return True

    @api.model
    def _plant_cron_briefings(self, limit=20):
        if not self._plant_ai_enabled():
            return   # no key: nothing to write, no noise
        self.search([("plant_request", "=", True), ("plant_briefing_state", "=", "pending")], limit=limit, order="create_date asc").action_plant_briefing()


def _fmt(v):
    v = float(v or 0)
    return ("%d" % v) if v == int(v) else ("%.2f" % v)
