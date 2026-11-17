import io
import os
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools.pdf import PdfFileReader

TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

# the ir.config_parameter keys behind Inventario › Ajustes › Planta (res.config.settings, config_parameter=)
ICP_PLANT_USERS = "plant_request_board.plant_user_ids"
ICP_CHANNEL = "plant_request_board.channel_id"
ICP_SHORT_WORDS = "plant_request_board.short_words"


@tagged("post_install", "-at_install")
class TestPlantRequest(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(ICP_PLANT_USERS, "")
        self.plant = self.env["stock.warehouse"].create({"name": "Planta test", "code": "TPLT", "plant_is_plant": True})
        self.store = self.env["stock.warehouse"].create({"name": "Tienda test", "code": "TST"})
        self.coffee = self.env["product.product"].create({"name": "CAFE EN GRANO PARA PREPARAR - PAZ", "type": "consu", "is_storable": True, "uom_id": self.env.ref("uom.product_uom_gram").id})
        self.cups = self.env["product.product"].create({"name": "VASO AZUL 9 ONZAS", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(self.cups, self.plant.lot_stock_id, 300)

    def _channel(self, code):
        return self.env.ref("plant_request_board.channel_%s" % code)

    def _transfer(self, plant, dest_wh, lines):
        """Internal transfer plant → dest_wh with [(product, qty)]."""
        return self.env["stock.picking"].create({
            "picking_type_id": plant.int_type_id.id, "location_id": plant.lot_stock_id.id, "location_dest_id": dest_wh.lot_stock_id.id,
            "move_ids": [(0, 0, {"product_id": p.id, "product_uom_qty": qty, "product_uom": p.uom_id.id, "location_id": plant.lot_stock_id.id, "location_dest_id": dest_wh.lot_stock_id.id}) for p, qty in lines],
        })

    def _request(self, qty_cups=1000):
        return self._transfer(self.plant, self.store, [(self.coffee, 15000), (self.cups, qty_cups)])

    def _deliver(self, partner, pricelist, team_id=False, product=None):
        """Delivery of a confirmed sale order from the plant."""
        so = self.env["sale.order"].create({"partner_id": partner.id, "pricelist_id": pricelist.id, "warehouse_id": self.plant.id, "team_id": team_id,
                                           "order_line": [(0, 0, {"product_id": (product or self.cups).id, "product_uom_qty": 10})]})
        so.action_confirm()
        return so.picking_ids[:1]

    def test_request_is_detected_and_summarised(self):
        pick = self._request()
        self.assertTrue(pick.plant_request)
        self.assertEqual((pick.plant_warehouse_id, pick.plant_store_id), (self.plant, self.store))
        self.assertEqual(pick.plant_stage, "new")
        self.assertEqual(pick.plant_line_count, 2)
        self.assertAlmostEqual(pick.plant_coffee_kg, 15.0)
        self.assertEqual(pick.plant_pack_units, 1000)
        self.assertEqual(pick.plant_briefing_state, "none")   # no Anthropic key in the tests: nothing is queued
        # a transfer inside the plant is not a request
        internal = self.env["stock.picking"].create({"picking_type_id": self.plant.int_type_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.plant.lot_stock_id.id})
        self.assertFalse(internal.plant_request)

    def test_card_describes_each_line(self):
        packed = self.env["product.product"].create({"name": "PAZ 340 G MOLIDO", "type": "consu", "is_storable": True})
        pick = self._request()
        pick.write({"move_ids": [(0, 0, {"product_id": packed.id, "product_uom_qty": 36, "product_uom": packed.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        html = pick.plant_card_html
        self.assertIn("Café para preparar", html)
        self.assertIn("<td class='plant-qty'>15 kg</td><td class='plant-name'><span>Paz</span>", html)
        self.assertIn("<td class='plant-qty'>36</td><td class='plant-name'><span>Paz 340 g molido</span>", html)
        self.assertIn("<td class='plant-qty'>1000</td><td class='plant-name'><span>Vaso Azul 9 oz</span>", html)
        self.assertEqual(self.env["stock.picking"]._plant_short_name("BOLSA PARA EMPACAR 454 GRAMOS LIBRE EN GRANO CODIGO DE BARRAS"), "Bolsa 454 g Libre en grano (cód. barras)")
        desc = pick._plant_describe(packed, pick._plant_line_rules())
        self.assertEqual((desc["kind"], desc["line"], desc["grind"], desc["size"]), ("packed", "Paz", "molido", "340 g"))

    def test_labels_and_keywords_are_configuration(self):
        """Labels, icons and keywords are records and settings: a change applies at once, with no deployment."""
        prepare = self.env.ref("plant_request_board.kind_prepare")
        prepare.write({"name": "Café para preparación", "icon": "fa-coffee"})
        pick = self._request()
        self.assertIn("<i class='fa fa-coffee' title='Café para preparación'></i> Café para preparación", pick.plant_card_html)
        self.assertEqual(pick.move_ids.filtered(lambda m: m.product_id == self.coffee).plant_kind_id, prepare)
        self.assertEqual(pick._plant_facts()["lines"][0]["kind"], "Café para preparación")
        # a product with none of the words is a supply; a word added to a kind reclassifies the open lines
        thermo = self.env["product.product"].create({"name": "TERMO LIBERTARIO", "type": "consu", "is_storable": True})
        pick.write({"move_ids": [(0, 0, {"product_id": thermo.id, "product_uom_qty": 3, "product_uom": thermo.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        line = pick.move_ids.filtered(lambda m: m.product_id == thermo)
        self.assertEqual(line.plant_kind_code, "supply")
        ready = self.env.ref("plant_request_board.kind_ready")
        ready.keywords = ready.keywords + ",TERMO"
        self.assertEqual(line.plant_kind_code, "ready")
        self.assertIn("Cápsulas, drip y listos <span class='plant-count'>1</span>", pick.plant_card_html)
        # the abbreviations of the card are a setting
        self.env["ir.config_parameter"].sudo().set_param(ICP_SHORT_WORDS, "TERMO=Termo; LIBERTARIO=Lib.")
        self.assertEqual(self.env["stock.picking"]._plant_short_name("TERMO LIBERTARIO"), "Termo Lib.")
        with self.assertRaises(Exception):   # the four kinds are structure: they cannot be deleted
            ready.unlink()

    def test_coffee_sheet_shows_on_card_and_inherits_from_bom(self):
        self.coffee.product_tmpl_id.write({"plant_coffee_variety": "Castillo", "plant_coffee_origin": "Huila", "plant_coffee_process": "lavado", "plant_roast_profile": "medio"})
        pick = self._request()
        self.assertIn("<div class='plant-sheet'>Castillo · Huila · Lavado · medio</div>", pick.plant_card_html)
        if "mrp.bom" in self.env:
            bag = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
            self.env["mrp.bom"].create({"product_tmpl_id": bag.product_tmpl_id.id, "product_qty": 1, "type": "phantom", "bom_line_ids": [(0, 0, {"product_id": self.coffee.id, "product_qty": 340})]})
            self.assertEqual(bag.product_tmpl_id.plant_coffee_summary, "Castillo · Huila · Lavado · medio")

    def test_channels_are_classified_by_records(self):
        """Every rule is a relation on the channel: warehouses, pricelists, teams, tags. No text is compared."""
        pick = self._request()
        self.assertEqual((pick.plant_channel_id, pick.plant_channel, pick.plant_counterparty), (self._channel("tiendas"), "tiendas", "Tienda test"))
        event = self.env["stock.warehouse"].create({"name": "Eventos test", "code": "TEVT"})
        self._channel("eventos").warehouse_ids = [(4, event.id)]
        ev = self._transfer(self.plant, event, [])
        self.assertEqual(ev.plant_channel, "eventos")
        self.assertFalse(event.plant_is_store)   # a warehouse a channel claims is not a store
        web = self.env["product.pricelist"].create({"name": "Pagina_Web test"})
        att = self.env["product.pricelist"].create({"name": "Attenza_USD test"})
        self._channel("ecommerce").pricelist_ids = [(4, web.id)]
        self._channel("attenza").pricelist_ids = [(4, att.id)]
        team = self.env["crm.team"].create({"name": "Comercial test"})
        self._channel("alianzas").team_ids = [(4, team.id)]
        tag = self.env["res.partner.category"].create({"name": "Hotel test"})
        self._channel("alianzas").partner_tag_ids = [(4, tag.id)]
        shop = self.env["res.partner"].create({"name": "Cliente web"})
        b2b = self.env["res.partner"].create({"name": "Restaurante X"})
        hotel = self.env["res.partner"].create({"name": "Hotel Y", "category_id": [(6, 0, tag.ids)]})
        usa = self.env["res.partner"].create({"name": "RE COFFEE TEST LLC"})
        plain = self.env["product.pricelist"].create({"name": "Lista comercial test"})
        self.assertEqual(self._deliver(shop, web).plant_channel, "ecommerce")
        self.assertEqual(self._deliver(usa, att).plant_channel, "attenza")
        b2b_pick = self._deliver(b2b, plain, team.id)
        self.assertEqual((b2b_pick.plant_channel, b2b_pick.plant_counterparty), ("alianzas", "Restaurante X"))
        self.assertEqual(self._deliver(hotel, plain).plant_channel, "alianzas")
        self.assertEqual(self._deliver(shop, plain).plant_channel, "otros")   # no rule: the fallback for deliveries
        # a rule change classifies the open requests again, at once
        self._channel("eventos").pricelist_ids = [(4, plain.id)]
        self.assertEqual(b2b_pick.plant_channel, "alianzas")   # Alianzas comes first in the order of evaluation
        self._channel("alianzas").write({"team_ids": [(3, team.id)], "partner_tag_ids": [(3, tag.id)]})
        self.assertEqual(b2b_pick.plant_channel, "eventos")

    def test_attenza_is_recognised_by_its_pricelists(self):
        """Attenza is not a contact in Odoo: the channel depends on its pricelists ("Attenza", "Attenza_USD");
        the partner rule stays empty and optional."""
        self.assertFalse(self._channel("attenza").partner_ids)
        att = self.env["product.pricelist"].create({"name": "Attenza"})
        att_usd = self.env["product.pricelist"].create({"name": "Attenza_USD"})
        self._channel("attenza").pricelist_ids = [(4, att.id), (4, att_usd.id)]
        customer = self.env["res.partner"].create({"name": "Cliente Attenza test"})
        for pricelist in (att, att_usd):
            pick = self._deliver(customer, pricelist)
            self.assertEqual((pick.plant_channel, pick.plant_counterparty), ("attenza", "Cliente Attenza test"))
            self.assertIn(pick.plant_channel_id, self.env["plant.sheet"]._sheet_channels("attenza"))
        plain = self.env["product.pricelist"].create({"name": "Lista plana test"})
        self.assertEqual(self._deliver(customer, plain).plant_channel, "otros")

    def test_partner_rule_recognises_company_contacts_and_branches(self):
        """The optional partner rule of a channel recognises the company, its contacts and its branches by record."""
        company = self.env["res.partner"].create({"name": "Empresa aliada test", "is_company": True})
        contact = self.env["res.partner"].create({"name": "Bodega aliada test", "parent_id": company.id, "type": "delivery"})
        branch = self.env["res.partner"].create({"name": "Sucursal aliada test", "parent_id": company.id, "is_company": True})
        other = self.env["res.partner"].create({"name": "Otro cliente test"})
        plain = self.env["product.pricelist"].create({"name": "Lista plana test"})
        self._channel("alianzas").partner_ids = [(4, company.id)]
        for partner in (company, contact):
            pick = self._deliver(partner, plain)
            self.assertEqual((pick.plant_channel, pick.plant_counterparty), ("alianzas", "Empresa aliada test"), partner.name)
        pick = self._deliver(branch, plain)   # a branch is its own commercial entity: the channel through its parent, named by itself
        self.assertEqual((pick.plant_channel, pick.plant_counterparty), ("alianzas", "Sucursal aliada test"))
        self.assertEqual(self._deliver(other, plain).plant_channel, "otros")

    def test_new_store_gets_its_column_without_configuration(self):
        """A warehouse that orders for the first time is a store: flagged by itself, with its own column at once.
        "Columnas de la hoja" is only a layer for alias, order and hiding."""
        rivana = self.env["stock.warehouse"].create({"name": "Rivana test", "code": "TRIV"})
        self.assertFalse(rivana.plant_is_store)
        Row = self.env["plant.sheet.row"]
        prep = Row.create({"sheet": "tiendas", "sequence": 1, "line": "Paz test", "name": "Paz Preparación test", "grams": 2500, "product_ids": [(6, 0, self.coffee.ids)]})
        pick = self._transfer(self.plant, rivana, [(self.coffee, 5000)])
        self.assertEqual((pick.plant_channel, pick.plant_store_id), ("tiendas", rivana))
        self.assertTrue(rivana.plant_is_store)
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        key = "w%s" % rivana.id
        col = next(c for c in data["columns"] if c["key"] == key)
        self.assertEqual((col["name"], col["fixed"], col["orders"]), ("RIVANA TEST", False, 1))
        row = next(r for g in data["groups"] for r in g["rows"] if r["id"] == prep.id)
        self.assertEqual((row["cells"][key], row["total"]), (2.0, 2.0))   # 5 kg = 2 bags of 2.5 kg
        # the optional layer: alias and order
        alias = self.env["plant.sheet.column"].create({"sheet": "tiendas", "sequence": 1, "name": "RIV", "warehouse_ids": [(6, 0, rivana.ids)]})
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertEqual((data["columns"][0]["key"], data["columns"][0]["name"]), ("c%s" % alias.id, "RIV"))
        self.assertFalse([c for c in data["columns"] if c["key"] == key])
        # hidden: the column is not drawn, the orders still count in the totals
        alias.hidden = True
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertFalse([c for c in data["columns"] if c["key"] in (key, "c%s" % alias.id)])
        row = next(r for g in data["groups"] for r in g["rows"] if r["id"] == prep.id)
        self.assertEqual(row["total"], 2.0)
        # a store the plant no longer serves is unflagged and loses its column
        alias.unlink()
        rivana.plant_is_store = False
        pick.action_cancel()
        self.assertFalse([c for c in self.env["plant.sheet"].get_data(sheet="tiendas")["columns"] if c["key"] == key])

    def test_second_plant_requests_are_detected(self):
        """Any warehouse flagged as plant: its transfers are requests, the sheet and the plan filter by plant and
        each plant is compared with its own stock."""
        med = self.env["stock.warehouse"].create({"name": "Planta Medellín test", "code": "TPLM", "plant_is_plant": True})
        wework = self.env["stock.warehouse"].create({"name": "WeWork test", "code": "TWEW"})
        self.env["stock.quant"]._update_available_quantity(self.coffee, med.lot_stock_id, 1000)
        self.assertEqual(self.env["plant.sheet"].get_plants(), [{"id": self.plant.id, "name": "Planta test"}, {"id": med.id, "name": "Planta Medellín test"}])
        pick = self._transfer(med, wework, [(self.coffee, 5000)])
        self.assertTrue(pick.plant_request)
        self.assertEqual((pick.plant_warehouse_id, pick.plant_channel, pick.plant_counterparty), (med, "tiendas", "WeWork test"))
        self.assertTrue(wework.plant_is_store)
        self.assertEqual(pick.move_ids.plant_warehouse_id, med)
        bog = self._request()   # 15 kg from the Bogotá plant
        self.assertEqual(bog.plant_warehouse_id, self.plant)
        prep = self.env["plant.sheet.row"].create({"sheet": "tiendas", "sequence": 1, "line": "Paz test", "name": "Paz Preparación test", "grams": 2500, "product_ids": [(6, 0, self.coffee.ids)]})
        Sheet = self.env["plant.sheet"]
        row_all = next(r for g in Sheet.get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["id"] == prep.id)
        row_med = next(r for g in Sheet.get_data(sheet="tiendas", plant_id=med.id)["groups"] for r in g["rows"] if r["id"] == prep.id)
        row_bog = next(r for g in Sheet.get_data(sheet="tiendas", plant_id=self.plant.id)["groups"] for r in g["rows"] if r["id"] == prep.id)
        self.assertEqual((row_all["total"], row_med["total"], row_bog["total"]), (8.0, 2.0, 6.0))
        self.assertAlmostEqual(row_med["inventory"], 0.4)   # 1 kg of coffee at Medellín = 0.4 bags of 2.5 kg
        self.assertAlmostEqual(row_all["inventory"], 0.4)
        self.assertEqual(row_bog["inventory"], 0.0)
        self.assertEqual(Sheet.get_data(sheet="tiendas", plant_id=med.id)["orders_total"], 1)
        # the plan: one row per product and plant
        rows = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open()["domain"])
        bulk = {r.plant_warehouse_id: r for r in rows.filtered(lambda r: r.product_id == self.coffee)}
        self.assertEqual((bulk[med].kg_ordered, bulk[med].kg_on_hand, bulk[med].kg_to_roast), (5.0, 1.0, 4.0))
        self.assertEqual((bulk[self.plant].kg_ordered, bulk[self.plant].kg_on_hand, bulk[self.plant].kg_to_roast), (15.0, 0.0, 15.0))
        only_med = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open(plant_id=med.id)["domain"])
        self.assertEqual(only_med.mapped("plant_warehouse_id"), med)

    def test_flagging_a_plant_classifies_its_transfers_again(self):
        """Marking (or unmarking) a warehouse as plant, in Ajustes or on the warehouse, classifies what leaves it."""
        depot = self.env["stock.warehouse"].create({"name": "Bodega test", "code": "TBOD"})
        pick = self._transfer(depot, self.store, [(self.coffee, 2000)])
        self.assertFalse(pick.plant_request)
        self.assertFalse(pick.move_ids.plant_request)
        depot.plant_is_plant = True
        self.assertTrue(pick.plant_request)
        self.assertEqual((pick.plant_warehouse_id, pick.plant_channel, pick.plant_stage), (depot, "tiendas", "new"))
        self.assertTrue(pick.move_ids.plant_request)
        self.assertEqual(pick.move_ids.plant_kind_code, "prepare")
        # through Ajustes: the Many2many writes the flag
        settings = self.env["res.config.settings"].create({})
        self.assertIn(depot, settings.plant_warehouse_ids)
        settings.plant_warehouse_ids = [(3, depot.id)]
        settings.set_values()
        self.assertFalse(depot.plant_is_plant)
        self.assertFalse(pick.plant_request)
        self.assertFalse(pick.plant_warehouse_id)

    def test_consolidation_and_production_plan(self):
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 10)
        pick = self._request()
        pick.write({"move_ids": [(0, 0, {"product_id": packed.id, "product_uom_qty": 36, "product_uom": packed.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        bag = pick.move_ids.filtered(lambda m: m.product_id == packed)
        self.assertEqual((bag.plant_kind_code, bag.plant_coffee_line, bag.plant_size, bag.plant_grind), ("packed", "Paz", "340 g", "en grano"))
        self.assertAlmostEqual(bag.plant_kg, 36 * 0.34, places=3)
        self.assertEqual((bag.plant_counterparty, bag.plant_channel_id, bag.plant_warehouse_id), ("Tienda test", self._channel("tiendas"), self.plant))
        coffee = pick.move_ids.filtered(lambda m: m.product_id == self.coffee)
        self.assertAlmostEqual(coffee.plant_kg, 15.0)
        action = self.env["plant.production.plan"].action_open()
        rows = self.env["plant.production.plan"].search(action["domain"])
        paz = rows.filtered(lambda r: r.product_id == packed)
        self.assertEqual((paz.ordered, paz.on_hand, paz.to_produce, paz.plant_warehouse_id, paz.variant_count), (36, 10, 26, self.plant, 1))
        self.assertAlmostEqual(paz.kg_to_roast, 26 * 0.34, places=3)
        cups = rows.filtered(lambda r: r.product_id == self.cups)
        self.assertEqual((cups.ordered, cups.on_hand, cups.to_produce, cups.kg_to_roast), (1000, 300, 700, 0))
        bulk = rows.filtered(lambda r: r.product_id == self.coffee)
        self.assertEqual((bulk.ordered, bulk.kg_ordered, bulk.kg_on_hand, bulk.kg_to_roast), (0, 15.0, 0.0, 15.0))
        supply_line = pick.move_ids.filtered(lambda m: m.product_id == self.cups)
        self.assertFalse(supply_line.plant_coffee_line)

    def test_sheet_matches_the_plant_workbook(self):
        """Manual exception rows and store columns, preparation counted in 2.5 kg bags, inventory from Odoo or typed."""
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO TEST", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 10)
        Row = self.env["plant.sheet.row"]
        r340 = Row.create({"sheet": "tiendas", "sequence": 1, "line": "Paz test", "name": "Paz 340 test", "color": "#FFE599", "grams": 340, "product_ids": [(6, 0, packed.ids)]})
        rprep = Row.create({"sheet": "tiendas", "sequence": 2, "line": "Paz test", "name": "Paz Preparación 2,5 test", "grams": 2500, "product_ids": [(6, 0, self.coffee.ids)]})
        rempty = Row.create({"sheet": "tiendas", "sequence": 3, "line": "Paz test", "name": "Paz 454 test", "grams": 454})
        col = self.env["plant.sheet.column"].create({"sheet": "tiendas", "sequence": 1, "name": "TIENDA T", "warehouse_ids": [(6, 0, self.store.ids)]})
        pick = self._request()   # 15 000 g of coffee for preparation + 1000 cups
        loose = self.env["product.product"].create({"name": "GEISHA 454 G TEST", "type": "consu", "is_storable": True})
        for product, qty in ((packed, 36), (loose, 4)):
            pick.write({"move_ids": [(0, 0, {"product_id": product.id, "product_uom_qty": qty, "product_uom": product.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        key = "c%s" % col.id
        self.assertEqual(data["columns"][0]["key"], key)
        self.assertEqual(data["columns"][0]["name"], "TIENDA T")
        self.assertFalse([c for c in data["columns"] if c["key"] == "w%s" % self.store.id])   # the store is under its alias, not twice
        group = next(g for g in data["groups"] if g["line"] == "Paz test")
        rows = {r["id"]: r for r in group["rows"]}
        self.assertEqual(list(rows), [r340.id, rprep.id, rempty.id])   # empty rows stay, in the plant's order
        paz = rows[r340.id]
        self.assertEqual((paz["cells"][key], paz["total"], paz["inventory"], paz["to_make"], paz["color"]), (36, 36, 10, 26, "#FFE599"))
        self.assertAlmostEqual(paz["kg"], 26 * 0.34, places=3)
        prep = rows[rprep.id]
        self.assertAlmostEqual(prep["cells"][key], 6.0)          # 15 kg = 6 bags of 2.5 kg
        self.assertAlmostEqual(prep["kg"], 15.0)
        self.assertEqual(rows[rempty.id]["total"], 0)
        self.assertAlmostEqual(group["kg"], 26 * 0.34 + 15.0, places=3)   # TOTAL NETO X TOSTAR of the line
        self.assertFalse(data["unmapped"])   # nothing is left without a row
        geisha = next(r for g in data["groups"] for r in g["rows"] if r["auto"] and r["line"] == "Geisha")   # coffee without a manual row gets its automatic row
        self.assertEqual((geisha["name"], geisha["cells"][key], geisha["total"]), ("Geisha 454", 4, 4))
        self.assertAlmostEqual(geisha["kg"], 4 * 0.454, places=3)
        self.assertFalse([r for g in data["groups"] for r in g["rows"] if r["name"].startswith("Vaso")])   # packaging was never part of the workbook
        # the plant types its own inventory; empty goes back to the stock of Odoo
        self.env["plant.sheet"].set_inventory(r340.id, 30)
        paz = next(r for g in self.env["plant.sheet"].get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["id"] == r340.id)
        self.assertEqual((paz["inventory"], paz["inventory_auto"], paz["inventory_manual"], paz["to_make"]), (30, 10, True, 6))
        self.env["plant.sheet"].set_inventory(r340.id, "")
        paz = next(r for g in self.env["plant.sheet"].get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["id"] == r340.id)
        self.assertEqual((paz["inventory"], paz["inventory_manual"]), (10, False))

    def test_other_orders_have_one_column_per_order_and_kits_explode(self):
        partner = self.env["res.partner"].create({"name": "Cliente otros test"})
        packed = self.env["product.product"].create({"name": "LIBRE 340 G TEST", "type": "consu", "is_storable": True})
        kit = self.env["product.product"].create({"name": "KIT TEST", "type": "consu", "is_storable": True})
        Row = self.env["plant.sheet.row"]
        lib = Row.create({"sheet": "otros", "line": "LIBRE T", "name": "LIBRE 340 GRANO T", "grams": 340, "product_ids": [(6, 0, packed.ids)]})
        out_type = self.plant.out_type_id
        picks = self.env["stock.picking"]
        for qty in (10, 5):
            picks |= self.env["stock.picking"].create({
                "picking_type_id": out_type.id, "partner_id": partner.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "move_ids": [(0, 0, {"product_id": packed.id, "product_uom_qty": qty, "product_uom": packed.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.env.ref("stock.stock_location_customers").id})],
            })
        self.assertTrue(all(p.plant_channel == "otros" for p in picks))
        data = self.env["plant.sheet"].get_data(sheet="otros")
        mine = [c for c in data["columns"] if c["picking_id"] in picks.ids]
        self.assertEqual(len(mine), 2)   # same customer, two orders = two columns, like the workbook
        self.assertTrue(all(c["name"] == "CLIENTE OTROS TEST" and c["date"] for c in mine))
        row = next(r for g in data["groups"] for r in g["rows"] if r["id"] == lib.id)
        self.assertEqual((row["total"], row["inventory"], row["to_make"]), (15, None, 15))   # no inventory here: everything is roasted
        self.assertAlmostEqual(row["kg"], 15 * 0.34, places=3)
        # Attenza kit: the components receive kit quantity x factor
        kit_row = Row.create({"sheet": "attenza", "line": "KIT T", "name": "KIT T", "product_ids": [(6, 0, kit.ids)], "units_per_box": 4})
        comp = Row.create({"sheet": "attenza", "line": "KIT T", "name": "PAZ 200 T", "grams": 200, "parent_id": kit_row.id, "factor": 2})
        pricelist = self.env["product.pricelist"].create({"name": "Attenza test"})
        self._channel("attenza").pricelist_ids = [(4, pricelist.id)]
        so = self.env["sale.order"].create({"partner_id": partner.id, "pricelist_id": pricelist.id, "warehouse_id": self.plant.id, "order_line": [(0, 0, {"product_id": kit.id, "product_uom_qty": 5})]})
        so.action_confirm()
        self.assertEqual(so.picking_ids.plant_channel, "attenza")
        att = self.env["plant.sheet"].get_data(sheet="attenza")
        rows = {r["id"]: r for g in att["groups"] for r in g["rows"]}
        self.assertEqual(rows[kit_row.id]["total"], 5)
        self.assertEqual(rows[kit_row.id]["boxes"], 2)
        self.assertEqual(rows[comp.id]["total"], 10)
        self.assertAlmostEqual(rows[comp.id]["kg"], 2.0)

    def test_workbook_rows_and_channels_are_seeded(self):
        rows = self.env["plant.sheet.row"].search([("is_auto", "=", False)])
        self.assertEqual(set(rows.mapped("sheet")), {"tiendas", "otros", "attenza"})
        self.assertEqual(self.env["plant.sheet"].get_tabs(), [["tiendas", "PEDIDOS TIENDAS"], ["otros", "OTROS PEDIDOS"], ["attenza", "ATTENZA"]])   # the CAFE tab is gone
        paz = self.env.ref("plant_request_board.row_t_paz_prep")
        self.assertEqual((paz.name, paz.grams, paz.line, paz.exception), ("Paz Preparación 2.5", 2500, "Paz", False))   # a legacy plain row: kept, inert
        kit = self.env.ref("plant_request_board.row_a_kit_lp_gra")
        self.assertTrue(kit.exception and kit.child_ids)   # kits keep working
        line = self.env["plant.coffee.line"].search([("name", "=ilike", "paz")])
        self.assertEqual((len(line), line.color), (1, "#FFFFFF"))
        self.assertEqual(self.env["plant.coffee.line"].search([("name", "=ilike", "libre")]).color, "#FFE599")   # the colour of the workbook
        evento = self.env.ref("plant_request_board.col_tiendas_evento")
        self.assertEqual(evento.name, "EVENTO")
        channels = self.env["plant.channel"].search([])
        self.assertEqual(channels.mapped("code"), ["ecommerce", "attenza", "alianzas", "eventos", "tiendas", "otros"])   # order of evaluation
        self.assertEqual((self._channel("tiendas").fallback, self._channel("otros").fallback), ("internal", "outgoing"))
        self.assertEqual(self.env["plant.sheet"]._sheet_channels("tiendas"), self._channel("eventos") | self._channel("tiendas"))

    def test_products_are_classified_on_create_and_fields_drive_everything(self):
        """The classifier fills the plant fields when the product is created; from then on the lines read the
        fields, and editing them (not the name) changes what the plant sees."""
        bag = self.env["product.product"].create({"name": "PAZ 340 G MOLIDO", "type": "consu", "is_storable": True})
        tmpl = bag.product_tmpl_id
        self.assertEqual((tmpl.plant_kind_code, tmpl.plant_coffee_line_id.name, tmpl.plant_net_grams, tmpl.plant_grind, tmpl.plant_in_sheet, tmpl.plant_manual), ("packed", "Paz", 340, "ground", True, False))
        self.assertEqual((self.coffee.product_tmpl_id.plant_kind_code, self.coffee.product_tmpl_id.plant_net_grams), ("prepare", 0))
        self.assertEqual((self.cups.product_tmpl_id.plant_kind_code, self.cups.product_tmpl_id.plant_in_sheet), ("supply", False))
        pick = self._transfer(self.plant, self.store, [(bag, 10)])
        line = pick.move_ids
        self.assertEqual((line.plant_kind_code, line.plant_coffee_line, line.plant_size, line.plant_grind), ("packed", "Paz", "340 g", "molido"))
        self.assertAlmostEqual(line.plant_kg, 3.4)
        tmpl.write({"plant_net_grams": 400, "plant_grind": "beans"})   # the plant corrects the product: reviewed, and the open line follows at once
        self.assertTrue(tmpl.plant_manual)
        self.assertEqual((line.plant_size, line.plant_grind), ("400 g", "en grano"))
        self.assertAlmostEqual(line.plant_kg, 4.0)
        tmpl.name = "PAZ 500 G MOLIDO"   # a reviewed product ignores its name
        self.assertEqual(tmpl.plant_net_grams, 400)
        auto = self.env["product.product"].create({"name": "LIBRE 200 G EN GRANO", "type": "consu", "is_storable": True}).product_tmpl_id
        auto.name = "LIBRE 227 G EN GRANO"   # an automatic one follows its name
        self.assertEqual(auto.plant_net_grams, 227)

    def test_new_product_gets_its_row_at_once(self):
        """A new presentation ordered by a store has its row in the sheet without any configuration."""
        new = self.env["product.product"].create({"name": "LIBRE 227 G MOLIDO", "type": "consu", "is_storable": True})
        pick = self._transfer(self.plant, self.store, [(new, 12)])
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertFalse(data["unmapped"])
        row = next(r for g in data["groups"] for r in g["rows"] if r["name"] == "Libre 227 molido")
        key = "w%s" % self.store.id
        self.assertEqual((row["auto"], row["cells"][key], row["total"], row["inventory"], row["to_make"], row["color"]), (True, 12, 12, 0, 12, "#FFE599"))
        self.assertAlmostEqual(row["kg"], 12 * 0.227, places=3)
        group = next(g for g in data["groups"] if g["line"] == "Libre")
        self.assertAlmostEqual(group["kg"], 12 * 0.227, places=3)
        # grind on the same row when the plant prefers it
        beans = self.env["product.product"].create({"name": "LIBRE 227 G EN GRANO", "type": "consu", "is_storable": True})
        pick.write({"move_ids": [(0, 0, {"product_id": beans.id, "product_uom_qty": 3, "product_uom": beans.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        names = [r["name"] for g in self.env["plant.sheet"].get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["line"] == "Libre"]
        self.assertEqual(names, ["Libre 227 en grano", "Libre 227 molido"])
        self.env["ir.config_parameter"].sudo().set_param("plant_request_board.row_grind", "merge")
        merged = next(r for g in self.env["plant.sheet"].get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["name"] == "Libre 227")
        self.assertEqual(merged["total"], 15)
        # bulk coffee and the bags of the preparation size share the "Preparación" row
        bag25 = self.env["product.product"].create({"name": "BOLSA 2.5 KG - PAZ", "type": "consu", "is_storable": True})
        bag25.product_tmpl_id.write({"plant_kind_id": self.env.ref("plant_request_board.kind_packed").id, "plant_coffee_line_id": self.coffee.product_tmpl_id.plant_coffee_line_id.id, "plant_net_grams": 2500, "plant_in_sheet": True})
        pick.write({"move_ids": [(0, 0, {"product_id": bag25.id, "product_uom_qty": 2, "product_uom": bag25.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id}),
                                 (0, 0, {"product_id": self.coffee.id, "product_uom_qty": 5000, "product_uom": self.coffee.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        prep = next(r for g in self.env["plant.sheet"].get_data(sheet="tiendas")["groups"] for r in g["rows"] if r["name"] == "Paz Preparación 2.5")
        self.assertEqual(prep["total"], 4)   # 2 bags + 5 kg = 2 bags
        self.assertAlmostEqual(prep["kg"], 10.0)

    def test_barcode_variant_adds_up_in_its_master(self):
        """The duplicate finder groups the variants, the plant assigns the master, and the variants add up in the
        master's row and plan line (stock included). Nothing is deleted."""
        master = self.env["product.product"].create({"name": "PAZ 454 G EN GRANO", "type": "consu", "is_storable": True})
        barcode = self.env["product.product"].create({"name": "PAZ 454 G EN GRANO CON CODIGO DE BARRAS", "type": "consu", "is_storable": True})
        odd = self.env["product.product"].create({"name": "PAZ454CB", "type": "consu", "is_storable": True})   # a name the classifier cannot read
        self.assertEqual(odd.product_tmpl_id.plant_kind_code, "supply")
        self.env["stock.quant"]._update_available_quantity(master, self.plant.lot_stock_id, 10)
        self.env["stock.quant"]._update_available_quantity(barcode, self.plant.lot_stock_id, 5)
        pick = self._transfer(self.plant, self.store, [(master, 20), (barcode, 8), (odd, 2)])
        wiz = self.env["plant.duplicate.wizard"].create({})
        wiz.action_scan()
        group = wiz.line_ids.filtered(lambda l: l.product_tmpl_id in (master | barcode).product_tmpl_id)
        self.assertEqual(len(group), 2)
        self.assertEqual(len(set(group.mapped("group_seq"))), 1)
        self.assertEqual(group.filtered("is_master").product_tmpl_id, master.product_tmpl_id)
        self.assertEqual(group.filtered(lambda l: not l.is_master).master_id, master.product_tmpl_id)
        # the plant adds the unreadable one to the group by hand, then applies
        wiz.line_ids.filtered(lambda l: l.product_tmpl_id == odd.product_tmpl_id).unlink()
        wiz.write({"line_ids": [(0, 0, {"group_seq": 99, "group": "manual", "product_tmpl_id": odd.product_tmpl_id.id, "master_id": master.product_tmpl_id.id})]})
        wiz.action_apply()
        self.assertEqual((barcode.product_tmpl_id.plant_master_id, odd.product_tmpl_id.plant_master_id), (master.product_tmpl_id, master.product_tmpl_id))
        self.assertTrue(barcode.active and odd.active)
        self.assertEqual(odd.product_tmpl_id._plant_values()["kind"], "packed")   # follows its master
        line = pick.move_ids.filtered(lambda m: m.product_id == odd)
        self.assertEqual((line.plant_kind_code, line.plant_coffee_line, line.plant_size), ("packed", "Paz", "454 g"))
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        row = next(r for g in data["groups"] for r in g["rows"] if r["name"] == "Paz 454 en grano")
        self.assertEqual((row["total"], row["inventory"], row["to_make"], row["products"]), (30, 15, 15, 3))
        rows = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open()["domain"])
        paz = rows.filtered(lambda r: r.product_tmpl_id == master.product_tmpl_id)
        self.assertEqual((len(paz), paz.product_id, paz.variant_count, paz.ordered, paz.on_hand, paz.to_produce), (1, master, 3, 30, 15, 15))
        self.assertFalse(rows.filtered(lambda r: r.product_tmpl_id in (barcode | odd).product_tmpl_id))
        with self.assertRaises(Exception):   # no chains: a master has no master
            master.product_tmpl_id.plant_master_id = odd.product_tmpl_id

    def test_attenza_products_have_their_rows(self):
        """B. ROJO 340 G, DECAF PAZ 454 G and IMPACTO 340 G EN GRANO add up in ATTENZA without any row configured."""
        products = self.env["product.product"].create([{"name": n, "type": "consu", "is_storable": True} for n in ("B. ROJO 340 G", "DECAF PAZ 454 G", "IMPACTO 340 G EN GRANO")])
        self.assertEqual(products.mapped("product_tmpl_id.plant_coffee_line_id.name"), ["B. Rojo", "Decaf", "Impacto"])
        partner = self.env["res.partner"].create({"name": "Attenza test"})
        pricelist = self.env["product.pricelist"].create({"name": "Attenza test"})
        self._channel("attenza").pricelist_ids = [(4, pricelist.id)]
        so = self.env["sale.order"].create({"partner_id": partner.id, "pricelist_id": pricelist.id, "warehouse_id": self.plant.id, "order_line": [(0, 0, {"product_id": p.id, "product_uom_qty": 6}) for p in products]})
        so.action_confirm()
        data = self.env["plant.sheet"].get_data(sheet="attenza")
        self.assertFalse(data["unmapped"])
        rows = {r["name"]: r for g in data["groups"] for r in g["rows"] if r["total"]}
        self.assertEqual(set(rows), {"B. Rojo 340", "Decaf 454", "Impacto 340 en grano"})
        self.assertTrue(all(r["total"] == 6 and r["auto"] for r in rows.values()))
        self.assertAlmostEqual(data["totals"]["kg"], 6 * (0.34 + 0.454 + 0.34), places=3)

    def test_fill_wizard_previews_then_applies(self):
        """The classifier's proposal is shown and corrected before anything is written."""
        odd = self.env["product.product"].create({"name": "XZ 454 PRUEBA", "type": "consu", "is_storable": True})   # an unknown line: unreadable
        odd.product_tmpl_id.with_context(plant_auto=True).write({"plant_kind_id": False})
        self.assertFalse(odd.product_tmpl_id.plant_kind_id)
        wiz = self.env["plant.product.fill.wizard"].create({"scope": "unclassified", "only_changes": False})
        wiz.action_preview()
        line = wiz.line_ids.filtered(lambda l: l.product_tmpl_id == odd.product_tmpl_id)
        self.assertEqual((wiz.state, line.kind_id.code, line.changed), ("preview", "supply", True))
        self.assertFalse(odd.product_tmpl_id.plant_kind_id)   # nothing written yet
        paz = self.env["plant.coffee.line"].search([("name", "=ilike", "paz")])
        line.write({"kind_id": self.env.ref("plant_request_board.kind_packed").id, "line_id": paz.id, "grams": 454, "grind": "beans", "in_sheet": True})
        wiz.action_apply()
        tmpl = odd.product_tmpl_id
        self.assertEqual((wiz.state, wiz.applied_count, tmpl.plant_kind_code, tmpl.plant_coffee_line_id, tmpl.plant_net_grams, tmpl.plant_grind, tmpl.plant_in_sheet, tmpl.plant_manual), ("done", 1, "packed", paz, 454, "beans", True, True))
        # a single origin in the finished-goods category names a new line: the classifier creates it on its own
        finished = self.env["product.category"].create({"name": "Producto terminado test"})
        single = self.env["product.product"].create({"name": "FINCA EL VERGEL 250 G", "type": "consu", "is_storable": True, "categ_id": finished.id})
        self.assertEqual((single.product_tmpl_id.plant_kind_code, single.product_tmpl_id.plant_coffee_line_id.name, single.product_tmpl_id.plant_net_grams), ("packed", "Finca El Vergel", 250))
        cheese = self.env["product.product"].create({"name": "QUESO MOZZARELLA 500 G", "type": "consu", "is_storable": True})   # a weight outside that category is not coffee
        self.assertEqual((cheese.product_tmpl_id.plant_kind_code, cheese.product_tmpl_id.plant_coffee_line_id.name), ("supply", False))
        # a new line named in the preview is created on apply
        wiz2 = self.env["plant.product.fill.wizard"].create({"scope": "selected", "only_changes": False, "product_tmpl_ids": [(6, 0, single.product_tmpl_id.ids)]})
        wiz2.action_preview()
        wiz2.line_ids.write({"line_id": False, "line_name": "Microlotes"})
        wiz2.action_apply()
        self.assertEqual(single.product_tmpl_id.plant_coffee_line_id.name, "Microlotes")

    def test_negative_stock_never_adds_to_roasting(self):
        """kg a tostar = max(0, kg pedidos − max(0, inventario)): a negative stock in Odoo counts as zero and is
        shown as a warning, in the plan and in the sheet. 10 kg ordered with −50 kg in Odoo → roast 10, not 60."""
        self.env["stock.quant"]._update_available_quantity(self.coffee, self.plant.lot_stock_id, -50000)
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, -5)
        self._transfer(self.plant, self.store, [(self.coffee, 10000), (packed, 36)])
        rows = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open()["domain"])
        bulk = rows.filtered(lambda r: r.product_id == self.coffee)
        self.assertEqual((bulk.kg_ordered, bulk.kg_on_hand, bulk.kg_on_hand_raw, bulk.kg_to_roast, bulk.negative_stock), (10.0, 0.0, -50.0, 10.0, True))
        self.assertIn("Inventario negativo en Odoo (-50.00 kg)", bulk.stock_note)
        bags = rows.filtered(lambda r: r.product_id == packed)
        self.assertEqual((bags.ordered, bags.on_hand, bags.on_hand_raw, bags.to_produce, bags.negative_stock), (36, 0, -5, 36, True))
        self.assertAlmostEqual(bags.kg_to_roast, 36 * 0.34, places=3)
        self.assertAlmostEqual(sum(rows.mapped("kg_to_roast")), 10.0 + 36 * 0.34, places=3)
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        prep = next(r for g in data["groups"] for r in g["rows"] if r["name"] == "Paz Preparación 2.5")
        self.assertEqual((prep["inventory"], prep["inventory_raw"], prep["negative"], prep["to_make"]), (0.0, -20.0, True, 4.0))   # −50 kg = −20 bags of 2.5 kg, counted as 0
        self.assertAlmostEqual(prep["kg"], 10.0)
        bag_row = next(r for g in data["groups"] for r in g["rows"] if r["name"] == "Paz 340 en grano")
        self.assertEqual((bag_row["inventory"], bag_row["inventory_raw"], bag_row["negative"], bag_row["to_make"]), (0.0, -5.0, True, 36.0))
        self.assertEqual(data["negative_rows"], 2)
        self.assertAlmostEqual(data["totals"]["kg"], data["plan_kg"], places=3)   # the same open orders: sheet and plan agree
        self.assertIn("Plan de tostión", self.env["plant.production.plan"]._comparison_text())

    def test_sheet_and_plan_agree_and_explain_their_difference(self):
        """For store orders alone the TOTAL NETO X TOSTAR of the sheet equals the plan; an OTROS order shows the
        documented difference (the plan discounts stock on every channel, the sheet only in PEDIDOS TIENDAS)."""
        packed = self.env["product.product"].create({"name": "LIBRE 454 G MOLIDO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 10)
        self._transfer(self.plant, self.store, [(packed, 30)])
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertAlmostEqual(data["totals"]["kg"], 20 * 0.454, places=3)
        self.assertAlmostEqual(data["plan_kg"], 20 * 0.454, places=3)
        partner = self.env["res.partner"].create({"name": "Cliente otros test"})
        self.env["stock.picking"].create({
            "picking_type_id": self.plant.out_type_id.id, "partner_id": partner.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [(0, 0, {"product_id": packed.id, "product_uom_qty": 5, "product_uom": packed.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.env.ref("stock.stock_location_customers").id})],
        })
        tiendas = self.env["plant.sheet"].get_data(sheet="tiendas")
        otros = self.env["plant.sheet"].get_data(sheet="otros")
        self.assertAlmostEqual(tiendas["totals"]["kg"] + otros["totals"]["kg"], 25 * 0.454, places=3)   # the sheet roasts OTROS in full
        self.assertAlmostEqual(tiendas["plan_kg"], 25 * 0.454, places=3)                                # the plan: 35 ordered − 10 in stock
        text = self.env["plant.production.plan"]._comparison_text()
        self.assertIn("PEDIDOS TIENDAS", text)
        self.assertIn("Difieren por diseño", text)
        self.assertEqual(self.env["plant.production.plan"].action_compare_with_sheet()["params"]["message"], text)

    def test_request_is_read_from_the_locations_not_the_operation_type(self):
        """A store's own internal transfer or receipt whose source is a plant location is a request; a transfer
        between two stores is not."""
        laureles = self.env["stock.warehouse"].create({"name": "Laureles Medellín test", "code": "TLAU"})
        wework = self.env["stock.warehouse"].create({"name": "Wework Medellin test", "code": "TWEW"})
        rivana = self.env["stock.warehouse"].create({"name": "COM - Mercado Libre - Rivana test", "code": "TMLR"})
        own_internal = self.env["stock.picking"].create({   # LAUME/INT/…: the store's internal type, source PLANT/Existencias
            "picking_type_id": laureles.int_type_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": laureles.lot_stock_id.id,
            "move_ids": [(0, 0, {"product_id": self.coffee.id, "product_uom_qty": 2000, "product_uom": self.coffee.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": laureles.lot_stock_id.id})],
        })
        self.assertEqual((own_internal.plant_request, own_internal.plant_channel, own_internal.plant_store_id, own_internal.plant_warehouse_id), (True, "tiendas", laureles, self.plant))
        self.assertTrue(laureles.plant_is_store)
        receipt = self.env["stock.picking"].create({   # the store's receipt type, source PLANT/Existencias
            "picking_type_id": wework.in_type_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": wework.lot_stock_id.id,
            "move_ids": [(0, 0, {"product_id": self.coffee.id, "product_uom_qty": 1000, "product_uom": self.coffee.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": wework.lot_stock_id.id})],
        })
        self.assertEqual((receipt.plant_request, receipt.plant_channel, receipt.plant_store_id), (True, "tiendas", wework))
        mercado = self._transfer(self.plant, rivana, [(self.coffee, 1000)])
        self.assertEqual((mercado.plant_channel, mercado.plant_counterparty), ("tiendas", "COM - Mercado Libre - Rivana test"))   # a name says nothing: no rule matches, so it is a store
        between_stores = self.env["stock.picking"].create({
            "picking_type_id": laureles.int_type_id.id, "location_id": laureles.lot_stock_id.id, "location_dest_id": wework.lot_stock_id.id,
            "move_ids": [(0, 0, {"product_id": self.coffee.id, "product_uom_qty": 500, "product_uom": self.coffee.uom_id.id, "location_id": laureles.lot_stock_id.id, "location_dest_id": wework.lot_stock_id.id})],
        })
        self.assertFalse(between_stores.plant_request)
        # delivered requests keep their store as a column under "Todos los pedidos"
        receipt.action_confirm()
        receipt.move_ids.quantity = 1000
        receipt.button_validate()
        self.assertEqual((receipt.state, receipt.plant_stage), ("done", "delivered"))
        names_open = [c["name"] for c in self.env["plant.sheet"].get_data(sheet="tiendas", scope="open")["columns"]]
        names_all = [c["name"] for c in self.env["plant.sheet"].get_data(sheet="tiendas", scope="all")["columns"]]
        self.assertIn("WEWORK MEDELLIN TEST", names_open)   # a flagged store always has its column
        self.assertIn("WEWORK MEDELLIN TEST", names_all)
        self.assertIn("COM - MERCADO LIBRE - RIVANA TEST", names_all)

    def test_production_products_get_their_rows_and_kinds(self):
        """The products the plant found without a row in production: each one classified and added up."""
        finished = self.env["product.category"].create({"name": "Producto terminado test"})
        gram = self.env.ref("uom.product_uom_gram").id
        Product = self.env["product.product"]
        lata = Product.create({"name": "LATA COLD BREW 269 ML", "default_code": "LATCOLBRE269ML", "type": "consu", "is_storable": True, "categ_id": finished.id})
        botella = Product.create({"name": "COLD BREW 750 ML (copia)", "type": "consu", "is_storable": True, "categ_id": finished.id})
        omb = Product.create({"name": "OMBLIGON 340 G", "default_code": "OMB340G", "type": "consu", "is_storable": True, "categ_id": finished.id})
        cold = Product.create({"name": "CAFE EN GRANO PARA PREPARAR - COLD BREW", "default_code": "CAFENGRAPARPRECOLBRE", "type": "consu", "is_storable": True, "uom_id": gram})
        muestra = Product.create({"name": "MUESTRA PAZ 150 G", "type": "consu", "is_storable": True})
        paz454 = Product.create({"name": "PAZ 454 G EN GRANO", "type": "consu", "is_storable": True})
        supplies = Product.create([{"name": n, "default_code": c, "type": "consu", "is_storable": True} for c, n in (
            ("PAPSAN", "PAPEL SANITARIO"), ("TAPVASAZU9ONZ", "TAPA VASO AZUL 9 ONZAS"), ("BOLKRAPEQ", "BOLSA KRAFT PEQUEÑA"), ("PAPPARPAS", "PAPEL PARA PASTELERIA"), ("BOLKRAMEDVER", "BOLSA KRAFT MEDIANA VERTICAL"))])
        t = lambda p: p.product_tmpl_id  # noqa: E731
        self.assertEqual((t(lata).plant_kind_code, t(lata).plant_net_grams, t(lata).plant_in_sheet), ("ready", 0, True))
        self.assertEqual(t(botella).plant_kind_code, "ready")
        self.assertEqual((t(omb).plant_kind_code, t(omb).plant_coffee_line_id.name, t(omb).plant_net_grams), ("packed", "Ombligon", 340))
        self.assertEqual((t(cold).plant_kind_code, t(cold).plant_coffee_line_id.name), ("prepare", "Cold Brew"))
        self.assertEqual((t(muestra).plant_kind_code, t(muestra).plant_coffee_line_id.name, t(muestra).plant_net_grams), ("packed", "Paz", 150))
        self.assertEqual((t(paz454).plant_kind_code, t(paz454).plant_coffee_line_id.name, t(paz454).plant_net_grams, t(paz454).plant_grind), ("packed", "Paz", 454, "beans"))
        self.assertTrue(all(p.product_tmpl_id.plant_kind_code == "supply" and not p.product_tmpl_id.plant_in_sheet for p in supplies))
        sura = self.env["stock.warehouse"].create({"name": "Sura test", "code": "TSUR"})
        pick = self._transfer(self.plant, sura, [(lata, 24), (botella, 6), (omb, 10), (cold, 73634), (muestra, 5), (paz454, 8)] + [(p, 3) for p in supplies])
        kg = {m.product_id: m.plant_kg for m in pick.move_ids}
        self.assertEqual((kg[lata], kg[botella]), (0.0, 0.0))
        self.assertAlmostEqual(kg[cold], 73.634)
        self.assertTrue(all(kg[p] == 0.0 for p in supplies))
        self.assertAlmostEqual(pick.plant_coffee_kg, 73.63, places=2)   # only the bulk coffee counts as coffee on the card (two decimals)
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertFalse(data["unmapped"])
        rows = {r["name"]: r["total"] for g in data["groups"] for r in g["rows"]}
        self.assertEqual((rows["Ombligon 340"], rows["Paz 150"], rows["Paz 454 en grano"]), (10, 5, 8))
        self.assertAlmostEqual(rows["Cold Brew Preparación 2.5"], 73.634 / 2.5, places=3)
        ready = {r["name"]: r["total"] for r in data["ready"]}
        self.assertEqual(len(ready), 2)   # two different ready products, two rows, never merged
        self.assertEqual(sorted(ready.values()), [6, 24])
        self.assertFalse([r for g in data["groups"] for r in g["rows"] if r["name"].startswith(("Papel", "Tapa", "Bolsa"))])
        # the duplicate finder does not pair the can with the bottle
        wiz = self.env["plant.duplicate.wizard"].create({})
        wiz.action_scan()
        self.assertFalse(wiz.line_ids.filtered(lambda l: l.product_tmpl_id in (lata | botella).product_tmpl_id))

    def test_duplicates_respect_internal_references_and_boms(self):
        """Same name, different internal references (GEI…, ROCJAV…, BAMA…): a group to review by hand, no master
        proposed. Same reference family: the busiest one is proposed."""
        finished = self.env["product.category"].create({"name": "Producto terminado test"})
        Product = self.env["product.product"]
        geishas = Product.create([{"name": "GEISHA 200 G (copia)", "default_code": c, "type": "consu", "is_storable": True, "categ_id": finished.id} for c in ("GEI200GENGRACAR", "ROCJAV200G", "BAMA200G")])
        imp = Product.create({"name": "IMPACTO 340 G EN GRANO", "default_code": "IMP340GENGRA", "type": "consu", "is_storable": True})
        imp_bc = Product.create({"name": "IMPACTO 340 G EN GRANO CON CODIGO DE BARRAS", "default_code": "IMP340GENGRACONCODDEBAR", "type": "consu", "is_storable": True})
        self._transfer(self.plant, self.store, [(imp_bc, 2)]).action_cancel()
        done = self._transfer(self.plant, self.store, [(imp, 4)])
        done.action_confirm()
        done.move_ids.quantity = 4
        done.button_validate()
        wiz = self.env["plant.duplicate.wizard"].create({})
        wiz.action_scan()
        group = wiz.line_ids.filtered(lambda l: l.product_tmpl_id in geishas.product_tmpl_id)
        self.assertEqual(len(group), 3)
        self.assertTrue(all(l.review and not l.master_id and not l.is_master and not l.apply for l in group))
        self.assertIn("GEI, ROCJAV", group[0].review_reason)
        impacto = wiz.line_ids.filtered(lambda l: l.product_tmpl_id in (imp | imp_bc).product_tmpl_id)
        self.assertEqual(len(impacto), 2)
        self.assertFalse(any(impacto.mapped("review")))
        self.assertEqual(impacto.filtered("is_master").product_tmpl_id, imp.product_tmpl_id)   # the one that moved
        wiz.action_apply()
        self.assertEqual(imp_bc.product_tmpl_id.plant_master_id, imp.product_tmpl_id)
        self.assertFalse(any(geishas.mapped("product_tmpl_id.plant_master_id")))
        if "mrp.bom" in self.env:   # the same reference family but different components: review
            a = Product.create({"name": "PUNK 200 G", "default_code": "PUN200GA", "type": "consu", "is_storable": True})
            b = Product.create({"name": "PUNK 200 G (copia)", "default_code": "PUN200GB", "type": "consu", "is_storable": True})
            other_coffee = Product.create({"name": "CAFE TOSTADO A GRANEL - PUNK", "type": "consu", "is_storable": True, "uom_id": self.coffee.uom_id.id})
            self.env["mrp.bom"].create({"product_tmpl_id": a.product_tmpl_id.id, "product_qty": 1, "bom_line_ids": [(0, 0, {"product_id": self.coffee.id, "product_qty": 200})]})
            self.env["mrp.bom"].create({"product_tmpl_id": b.product_tmpl_id.id, "product_qty": 1, "bom_line_ids": [(0, 0, {"product_id": other_coffee.id, "product_qty": 200})]})
            wiz2 = self.env["plant.duplicate.wizard"].create({})
            wiz2.action_scan()
            punk = wiz2.line_ids.filtered(lambda l: l.product_tmpl_id in (a | b).product_tmpl_id)
            self.assertTrue(all(punk.mapped("review")))
            self.assertIn("materiales", punk[0].review_reason)

    def test_green_coffee_has_its_own_kind(self):
        """Green coffee (category Cafe verde, sold by weight) is its own kind: never bulk, never in the sheet, no kg
        to roast. Rolls, packaging and infusions are supplies."""
        verde = self.env["product.category"].create({"name": "Cafe verde"})
        gram = self.env.ref("uom.product_uom_gram").id
        green = self.env["product.product"].create({"name": "CAFE VERDE BOURBON AJI LAVADO", "type": "consu", "is_storable": True, "uom_id": gram, "categ_id": verde.id})
        self.assertEqual((green.product_tmpl_id.plant_kind_code, green.product_tmpl_id.plant_in_sheet), ("green", False))
        roll = self.env["product.product"].create({"name": "ROLLO EMPAQUE DRIP PAZ", "type": "consu", "is_storable": True, "uom_id": gram})
        infusion = self.env["product.product"].create({"name": "INFUSION LIBERTARIO", "type": "consu", "is_storable": True, "uom_id": gram})
        self.assertEqual((roll.product_tmpl_id.plant_kind_code, infusion.product_tmpl_id.plant_kind_code), ("supply", "supply"))
        pick = self._transfer(self.plant, self.store, [(green, 30000), (roll, 500)])
        self.assertEqual(pick.move_ids.mapped("plant_kg"), [0.0, 0.0])
        self.assertEqual(pick.plant_coffee_kg, 0.0)
        self.assertIn("Café verde", pick.plant_card_html)
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertFalse(data["unmapped"])
        self.assertFalse([r for g in data["groups"] for r in g["rows"] if "Aji" in r["name"]])
        rows = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open()["domain"])
        self.assertEqual(sum(rows.mapped("kg_to_roast")), 0.0)
        with self.assertRaises(Exception):
            self.env.ref("plant_request_board.kind_green").unlink()

    def test_briefing_is_silent_without_a_key(self):
        """No Anthropic key: new requests are not queued and the cron does nothing; with a key (environment or
        odoo.conf, never the database) they are queued."""
        self.env["ir.config_parameter"].sudo().set_param("plant_request_board.anthropic_api_key", "sk-in-database")   # ignored: the key is not read from the database any more
        with patch.dict(os.environ, {"PLANT_ANTHROPIC_API_KEY": ""}):
            self.assertFalse(self.env["stock.picking"]._plant_ai_enabled())
            pick = self._request()
            self.assertEqual(pick.plant_briefing_state, "none")
            with patch.object(type(self.env["stock.picking"]), "action_plant_briefing") as briefing:
                self.env["stock.picking"]._plant_cron_briefings()
                briefing.assert_not_called()
            settings = self.env["res.config.settings"].create({})
            self.assertFalse(settings.plant_ai_enabled)
        with patch.dict(os.environ, {"PLANT_ANTHROPIC_API_KEY": "sk-test"}):
            self.assertEqual(self.env["stock.picking"]._plant_anthropic_key(), "sk-test")
            self.assertEqual(self._request().plant_briefing_state, "pending")
            self.assertTrue(self.env["res.config.settings"].create({}).plant_ai_enabled)

    def _user(self, login, group_xmlid):
        groups = [self.env.ref("base.group_user").id, self.env.ref(group_xmlid).id]
        field = "group_ids" if "group_ids" in self.env["res.users"]._fields else "groups_id"
        return self.env["res.users"].create({"name": login, "login": login, field: [(6, 0, groups)]})

    def test_inventory_groups_split_the_board_from_the_configuration(self):
        """Inventario / Usuario works the board (ticks, delivery, plan, sheet); Inventario / Administrador owns the
        configuration, the typed inventory and the plan's rows. The module adds no group of its own."""
        self.assertFalse(self.env.ref("plant_request_board.group_plant_user", raise_if_not_found=False))
        self.assertFalse(self.env.ref("plant_request_board.group_plant_manager", raise_if_not_found=False))
        worker = self._user("planta.usuario@local", "stock.group_stock_user")
        boss = self._user("planta.jefe@local", "stock.group_stock_manager")
        self.assertTrue(worker.has_group("stock.group_stock_user"))
        self.assertTrue(boss.has_group("stock.group_stock_user"))
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 50)
        pick = self._transfer(self.plant, self.store, [(packed, 10)])
        # the worker: plan and sheet first (the request is still pending), then ticks and delivery
        Plan = self.env["plant.production.plan"].with_user(worker)
        rows = Plan.search(Plan.action_open()["domain"])
        self.assertTrue(rows)
        self.assertEqual(rows.create_uid, worker)
        with self.assertRaises(Exception):
            rows.with_user(worker).unlink()   # the rows belong to the manager
        data = self.env["plant.sheet"].with_user(worker).get_data(sheet="tiendas")
        self.assertTrue(data["columns"])
        pick.plant_check_ids.with_user(worker).write({"done": True})
        self.assertEqual(pick.plant_stage, "ready")
        with self.assertRaises(Exception):
            self.env["plant.sheet"].with_user(worker).set_inventory(data["groups"][0]["rows"][0]["id"], 5)
        for model, vals in (("plant.channel", {"name": "X", "code": "x"}), ("plant.coffee.line", {"name": "Línea X"}), ("plant.sheet.row", {"name": "Fila X"}), ("plant.sheet.column", {"name": "Col X"})):
            with self.assertRaises(Exception, msg=model):
                self.env[model].with_user(worker).create(vals)
        with self.assertRaises(Exception):
            self._channel("tiendas").with_user(worker).write({"name": "Tiendas 2"})
        self.assertTrue(pick.with_user(worker).action_plant_validate())   # a user without e-mail: the note is still written
        self.assertEqual(pick.state, "done")
        self.assertIn("planta.usuario@local", pick.message_ids[0].body)
        # the boss: everything
        self.env["plant.sheet"].with_user(boss).set_inventory(data["groups"][0]["rows"][0]["id"], 5)
        self.env["plant.coffee.line"].with_user(boss).create({"name": "Línea del jefe"})
        self._channel("tiendas").with_user(boss).write({"color": 3})

    def test_inventory_user_operates_and_only_the_administrator_configures(self):
        """An Inventario / Usuario operates every day (ticks, sheet, plan, note, delivery); only an Inventario /
        Administrador changes the settings, the rows and columns of the sheet and the shrinkage of a line."""
        worker = self._user("inventario.usuario@local", "stock.group_stock_user")
        admin = self._user("inventario.admin@local", "stock.group_stock_manager")
        field = "group_ids" if "group_ids" in self.env["res.users"]._fields else "groups_id"
        admin.write({field: [(4, self.env.ref("base.group_system").id)]})   # the settings form needs the Settings right, as in Odoo
        packed = self.env["product.product"].create({"name": "PAZ 454 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 20)
        pick = self._transfer(self.plant, self.store, [(packed, 6), (self.cups, 10)])
        paz = self.env["plant.coffee.line"].search([("name", "=ilike", "paz")], limit=1)
        self.assertTrue(paz)
        row = self.env["plant.sheet.row"].create({"sheet": "tiendas", "name": "Fila del admin", "grams": 454})
        col = self.env["plant.sheet.column"].create({"sheet": "tiendas", "name": "COL", "warehouse_ids": [(6, 0, self.store.ids)]})
        # the user operates: plan and sheet while the request is pending, then ticks, note and delivery
        Plan = self.env["plant.production.plan"].with_user(worker)
        rows = Plan.search(Plan.action_open()["domain"])
        self.assertTrue(rows)
        self.assertEqual(rows.mapped("create_uid"), worker)
        self.assertTrue(self.env["plant.sheet"].with_user(worker).get_data(sheet="tiendas")["groups"])
        as_worker = pick.with_user(worker)
        as_worker.plant_check_ids.write({"done": True})
        self.assertEqual(pick.plant_stage, "ready")
        self.assertIn(pick.name, self.env["ir.actions.report"].with_user(worker)._render_qweb_html(self.env.ref("plant_request_board.action_report_plant_delivery_note").report_name, pick.ids)[0].decode())
        self.assertTrue(as_worker.action_plant_validate())
        self.assertEqual(pick.state, "done")
        # the user cannot configure
        for action in (
            lambda: paz.with_user(worker).write({"shrinkage": 18.0}),
            lambda: row.with_user(worker).write({"grams": 500}),
            lambda: col.with_user(worker).write({"name": "COL 2"}),
            lambda: self.env["plant.sheet"].with_user(worker).set_inventory(row.id, 3),
            lambda: self.env["res.config.settings"].with_user(worker).create({"plant_prep_bag_grams": 3000}).execute(),
            lambda: self._channel("tiendas").with_user(worker).write({"sequence": 1}),
            lambda: self.env["plant.product.fill.wizard"].with_user(worker).create({}),
        ):
            with self.assertRaises(Exception):
                action()
        self.assertEqual((paz.shrinkage, row.grams, col.name), (0.0, 454, "COL"))
        # the administrator configures
        paz.with_user(admin).write({"shrinkage": 18.0})
        row.with_user(admin).write({"grams": 500})
        col.with_user(admin).write({"name": "COL 2", "hidden": True})
        self.env["plant.sheet"].with_user(admin).set_inventory(row.id, 3)
        settings = self.env["res.config.settings"].with_user(admin).create({"plant_prep_bag_grams": 3000, "plant_default_shrinkage": 15.0})
        settings.execute()
        self.assertEqual(self.env["res.config.settings"]._plant_get_float("plant_prep_bag_grams"), 3000.0)
        self.assertEqual((paz.shrinkage, row.grams, row.inventory_manual, col.name, col.hidden), (18.0, 500, 3.0, "COL 2", True))

    def test_ticks_never_change_quantities(self):
        """A tick per line × presentation, who and when; nothing else moves: quantities, moves and stock stay."""
        bag = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        bag_bc = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO CON CODIGO DE BARRAS", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(bag, self.plant.lot_stock_id, 12)
        pick = self._transfer(self.plant, self.store, [(self.coffee, 5000), (bag, 10), (bag_bc, 2), (self.cups, 100)])
        checks = pick.plant_check_ids.sorted("sequence")
        self.assertEqual(checks.mapped("name"), ["Paz 340 en grano", "Paz Preparación 2.5", "Vaso Azul 9 oz"])   # line × presentation, supplies by product
        self.assertEqual(checks.mapped("qty_text"), ["12", "5 kg", "100"])
        self.assertEqual(set(checks.filtered(lambda c: c.name == "Paz 340 en grano").move_ids.product_id.ids), {bag.id, bag_bc.id})
        self.assertEqual((pick.plant_check_count, pick.plant_check_done, pick.plant_progress), (3, 0, 0))
        before = {m.id: (m.product_uom_qty, m.quantity, m.state) for m in pick.move_ids}
        stock_before = bag.with_context(location=self.plant.lot_stock_id.id).qty_available
        first = checks[0]
        first.done = True
        self.assertEqual((first.done_by, bool(first.done_date)), (self.env.user, True))
        self.assertEqual({m.id: (m.product_uom_qty, m.quantity, m.state) for m in pick.move_ids}, before)
        self.assertEqual(bag.with_context(location=self.plant.lot_stock_id.id).qty_available, stock_before)
        self.assertEqual((pick.plant_check_done, pick.plant_progress), (1, 33))
        first.done = False
        self.assertEqual((first.done_by.id, first.done_date), (False, False))
        # the ticks follow the lines: a new line gets its tick, a removed line loses it, the others keep their state
        checks[1].done = True
        pick.write({"move_ids": [(0, 0, {"product_id": bag.id, "product_uom_qty": 1, "product_uom": bag.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})]})
        self.assertEqual(pick.plant_check_ids.filtered(lambda c: c.name == "Paz 340 en grano").qty_text, "13")
        self.assertTrue(pick.plant_check_ids.filtered(lambda c: c.name == "Paz Preparación 2.5").done)
        pick.move_ids.filtered(lambda m: m.product_id == self.cups).unlink()
        self.assertEqual(pick.plant_check_ids.mapped("name"), ["Paz 340 en grano", "Paz Preparación 2.5"])

    def test_stages_follow_the_ticks_and_the_transfer(self):
        """Nueva → En alistamiento (first tick) → Lista para despachar (all ticks) → Entregada (validation). A stage
        fixed by hand holds until the ticks change; Entregada and Cancelada cannot be set by hand."""
        pick = self._request()
        self.assertEqual(pick.plant_stage, "new")
        pick.action_confirm()
        pick.action_assign()   # the reservation of Odoo no longer moves the stage
        self.assertEqual(pick.plant_stage, "new")
        checks = pick.plant_check_ids.sorted("sequence")
        checks[0].done = True
        self.assertEqual(pick.plant_stage, "preparing")
        checks[1].done = True
        self.assertEqual(pick.plant_stage, "ready")
        checks[1].done = False
        self.assertEqual(pick.plant_stage, "preparing")
        pick.plant_stage = "ready"   # by hand, before the last tick
        self.assertEqual((pick.plant_stage, pick.plant_stage_manual_progress), ("ready", "1/2"))
        pick.action_assign()
        self.assertEqual(pick.plant_stage, "ready")   # holds while the ticks do not change
        checks[0].done = False
        self.assertEqual(pick.plant_stage, "new")     # the ticks changed: back to what they say
        with self.assertRaises(Exception):
            pick.plant_stage = "delivered"
        with patch.object(type(self.env["bus.bus"]), "_sendone") as sendone:
            self.env["ir.config_parameter"].sudo().set_param(ICP_PLANT_USERS, str(self.env.user.id))
            checks[0].done = True
            channels = [call[0][1] for call in sendone.call_args_list]
            self.assertIn("plant_request_board/update", channels)   # the plant views reload in place
        pick.action_cancel()
        self.assertEqual(pick.plant_stage, "cancelled")

    def test_prepared_and_delivered_requests_leave_the_active_sheet(self):
        """The active sheet and the plan count Nueva and En alistamiento; Lista and Despachadas have their own scope."""
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 40)
        pick = self._transfer(self.plant, self.store, [(packed, 36)])
        other = self._transfer(self.plant, self.store, [(packed, 4)])
        Sheet = self.env["plant.sheet"]
        row = lambda scope: next((r for g in Sheet.get_data(sheet="tiendas", scope=scope)["groups"] for r in g["rows"] if r["name"] == "Paz 340 en grano"), None)  # noqa: E731
        self.assertEqual(row("open")["total"], 40)
        pick.plant_check_ids.write({"done": True})   # every line ticked: prepared
        self.assertEqual(pick.plant_stage, "ready")
        self.assertEqual((row("open")["total"], row("ready")["total"], row("all")["total"]), (4, 36, 40))
        plan = self.env["plant.production.plan"]
        self.assertEqual(plan.search(plan.action_open()["domain"]).filtered(lambda r: r.product_id == packed).ordered, 4)
        pick.action_plant_validate()
        self.assertEqual((pick.state, pick.plant_stage), ("done", "delivered"))
        self.assertEqual((row("open")["total"], row("ready"), row("delivered")["total"]), (4, None, 36))
        self.assertEqual(Sheet.get_scopes()[0][0], "open")
        self.assertEqual([c for c in Sheet.get_data(sheet="otros", scope="all")["columns"]], [])   # no OTROS orders here
        # the ticks of one cell of the sheet, toggled from the sheet
        cell = row("open")["checks"]["w%s" % self.store.id] if "w%s" % self.store.id in row("open")["checks"] else next(iter(row("open")["checks"].values()))
        self.assertEqual(cell[:2], [0, 1])
        Sheet.toggle_checks(cell[2], True)
        self.assertEqual(other.plant_stage, "ready")
        self.assertEqual(other.plant_check_ids.done_by, self.env.user)

    def test_validate_from_the_board_delivers_and_notes(self):
        """Validar entrega: the standard validation with the user's rights, the lines delivered in full, a note in
        the chatter, the stage Entregada; a user without stock rights is refused."""
        packed = self.env["product.product"].create({"name": "LIBRE 454 G MOLIDO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 20)
        pick = self._transfer(self.plant, self.store, [(packed, 8), (self.cups, 10)])
        pick.plant_check_ids.write({"done": True})   # every line ticked and stock enough: direct validation
        before = len(pick.message_ids)
        res = pick.action_plant_validate()
        self.assertTrue(res)
        self.assertEqual((pick.state, pick.plant_stage), ("done", "delivered"))
        self.assertEqual(pick.move_ids.mapped("quantity"), [8, 10])
        self.assertEqual(packed.with_context(location=self.plant.lot_stock_id.id).qty_available, 12)
        self.assertEqual(len(pick.message_ids), before + 1)
        self.assertIn("Entrega validada desde Planta", pick.message_ids[0].body)
        with self.assertRaises(Exception):
            pick.action_plant_validate()   # already delivered
        nobody = self.env["res.users"].create({"name": "Sin permisos", "login": "nobody.test@local", "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]}) if "groups_id" in self.env["res.users"]._fields else \
            self.env["res.users"].create({"name": "Sin permisos", "login": "nobody.test@local", "group_ids": [(6, 0, [self.env.ref("base.group_user").id])]})
        other = self._transfer(self.plant, self.store, [(packed, 1)])
        with self.assertRaises(Exception):
            other.with_user(nobody).action_plant_validate()
        self.assertEqual(other.state, "draft")

    def test_validation_asks_before_delivering_in_full_or_short(self):
        """Direct validation only when every tick is done or every line has its quantity, and nothing is short;
        otherwise an explicit confirmation listing the lines delivered in full and the shortages."""
        packed = self.env["product.product"].create({"name": "LIBRE 454 G MOLIDO", "type": "consu", "is_storable": True})
        self.env["stock.quant"]._update_available_quantity(packed, self.plant.lot_stock_id, 20)
        # A. nothing ticked, no quantities: confirmation, nothing happens until it is confirmed
        pick = self._transfer(self.plant, self.store, [(packed, 8)])
        res = pick.action_plant_validate()
        self.assertEqual((res["type"], res["res_model"]), ("ir.actions.act_window", "plant.validate.wizard"))
        wiz = self.env["plant.validate.wizard"].browse(res["res_id"])
        self.assertEqual((wiz.has_missing, wiz.has_shortage, pick.state), (True, False, "draft"))
        self.assertIn("LIBRE 454 G MOLIDO", wiz.missing_html)
        self.assertTrue(wiz.action_confirm())
        self.assertEqual((pick.state, pick.plant_stage, pick.move_ids.quantity), ("done", "delivered", 8))
        self.assertIn("Entregadas completas sin cantidad previa", pick.message_ids[0].body)
        # B. quantities set by the reservation, no ticks: direct
        pick2 = self._transfer(self.plant, self.store, [(packed, 5)])
        pick2.action_confirm()
        pick2.action_assign()
        self.assertEqual(pick2.move_ids.quantity, 5)
        self.assertTrue(pick2.action_plant_validate())
        self.assertEqual(pick2.state, "done")
        # C. every tick done but a line short of stock: the shortage is shown and must be confirmed
        punk = self.env["product.product"].create({"name": "CAFE EN GRANO PARA PREPARAR - PUNK", "type": "consu", "is_storable": True, "uom_id": self.coffee.uom_id.id})
        self.env["stock.quant"]._update_available_quantity(punk, self.plant.lot_stock_id, 5000)
        pick3 = self._transfer(self.plant, self.store, [(punk, 7500)])
        pick3.plant_check_ids.write({"done": True})
        res = pick3.action_plant_validate()
        wiz = self.env["plant.validate.wizard"].browse(res["res_id"])
        self.assertEqual((wiz.has_missing, wiz.has_shortage, pick3.state), (True, True, "draft"))
        self.assertIn("7.5 kg pedido, 5 kg en stock", wiz.shortage_html)
        wiz.action_confirm()
        self.assertEqual(pick3.state, "done")
        self.assertIn("Sin stock suficiente al validar", pick3.message_ids[0].body)
        self.assertIn("7.5 kg pedido", pick3.message_ids[0].body)
        self.assertEqual(punk.with_context(location=self.plant.lot_stock_id.id).qty_available, -2500)
        # D. the issues of a fresh request
        pick4 = self._transfer(self.plant, self.store, [(packed, 3), (punk, 1000)])
        issues = pick4._plant_validation_issues()
        self.assertEqual(len(issues["missing"]), 2)
        self.assertEqual([m.product_id for m, _d, _a in issues["shortages"]], [punk])   # packed: 20 − 13 delivered = 7 ≥ 3, not short; punk: 1000 > −2500, short

    def test_first_ticks_keep_the_stage_of_old_requests(self):
        """Requests from before the ticks (1.7.0 migration): each keeps its stage; Lista gets every tick done,
        En alistamiento and Nueva hold until a tick changes."""
        packed = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        picks = {}
        for stage, state_action in (("new", None), ("preparing", "confirm"), ("ready", "assign")):
            pick = self._transfer(self.plant, self.store, [(packed, 10), (self.cups, 5)])
            if state_action:
                pick.action_confirm()
            if state_action == "assign":
                pick.action_assign()
            pick.plant_check_ids.sudo().unlink()   # as a database without ticks
            pick.with_context(plant_auto_stage=True).write({"plant_stage": stage, "plant_stage_manual_progress": False})   # as the old state-driven stage
            picks[stage] = pick
        self.env["stock.picking"].browse([p.id for p in picks.values()])._plant_init_checks_keeping_stage()
        for stage, pick in picks.items():
            self.assertEqual(pick.plant_stage, stage, stage)
            self.assertEqual(len(pick.plant_check_ids), 2, stage)
        self.assertTrue(all(picks["ready"].plant_check_ids.mapped("done")))
        self.assertFalse(any(picks["preparing"].plant_check_ids.mapped("done")))
        self.assertFalse(any(picks["new"].plant_check_ids.mapped("done")))
        picks["preparing"].action_assign()   # a reservation does not move it
        self.assertEqual(picks["preparing"].plant_stage, "preparing")
        picks["preparing"].plant_check_ids.write({"done": True})   # a tick does
        self.assertEqual(picks["preparing"].plant_stage, "ready")
        picks["ready"].plant_check_ids[0].done = False
        self.assertEqual(picks["ready"].plant_stage, "preparing")

    def _note_pdf_pages(self, picks):
        """Pages of the real PDF (wkhtmltopdf). The note carries its own styles, so the external assets are not
        fetched: report.url points to a closed port and wkhtmltopdf gives up on them at once instead of waiting
        on the test server, which holds the test transaction."""
        self.env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:1")
        report = self.env.ref("plant_request_board.action_report_plant_delivery_note")
        pdf = self.env["ir.actions.report"].with_context(force_report_rendering=True)._render_qweb_pdf(report.report_name, picks.ids)[0]
        return len(PdfFileReader(io.BytesIO(pdf), strict=False).pages)

    def test_delivery_note_is_always_one_page(self):
        """40 and 50 lines (and a short one) still print on one letter page each; several requests, one page each."""
        Product = self.env["product.product"]
        lines = [(Product.create({"name": "PAZ %s G MOLIDO" % g, "default_code": "PAZ%sGMOL" % g, "type": "consu", "is_storable": True}), 3) for g in range(100, 140)]
        lines += [(Product.create({"name": "VASO BLANCO %s ONZAS" % n, "type": "consu", "is_storable": True}), 50) for n in range(4, 14)]
        pick50 = self._transfer(self.plant, self.store, lines)
        pick40 = self._transfer(self.plant, self.store, lines[:40])
        short = self._request()
        for pick, layout in ((pick50, "columns"), (pick40, "dense"), (short, "normal")):
            data = pick._plant_delivery_note_data()
            self.assertEqual((data["layout"]["name"], data["line_count"]), (layout, len(pick.move_ids)))
            self.assertEqual(self._note_pdf_pages(pick), 1, "%s lines" % len(pick.move_ids))
        self.assertEqual(self._note_pdf_pages(pick50 | pick40 | short), 3)
        huge = self._transfer(self.plant, self.store, lines + [(Product.create({"name": "LIBRE %s G EN GRANO" % g, "type": "consu", "is_storable": True}), 1) for g in range(100, 160)])
        self.assertEqual(huge._plant_delivery_note_data()["layout"]["name"], "columns3")
        self.assertEqual(self._note_pdf_pages(huge), 1)

    def test_cancelled_request_prints_a_cancelled_mark(self):
        pick = self._request()
        report = self.env.ref("plant_request_board.action_report_plant_delivery_note")
        html = self.env["ir.actions.report"]._render_qweb_html(report.report_name, pick.ids)[0].decode()
        self.assertNotIn("CANCELADA", html)
        pick.action_cancel()
        self.assertEqual((pick.state, pick.plant_stage), ("cancel", "cancelled"))
        data = pick._plant_delivery_note_data()
        self.assertTrue(data["cancelled"])
        self.assertEqual(data["line_count"], 2)   # what was asked is still printed
        html = self.env["ir.actions.report"]._render_qweb_html(report.report_name, pick.ids)[0].decode()
        self.assertIn("pn-watermark", html)
        self.assertIn("SOLICITUD CANCELADA · NO DESPACHAR", html)
        self.assertGreaterEqual(html.count("CANCELADA"), 2)   # band and watermark
        self.assertEqual(self._note_pdf_pages(pick), 1)

    def test_delivery_note_units_and_totals_are_separate(self):
        """Supplies in their own unit, never kg; coffee kg and bags, ready units and supply units apart."""
        Product = self.env["product.product"]
        bag = Product.create({"name": "PAZ 454 G EN GRANO", "type": "consu", "is_storable": True})
        can = Product.create({"name": "LATA COLD BREW 269 ML", "type": "consu", "is_storable": True})
        supplies = Product.create([{"name": n, "type": "consu", "is_storable": True} for n in ("VASO 9 ONZAS", "VASO 12 ONZAS", "VASO 4 ONZAS", "TAPA VASO 9 ONZAS", "PAPEL PARA PASTELERIA", "BOLSA KRAFT PEQUEÑA", "POSTAL LIBERTARIO", "ROLLO EMPAQUE DRIP PAZ", "EMPAQUE REGALO")])
        pick = self._transfer(self.plant, self.store, [(self.coffee, 2500), (bag, 10), (can, 24)] + [(p, 100) for p in supplies])
        data = pick._plant_delivery_note_data()
        by_name = {l["name"]: l for g in data["groups"] for l in g["lines"]}
        for p in supplies:
            self.assertEqual((by_name[p.name]["kg"], by_name[p.name]["qty"], by_name[p.name]["coffee"]), ("—", "100", False), p.name)
        self.assertEqual(by_name["LATA COLD BREW 269 ML"]["kg"], "—")
        self.assertEqual((by_name["PAZ 454 G EN GRANO"]["kg"], by_name["CAFE EN GRANO PARA PREPARAR - PAZ"]["kg"]), ("4.540", "2.500"))
        self.assertEqual((data["kg"], data["bags"], data["ready_units"], data["supply_units"]), ("7.040", "10", "24", "900"))
        html = self.env["ir.actions.report"]._render_qweb_html(self.env.ref("plant_request_board.action_report_plant_delivery_note").report_name, pick.ids)[0].decode()
        self.assertIn("7.040", html)
        self.assertIn("900", html)
        self.assertIn("Unidad", html)

    def test_delivery_note_uses_the_company_logo_and_colours(self):
        """Logo and colours come from the company's document layout (res.company logo, primary and secondary colour)."""
        company = self.plant.company_id or self.env.company
        company.write({"logo": TINY_PNG, "primary_color": "#123456", "secondary_color": "#ABCDEF"})
        pick = self._request()
        data = pick._plant_delivery_note_data()
        self.assertTrue(data["logo"].startswith("data:image/png;base64,"))
        self.assertEqual((data["color"], data["color2"]), ("#123456", "#ABCDEF"))
        html = self.env["ir.actions.report"]._render_qweb_html(self.env.ref("plant_request_board.action_report_plant_delivery_note").report_name, pick.ids)[0].decode()
        self.assertIn('src="data:image/png;base64,', html)
        self.assertIn("--plant-color: #123456", html)
        company.write({"logo": False})
        html = self.env["ir.actions.report"]._render_qweb_html(self.env.ref("plant_request_board.action_report_plant_delivery_note").report_name, pick.ids)[0].decode()
        self.assertNotIn('src="data:image', html)   # no logo: the company name instead
        self.assertIn(company.name, html)

    def test_delivery_note_prints_everything_on_one_page(self):
        """The PDF delivery note: references, every line with its plant data, totals, the delivery address and the
        signature boxes; several requests print in one go."""
        packed = self.env["product.product"].create({"name": "PAZ 340 G MOLIDO", "default_code": "PAZ340GMOL", "type": "consu", "is_storable": True})
        state = self.env["res.country.state"].search([("country_id.code", "=", "CO")], limit=1) or self.env["res.country.state"].create({"name": "Cundinamarca", "code": "CUN", "country_id": self.env.ref("base.co").id})
        self.store.partner_id.write({"street": "Calle 93 # 11-27", "street2": "Local 2", "city": "Bogotá", "state_id": state.id, "zip": "110221", "country_id": self.env.ref("base.co").id, "phone": "601 555 1234"})
        pick = self._transfer(self.plant, self.store, [(self.coffee, 15000), (packed, 36), (self.cups, 100)])
        pick.write({"origin": "CO#4812", "note": "Entregar antes de las 10 am"})
        data = pick._plant_delivery_note_data()
        self.assertEqual((data["line_count"], data["units"], data["kg"], data["bags"], data["supply_units"], data["external_ref"], data["sale"]), (3, "136", "27.240", "36", "100", "CO#4812", ""))
        self.assertEqual(next(l for g in data["groups"] for l in g["lines"] if l["name"] == "VASO AZUL 9 ONZAS")["kg"], "—")
        self.assertEqual([g["name"] for g in data["groups"]], ["Café para preparar", "Café empacado", "Insumos y empaque"])
        bag = next(l for g in data["groups"] for l in g["lines"] if l["code"] == "PAZ340GMOL")
        self.assertEqual((bag["line"], bag["size"], bag["grind"], bag["qty"], bag["kg"]), ("Paz", "340 g", "molido", "36", "12.240"))
        self.assertEqual(data["address"][0], "Tienda test")   # the store first, then its contact's address
        self.assertIn("Calle 93 # 11-27", data["address"])
        self.assertIn("Local 2", data["address"])
        self.assertIn("Tel: 601 555 1234", data["address"])
        self.assertTrue(any("Bogotá" in line and "110221" in line for line in data["address"]))
        self.assertIn("Colombia", data["address"])
        self.assertFalse(data["dense"])
        report = self.env.ref("plant_request_board.action_report_plant_delivery_note")
        self.assertEqual((report.model, report.binding_model_id.model, report.paperformat_id.format), ("stock.picking", "stock.picking", "Letter"))
        html = self.env["ir.actions.report"]._render_qweb_html(report.report_name, pick.ids)[0].decode()
        for text in (pick.name, "REMISIÓN DE SOLICITUD", "PAZ340GMOL", "Paz", "340 g", "molido", "27.240", "Calle 93 # 11-27", "Tel: 601 555 1234", "Entregar antes de las 10 am", "Despacha", "Recibe", "Tienda test", "Tiendas", "CO#4812"):
            self.assertIn(text, html, text)
        # a sale with an external reference and a delivery contact: the customer's address
        partner = self.env["res.partner"].create({"name": "Cliente remisión test", "street": "Carrera 7 # 71-21", "street2": "Apto 501", "city": "Medellín", "zip": "050021", "country_id": self.env.ref("base.co").id, "phone": "310 000 0000"})
        pricelist = self.env["product.pricelist"].create({"name": "Lista remisión test"})
        so = self.env["sale.order"].create({"partner_id": partner.id, "pricelist_id": pricelist.id, "warehouse_id": self.plant.id, "client_order_ref": "CO#5000", "order_line": [(0, 0, {"product_id": packed.id, "product_uom_qty": 4})]})
        so.action_confirm()
        delivery = so.picking_ids[:1]
        d2 = delivery._plant_delivery_note_data()
        self.assertEqual((d2["sale"], d2["external_ref"]), (so.name, "CO#5000"))
        self.assertEqual(d2["address"][:3], ["Cliente remisión test", "Carrera 7 # 71-21", "Apto 501"])
        self.assertIn("Tel: 310 000 0000", d2["address"])
        # mass printing: one document, every request
        html = self.env["ir.actions.report"]._render_qweb_html(report.report_name, (pick | delivery).ids)[0].decode()
        self.assertEqual(html.count("REMISIÓN DE SOLICITUD"), 2)
        self.assertIn(delivery.name, html)
        self.assertEqual(pick.action_plant_print_delivery_note()["type"], "ir.actions.report")
        # many lines: the dense layout
        many = self._transfer(self.plant, self.store, [(self.env["product.product"].create({"name": "PAZ %s G MOLIDO" % g, "type": "consu", "is_storable": True}), 1) for g in range(100, 125)])
        self.assertTrue(many._plant_delivery_note_data()["dense"])

    def _green(self, name, line, kg, code=None):
        """A green coffee product of the line with kg in stock at the plant."""
        gram = self.env.ref("uom.product_uom_gram").id
        green = self.env["product.product"].create({"name": name, "default_code": code, "type": "consu", "is_storable": True, "uom_id": gram})
        green.product_tmpl_id.write({"plant_kind_id": self.env.ref("plant_request_board.kind_green").id, "plant_coffee_line_id": line.id})
        if kg:
            self.env["stock.quant"]._update_available_quantity(green, self.plant.lot_stock_id, kg * 1000)
        return green

    def test_green_coffee_shrinkage_and_cumulative_alerts(self):
        """kg verde = kg a tostar ÷ (1 − merma), per line; the pending requests consume roasted stock first and
        then green coffee in order of arrival: green (enough), yellow (below the minimum), red (missing)."""
        Line = self.env["plant.coffee.line"]
        paz = Line.search([("name", "=ilike", "paz")])
        paz.write({"shrinkage": 16.0, "green_minimum_kg": 20.0})
        self.assertAlmostEqual(paz._plant_shrinkage(), 0.16)
        self.assertAlmostEqual(Line._plant_green_kg(42.0, 0.16), 50.0)
        self.env["ir.config_parameter"].sudo().set_param("plant_request_board.default_shrinkage", "20")
        libre = Line.search([("name", "=ilike", "libre")])
        self.assertAlmostEqual(libre._plant_shrinkage(), 0.20)   # no own shrinkage: the default of the settings
        self.assertAlmostEqual(Line._plant_green_kg(8.0, libre._plant_shrinkage()), 10.0)
        green = self._green("CAFE VERDE PAZ", paz, 60)
        self.assertEqual(paz.green_product_ids, green)
        self.assertAlmostEqual(paz.green_stock_kg, 60.0)
        first = self._transfer(self.plant, self.store, [(self.coffee, 42000)])          # 42 kg of Paz to roast
        second = self._transfer(self.plant, self.store, [(self.coffee, 16800)])         # 16.8 kg more, asked later
        allocation = Line._plant_green_allocation()
        line = next(l for l in allocation["lines"] if l["line_id"] == paz.id)
        self.assertAlmostEqual(line["to_roast_kg"], 58.8)
        self.assertAlmostEqual(line["green_needed_kg"], 70.0)
        self.assertAlmostEqual(line["remaining_kg"], -10.0)
        self.assertEqual(line["status"], "red")
        by_pick = {r["picking_id"]: r for r in allocation["requests"]}
        a, b = by_pick[first.id]["alerts"][0], by_pick[second.id]["alerts"][0]
        self.assertEqual((round(a["green_needed_kg"], 3), round(a["remaining_kg"], 3), a["status"]), (50.0, 10.0, "yellow"))   # 10 kg left, below the minimum of 20
        self.assertIn("Te quedan solo 10.0 kg de café verde Paz", a["message"])
        self.assertEqual((round(b["green_needed_kg"], 3), round(b["remaining_kg"], 3), b["status"]), (20.0, -10.0, "red"))
        self.assertIn("te faltan 10.0 kg de café verde Paz", b["message"])
        self.assertEqual([r["picking_id"] for r in allocation["requests"]], [first.id, second.id])   # order of arrival
        self.assertEqual((first.plant_green_status, second.plant_green_status), ("yellow", "red"))
        self.assertIn("plant-green-red", second.plant_green_alert_html)
        self.assertIn("faltan 10.0 kg", second.plant_green_alert_html)
        sheet_green = self.env["plant.sheet"].get_data(sheet="tiendas")["green"]
        self.assertEqual([r["status"] for r in sheet_green["requests"]], ["yellow", "red"])
        self.assertEqual(next(l for l in sheet_green["lines"] if l["line_id"] == paz.id)["status"], "red")
        # roasted coffee in stock is used first: 42 kg of bulk Paz at the plant covers the first request
        self.env["stock.quant"]._update_available_quantity(self.coffee, self.plant.lot_stock_id, 42000)
        allocation = Line._plant_green_allocation()
        by_pick = {r["picking_id"]: r for r in allocation["requests"]}
        a, b = by_pick[first.id]["alerts"][0], by_pick[second.id]["alerts"][0]
        self.assertEqual((a["from_roasted_kg"], a["to_roast_kg"], a["green_needed_kg"], round(a["remaining_kg"], 3), a["status"]), (42.0, 0.0, 0.0, 60.0, "green"))
        self.assertIn("no gasta café verde", a["message"])
        self.assertNotIn(self._transfer(self.plant, self.store, [(self.cups, 5)]).id, [r["picking_id"] for r in Line._plant_green_allocation()["requests"]])   # no coffee: no alert row
        self.assertEqual((round(b["to_roast_kg"], 3), round(b["green_needed_kg"], 3), round(b["remaining_kg"], 3), b["status"]), (16.8, 20.0, 40.0, "green"))
        self.assertIn("Te quedan 40.0 kg", b["message"])
        # a delivered request leaves the queue; the manual tick of "Lista" too
        first.plant_check_ids.write({"done": True})
        self.assertNotIn(first.id, [r["picking_id"] for r in Line._plant_green_allocation()["requests"]])

    def test_green_coffee_from_the_roasting_bom(self):
        """With manufacturing, the green coffee of a line is also the green component of the roasting BoM of its
        roasted coffee, even when the green product has no line of its own."""
        if "mrp.bom" not in self.env:
            self.skipTest("mrp is not installed")
        paz = self.env["plant.coffee.line"].search([("name", "=ilike", "paz")])
        gram = self.env.ref("uom.product_uom_gram").id
        green = self.env["product.product"].create({"name": "CAFE VERDE LOTE 7 HUILA", "type": "consu", "is_storable": True, "uom_id": gram, "categ_id": self.env["product.category"].create({"name": "Cafe verde"}).id})
        self.assertEqual((green.product_tmpl_id.plant_kind_code, bool(green.product_tmpl_id.plant_coffee_line_id)), ("green", False))   # no known line in its name
        self.env["stock.quant"]._update_available_quantity(green, self.plant.lot_stock_id, 30000)
        self.env["mrp.bom"].create({"product_tmpl_id": self.coffee.product_tmpl_id.id, "product_qty": 840, "product_uom_id": gram, "bom_line_ids": [(0, 0, {"product_id": green.id, "product_qty": 1000, "product_uom_id": gram})]})
        self.assertIn(green, paz.green_product_ids)
        self.assertAlmostEqual(paz.green_stock_kg, 30.0)
        bag = self.env["product.product"].create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        self.env["mrp.bom"].create({"product_tmpl_id": bag.product_tmpl_id.id, "product_qty": 1, "bom_line_ids": [(0, 0, {"product_id": self.coffee.id, "product_qty": 340, "product_uom_id": gram})]})
        self.assertEqual(paz.green_product_ids, green)   # through the bag's bulk coffee too, counted once

    def test_bom_supplies_are_compared_with_stock(self):
        """The supplies of the bills of materials of what has to be made (bags, valves…) against the stock at the
        plant: enough, below the minimum, missing. The coffee inside is left to the green coffee."""
        if "mrp.bom" not in self.env:
            self.skipTest("mrp is not installed")
        Product = self.env["product.product"]
        gram = self.env.ref("uom.product_uom_gram").id
        bag = Product.create({"name": "PAZ 340 G EN GRANO", "type": "consu", "is_storable": True})
        bolsa = Product.create({"name": "BOLSA PARA EMPACAR 340 GRAMOS PAZ", "type": "consu", "is_storable": True})
        valvula = Product.create({"name": "VALVULA DESGASIFICADORA", "type": "consu", "is_storable": True})
        valvula.product_tmpl_id.write({"plant_kind_id": self.env.ref("plant_request_board.kind_supply").id})
        self.env["mrp.bom"].create({"product_tmpl_id": bag.product_tmpl_id.id, "product_qty": 1, "bom_line_ids": [
            (0, 0, {"product_id": self.coffee.id, "product_qty": 340, "product_uom_id": gram}),
            (0, 0, {"product_id": bolsa.id, "product_qty": 1}), (0, 0, {"product_id": valvula.id, "product_qty": 1})]})
        self.env["stock.quant"]._update_available_quantity(bag, self.plant.lot_stock_id, 10)
        self.env["stock.quant"]._update_available_quantity(bolsa, self.plant.lot_stock_id, 20)
        self.env["stock.quant"]._update_available_quantity(valvula, self.plant.lot_stock_id, 5)
        self._transfer(self.plant, self.store, [(bag, 36)])   # 36 asked, 10 in stock: 26 to make
        rows = {r["product_id"]: r for r in self.env["plant.sheet"]._plant_bom_supplies()}
        self.assertEqual(set(rows), {bolsa.id, valvula.id})   # the coffee is not a supply
        self.assertEqual((rows[bolsa.id]["needed"], rows[bolsa.id]["stock"], rows[bolsa.id]["missing"], rows[bolsa.id]["status"]), (26, 20, 6, "red"))
        self.assertEqual((rows[valvula.id]["needed"], rows[valvula.id]["stock"], rows[valvula.id]["missing"], rows[valvula.id]["status"]), (26, 5, 21, "red"))
        self.assertIn("PAZ 340 G EN GRANO ×26", rows[bolsa.id]["for"])
        self.env["stock.quant"]._update_available_quantity(bolsa, self.plant.lot_stock_id, 10)   # 30 in stock, 4 left over
        self.env["ir.config_parameter"].sudo().set_param("plant_request_board.supply_minimum", "5")
        rows = {r["product_id"]: r for r in self.env["plant.sheet"]._plant_bom_supplies()}
        self.assertEqual((rows[bolsa.id]["missing"], rows[bolsa.id]["remaining"], rows[bolsa.id]["status"]), (0, 4, "yellow"))
        self.env["stock.quant"]._update_available_quantity(valvula, self.plant.lot_stock_id, 100)
        rows = {r["product_id"]: r for r in self.env["plant.sheet"]._plant_bom_supplies()}
        self.assertEqual(rows[valvula.id]["status"], "green")
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertTrue(data["bom_available"])
        self.assertEqual([b["product_id"] for b in data["bom_supplies"]][:1], [bolsa.id])   # the worst first

    def test_store_supplies_never_add_kg_and_show_in_the_sheet(self):
        """A store asks coffee plus cups, lids, kraft bags, pastry paper and postcards: the supplies show on the card,
        the note and the sheet's supplies block in their own unit, and never add a gram to the roasting."""
        Product = self.env["product.product"]
        names = ("TAPA VASO 9 ONZAS", "BOLSA KRAFT MEDIANA", "PAPEL PARA PASTELERIA", "POSTAL LIBERTARIO", "VASO 12 ONZAS")
        supplies = Product.create([{"name": n, "type": "consu", "is_storable": True} for n in names])
        self.env["stock.quant"]._update_available_quantity(supplies[0], self.plant.lot_stock_id, 500)
        self.env["stock.quant"]._update_available_quantity(supplies[1], self.plant.lot_stock_id, -40)
        laureles = self.env["stock.warehouse"].create({"name": "Laureles Medellín test", "code": "TLAU"})
        pick = self._transfer(self.plant, laureles, [(self.coffee, 10000)] + [(p, 100) for p in supplies])
        self.assertTrue(all(p.product_tmpl_id.plant_kind_code == "supply" for p in supplies))
        self.assertEqual([m.plant_kg for m in pick.move_ids if m.product_id in supplies], [0.0] * 5)
        self.assertAlmostEqual(pick.plant_coffee_kg, 10.0)
        self.assertEqual(pick.plant_pack_units, 500)
        self.assertIn("Insumos y empaque <span class='plant-count'>5</span>", pick.plant_card_html)
        self.assertEqual(pick._plant_delivery_note_data()["supply_units"], "500")
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        self.assertAlmostEqual(data["totals"]["kg"], 10.0)   # only the coffee
        self.assertEqual(data["totals"]["supply_units"], 500)
        sup = {sp["name"]: sp for sp in data["supplies"]}
        self.assertEqual(set(sup), {"Tapa Vaso 9 oz", "Bolsa Kraft Mediana", "Papel para Pasteleria", "Postal Libertario", "Vaso 12 oz"})
        key = "w%s" % laureles.id
        self.assertEqual((sup["Tapa Vaso 9 oz"]["cells"][key], sup["Tapa Vaso 9 oz"]["total"], sup["Tapa Vaso 9 oz"]["stock"], sup["Tapa Vaso 9 oz"]["to_buy"]), (100, 100, 500, 0))
        self.assertEqual((sup["Bolsa Kraft Mediana"]["stock"], sup["Bolsa Kraft Mediana"]["stock_raw"], sup["Bolsa Kraft Mediana"]["negative"], sup["Bolsa Kraft Mediana"]["to_buy"]), (0, -40, True, 100))
        self.assertEqual((sup["Postal Libertario"]["stock"], sup["Postal Libertario"]["to_buy"]), (0, 100))
        self.assertFalse([r for g in data["groups"] for r in g["rows"] if r["name"].startswith(("Tapa", "Bolsa", "Papel", "Postal", "Vaso"))])
        rows = self.env["plant.production.plan"].search(self.env["plant.production.plan"].action_open()["domain"])
        self.assertEqual(sum(rows.filtered(lambda r: r.product_id in supplies).mapped("kg_to_roast")), 0.0)

    def test_negative_stock_is_zero_with_a_warning_and_bulk_is_split_from_bags(self):
        """Negative stock reads as zero with a warning everywhere (sheet rows, supplies, green coffee); the
        preparation row shows bulk kg and bags apart."""
        paz = self.env["plant.coffee.line"].search([("name", "=ilike", "paz")])
        bag25 = self.env["product.product"].create({"name": "BOLSA 2.5 KG - PAZ", "type": "consu", "is_storable": True})
        bag25.product_tmpl_id.write({"plant_kind_id": self.env.ref("plant_request_board.kind_packed").id, "plant_coffee_line_id": paz.id, "plant_net_grams": 2500, "plant_in_sheet": True})
        self.env["stock.quant"]._update_available_quantity(self.coffee, self.plant.lot_stock_id, -50000)   # −50 kg of bulk
        self.env["stock.quant"]._update_available_quantity(bag25, self.plant.lot_stock_id, 3)              # 3 bags of 2.5 kg
        green = self._green("CAFE VERDE PAZ", paz, 0)
        self.env["stock.quant"]._update_available_quantity(green, self.plant.lot_stock_id, -8000)
        self._transfer(self.plant, self.store, [(self.coffee, 10000), (bag25, 2)])
        data = self.env["plant.sheet"].get_data(sheet="tiendas")
        prep = next(r for g in data["groups"] for r in g["rows"] if r["name"] == "Paz Preparación 2.5")
        self.assertEqual((prep["inventory"], round(prep["inventory_raw"], 3), prep["negative"], prep["to_make"]), (0.0, -17.0, True, 6.0))   # −20 bags of bulk + 3 bags = −17 → 0
        self.assertEqual((round(prep["inventory_detail"]["bulk_kg"], 3), prep["inventory_detail"]["bags"]), (-50.0, 3))
        line = next(l for l in data["green"]["lines"] if l["line_id"] == paz.id)
        self.assertEqual((line["green_stock_kg"], round(line["green_raw_kg"], 3), line["negative"], line["roasted_stock_kg"]), (0.0, -8.0, True, 0.0))
        self.assertEqual(line["status"], "red")   # nothing to roast with
        self.assertAlmostEqual(paz.green_stock_kg, 0.0)
        self.assertAlmostEqual(paz.green_stock_raw_kg, -8.0)
        self.assertEqual(data["negative_rows"], 1)

    def test_facts_flag_shortage_and_history(self):
        pick = self._request()
        facts = pick._plant_facts()
        self.assertEqual(facts["channel"], "Tiendas")
        cups = next(ln for ln in facts["lines"] if ln["product"] == "VASO AZUL 9 ONZAS")
        self.assertEqual(cups["available_at_plant"], 300)
        self.assertIn("faltante", cups["flags"])
        self.assertIn("nuevo para esta tienda", cups["flags"])
        pick.action_plant_briefing()
        self.assertEqual(pick.plant_briefing_state, "done")
        self.assertIn("faltante", pick.plant_briefing)
        self.assertIn("15 kg de café", pick.plant_briefing)

    def test_plant_staff_do_not_ring(self):
        self.env["ir.config_parameter"].sudo().set_param(ICP_PLANT_USERS, str(self.env.user.id))
        with patch.object(type(self.env["bus.bus"]), "_sendone") as sendone:
            self._request()._plant_notify_odoo()
            sendone.assert_not_called()

    def test_request_is_announced_in_channel_and_bus(self):
        channel = self.env.ref("plant_request_board.channel_plant_requests")
        self.env["ir.config_parameter"].sudo().set_param(ICP_PLANT_USERS, str(self.env.user.id))
        self.env["ir.config_parameter"].sudo().set_param(ICP_CHANNEL, str(channel.id))
        other = self.env["res.users"].create({"name": "Tienda test", "login": "tienda.test@local"})
        before = len(channel.message_ids)
        with patch.object(type(self.env["bus.bus"]), "_sendone") as sendone:
            pick = self.env["stock.picking"].with_user(other).sudo().create({
                "picking_type_id": self.plant.int_type_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id,
                "move_ids": [(0, 0, {"product_id": self.coffee.id, "product_uom_qty": 5000, "product_uom": self.coffee.uom_id.id, "location_id": self.plant.lot_stock_id.id, "location_dest_id": self.store.lot_stock_id.id})],
            })
            pick._plant_notify_odoo()   # in production this runs after the transaction commits
            self.assertEqual(len(channel.message_ids), before + 1)
            self.assertIn(pick.name, channel.message_ids[0].body)
            args = sendone.call_args[0]
            self.assertEqual(args[1], "plant_request_board/new")
            self.assertEqual((args[2]["store"], args[2]["channel"]), ("Tienda test", "Tiendas"))
            self.assertEqual(args[0], self.env.user.partner_id)
