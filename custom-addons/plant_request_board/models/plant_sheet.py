from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# what each scope of the sheet shows: pending requests (the active sheet), prepared, delivered, everything
SCOPES = {"open": ("new", "preparing"), "ready": ("ready",), "delivered": ("delivered",), "all": ("new", "preparing", "ready", "delivered")}
HEADER_BLUE = "#2F5496"


class PlantSheet(models.AbstractModel):
    """The plant's workbook, filled from Odoo. Same tabs, colours and columns as the sheet they keep by hand; the
    rows come from the products and the numbers from the open orders and the stock at the plant (one plant, or
    every plant together).

    - Rows: one automatic row per coffee line × grams × grind (and per ready product) of the products ordered in
      the scope shown, from their plant fields, in the order of the lines; a product nobody classified is read
      from its name on the fly, so a new product has its row at once. Manual rows (always shown) stay for the
      kits (components × factor) and for exceptions (a manual row that takes its products away from the
      automatic row).
    - PEDIDOS TIENDAS: store columns (warehouses flagged "Es tienda", flagged by their first request) under the
      optional layer of plant.sheet.column (alias, order, colour, hidden; EVENTO groups the event warehouses), plus
      any other warehouse that ordered. TOTAL BOLSAS, INVENTARIO (stock at the plant, or the value the plant
      typed), POR FABRICAR, TOSTAR and TOTAL NETO X TOSTAR per coffee line. Capsules and drips below.
    - OTROS PEDIDOS / ATTENZA: one column per order with its date; everything ordered is roasted (no inventory).
      Attenza explodes kits into components and adds CAJAS, lotes and fecha de vencimiento.
    """

    _name = "plant.sheet"
    _description = "Hoja de pedidos de la planta"

    # --- entry point -------------------------------------------------------------------
    @api.model
    def get_tabs(self):
        """[code, title] of the workbook's tabs, as the rows define them (the client draws the tabs from this)."""
        return [list(tab) for tab in self.env["plant.sheet.row"]._fields["sheet"].selection]

    @api.model
    def get_plants(self):
        """[{id, name}] of the plants; the client shows a selector when there is more than one."""
        return [{"id": wh.id, "name": wh.name} for wh in self.env["stock.picking"]._plant_warehouses()]

    @api.model
    def get_data(self, sheet="tiendas", scope="open", plant_id=None):
        """The tab, for the open orders (or all of them) of one plant, or of every plant when plant_id is empty."""
        plant_id = int(plant_id) if plant_id else None
        plan_rows = self.env["plant.production.plan"]._compute_rows(plant_id=plant_id)   # once: the plan's total and the BoM supplies read it
        data = self._orders_data(sheet, scope, plant_id, plan_rows=plan_rows)
        data.update({
            "sheet": sheet, "title": dict(self.get_tabs())[sheet], "scope": scope, "plant_id": plant_id,
            "plan_kg": sum(r["kg_to_roast"] for r in plan_rows) if scope == "open" else None,   # the same open orders, every channel, stock discounted everywhere
            "negative_rows": sum(1 for g in data["groups"] for r in g["rows"] if r.get("negative")),
            "generated": fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime("%Y-%m-%d %H:%M"),
        })
        return data

    @api.model
    def get_scopes(self):
        """[code, label] of the scopes the client offers."""
        return [["open", "Por alistar (nuevas y en alistamiento)"], ["ready", "Listas para despachar"], ["delivered", "Despachadas"], ["all", "Todos los pedidos"]]

    @api.model
    def toggle_checks(self, check_ids, done):
        """Tick (or untick) the ticks of one cell of the sheet: the lines of that row for that store or order."""
        self.env["plant.request.check"].browse([int(i) for i in check_ids]).write({"done": bool(done)})
        return True

    @api.model
    def set_inventory(self, row_id, value):
        """INVENTARIO typed by the plant on the sheet (inventory administrators only). Empty clears it and the stock
        of Odoo is used again."""
        if not self.env.su and not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Solo un administrador de Inventario digita el inventario de la hoja."))
        row = self.env["plant.sheet.row"].browse(int(row_id))
        if value in (None, "", False):
            row.write({"inventory_manual": 0.0, "inventory_manual_date": False})
        else:
            row.write({"inventory_manual": float(value), "inventory_manual_date": fields.Date.context_today(self)})
        return True

    # --- helpers --------------------------------------------------------------------------
    @api.model
    def _plant_locations(self, plant_id=None):
        """Stock locations of the plants shown: the one chosen, or every plant."""
        plants = self.env["stock.picking"]._plant_warehouses()
        if plant_id:
            plants = plants.filtered(lambda wh: wh.id == plant_id)
        return plants.lot_stock_id

    @api.model
    def _sheet_channels(self, sheet):
        """The channels that feed the tab (Planta › Canales › Pestaña de la hoja)."""
        return self.env["plant.channel"].sudo().search([("sheet", "=", sheet)])

    @api.model
    def _moves(self, sheet, scope, plant_id=None):
        dom = [("plant_request", "=", True), ("plant_channel_id", "in", self._sheet_channels(sheet).ids), ("state", "!=", "cancel"), ("plant_stage", "in", SCOPES.get(scope, SCOPES["all"]))]
        if plant_id:
            dom.append(("plant_warehouse_id", "=", plant_id))
        return self.env["stock.move"].search(dom, order="id")

    def _local_date(self, dt):
        return fields.Datetime.context_timestamp(self, dt).strftime("%Y-%m-%d") if dt else None

    @api.model
    def _columns(self, sheet, moves):
        """Columns and a function move → column key. Stores: the configured columns in the plant's order, then every
        store (warehouse flagged "Es tienda") by name, then any other warehouse that ordered. Orders: one column per
        transfer, named after the store/customer, with its date."""
        columns, index = [], {}
        if sheet == "tiendas":
            wh_key = {}
            for col in self.env["plant.sheet.column"].search([("sheet", "=", sheet)]):
                key = "c%s" % col.id
                columns.append({"key": key, "name": col.name, "date": None, "orders": set(), "picking_id": None, "fixed": True, "hidden": col.hidden, "color": col.header_color or HEADER_BLUE})
                index[key] = columns[-1]
                for wh in col.warehouse_ids:
                    wh_key[wh.id] = key
            for wh in self.env["stock.warehouse"].search([("plant_is_store", "=", True)], order="name, id"):
                if wh.id not in wh_key:   # a store without a configured column gets its own, with its name
                    key = "w%s" % wh.id
                    columns.append({"key": key, "name": (wh.name or "—").upper(), "date": None, "orders": set(), "picking_id": None, "fixed": False, "hidden": False, "color": HEADER_BLUE})
                    index[key] = columns[-1]
                    wh_key[wh.id] = key

            def key_for(move):
                wh = move.picking_id.location_dest_id.warehouse_id
                key = wh_key.get(wh.id) if wh else None
                if not key:
                    key = "w%s" % (wh.id if wh else (move.plant_counterparty or "-"))
                    if key not in index:
                        columns.append({"key": key, "name": ((wh.name if wh else move.plant_counterparty) or "—").upper(), "date": None, "orders": set(), "picking_id": None, "fixed": False, "hidden": False, "color": HEADER_BLUE})
                        index[key] = columns[-1]
                return key
        else:
            stage_labels = dict(self.env["stock.picking"]._fields["plant_stage"].selection)

            def key_for(move):
                pick = move.picking_id
                key = "p%s" % pick.id
                if key not in index:
                    columns.append({"key": key, "name": (pick.plant_counterparty or pick.name).upper(), "date": None, "orders": set(), "picking_id": pick.id, "fixed": False, "ref": pick.name, "color": HEADER_BLUE,
                                    "stage": pick.plant_stage, "stage_label": stage_labels.get(pick.plant_stage, ""), "progress": pick.plant_progress})
                    index[key] = columns[-1]
                return key

        for mv in moves:
            col = index[key_for(mv)]
            col["orders"].add(mv.picking_id.id)
            created = mv.picking_id.create_date
            if created and (col.get("_dt") is None or created > col["_dt"]):
                col["_dt"] = created
        for col in columns:
            col["date"] = self._local_date(col.pop("_dt", None))
            col["orders"] = len(col["orders"])
        return columns, key_for

    # --- automatic rows -------------------------------------------------------------------
    @api.model
    def _row_settings(self):
        Settings = self.env["res.config.settings"]
        return {
            "prep_grams": Settings._plant_get_float("plant_prep_bag_grams") or 2500.0,
            "split_grind": Settings._plant_get("plant_row_grind") != "merge",
            "grind_text": {code: label.lower() for code, label in self.env["product.template"]._fields["plant_grind"].selection},
        }

    @api.model
    def _row_key(self, vals, settings):
        """Key of the automatic row a product adds up in, from its plant values; None when it does not count.
        Coffee: line × grams × grind (bulk coffee and the bags of the preparation size share the "Preparación" row,
        whatever the grind). Ready products: one row per master product."""
        if not vals["in_sheet"] or vals["kind"] not in ("prepare", "packed", "ready"):
            return None
        if vals["kind"] == "ready":
            return "ready:%s:%s" % (vals["line"].id or 0, vals["master"].id)
        grams = settings["prep_grams"] if vals["kind"] == "prepare" else (vals["grams"] or 0.0)
        split = settings["split_grind"] and vals["kind"] == "packed" and grams != settings["prep_grams"]
        return "coffee:%s:%g:%s" % (vals["line"].id or 0, grams, (vals["grind"] or "") if split else "")

    @api.model
    def _row_vals(self, vals, settings):
        """Name, line, colour, grams, block and order of the automatic row of a product, from its plant values."""
        line = vals["line"]
        line_name = vals["line_name"] or "—"
        line_seq = line.sequence if line else 99999
        base = {"line": line_name, "line_id": line.id if line else False, "color": (line.color if line else "") or "#FFFFFF", "net_color": (line.net_color if line else "") or False}
        if vals["kind"] == "ready":
            name = self.env["stock.picking"]._plant_short_name(vals["master"].name, settings.get("line_rules"))
            return dict(base, name=name, block="ready", grams=0.0, sequence=line_seq * 10000 + 9999)
        grams = settings["prep_grams"] if vals["kind"] == "prepare" else (vals["grams"] or 0.0)
        if grams == settings["prep_grams"]:
            name = "%s Preparación %g" % (line_name, grams / 1000.0)
            grind_rank = 0
        else:
            name = "%s %g" % (line_name, grams)
            split = settings["split_grind"] and vals["kind"] == "packed" and vals["grind"]
            if split:
                name += " " + settings["grind_text"][vals["grind"]]
            grind_rank = 1 if (split and vals["grind"] == "ground") else 0
        return dict(base, name=name, block="coffee", grams=grams, sequence=line_seq * 10000 + min(int(grams), 4990) * 2 + grind_rank)

    @api.model
    def _sync_auto_rows(self, sheet, keyed):
        """The automatic rows of the tab for the keys given ({key: row values}): created when new, refreshed when
        the line or the product changed. Returns {key: row} (archived rows included: an archived row hides its
        products from the tab)."""
        Row = self.env["plant.sheet.row"].sudo().with_context(active_test=False)
        rows = {row.auto_key: row for row in Row.search([("sheet", "=", sheet), ("is_auto", "=", True), ("auto_key", "in", list(keyed))])}
        for key, vals in keyed.items():
            row = rows.get(key)
            if not row:
                rows[key] = Row.create(dict(vals, sheet=sheet, auto_key=key, is_auto=True, exception=False))
                continue
            changed = {name: value for name, value in vals.items() if (row[name].id if isinstance(row[name], models.BaseModel) else row[name]) != value and (row[name] or value)}
            if changed:
                row.write(changed)
        return rows

    # --- order tabs -----------------------------------------------------------------------
    @api.model
    def _orders_data(self, sheet, scope, plant_id=None, plan_rows=None):
        Row = self.env["plant.sheet.row"]
        moves = self._moves(sheet, scope, plant_id)
        columns, key_for = self._columns(sheet, moves)
        settings = self._row_settings()
        line_rules = self.env["stock.picking"]._plant_line_rules()   # kinds, classifier rules and card words, loaded once for the whole tab
        settings["line_rules"] = line_rules
        rules = line_rules["parser"]
        # manual rows that take products: kits (kit row + component rows) and exceptions
        manual = Row.search([("sheet", "=", sheet), ("is_auto", "=", False), "|", "|", ("exception", "=", True), ("parent_id", "!=", False), ("child_ids", "!=", False)])
        by_product, row_products = {}, {}
        for row in manual:
            for product in row.product_ids:
                if product.id not in by_product:
                    by_product[product.id] = row
                    row_products.setdefault(row.id, []).append(product)
        # automatic rows: one per line × grams × grind of the products ordered in this scope
        keyed, product_key = {}, {}
        for product in moves.product_id:
            if product.id in by_product:
                continue
            vals = product.product_tmpl_id._plant_values(rules)
            key = self._row_key(vals, settings)
            if key:
                product_key[product.id] = key
                keyed.setdefault(key, self._row_vals(vals, settings))
        auto = self._sync_auto_rows(sheet, keyed)
        rows = Row.search([("id", "in", manual.ids + [row.id for row in auto.values()])])   # active rows, in the sheet's order
        for product_id, key in product_key.items():
            row = auto[key]
            by_product[product_id] = row
            row_products.setdefault(row.id, []).append(self.env["product.product"].browse(product_id))
        cells = {row.id: {} for row in rows}
        checks = {row.id: {} for row in rows}   # (row, column) → the ticks of those lines
        check_by_move = {m.id: c for c in self.env["plant.request.check"].search([("picking_id", "in", moves.picking_id.ids)]) for m in c.move_ids}
        unmapped = {}
        supplies = {}   # supplies (and anything that is not coffee to roast) ordered by the stores: shown apart, never in kg
        for mv in moves:
            key = key_for(mv)
            row = by_product.get(mv.product_id.id)
            if row and row.id in cells:
                cells[row.id][key] = cells[row.id].get(key, 0.0) + row._units(mv.product_id, mv.product_uom_qty, mv.product_uom)
                check = check_by_move.get(mv.id)
                if check:
                    checks[row.id].setdefault(key, {}).setdefault(check.id, check.done)
            elif mv.plant_kind_code in ("prepare", "packed", "ready"):
                u = unmapped.setdefault(mv.product_id.id, {"product_id": mv.product_id.id, "name": mv.product_id.display_name, "unit": mv.product_uom.name, "cells": {}, "total": 0.0})
                u["cells"][key] = u["cells"].get(key, 0.0) + mv.product_uom_qty
                u["total"] += mv.product_uom_qty
            else:
                master = mv.product_id.product_tmpl_id._plant_values(rules)["master"]
                sp = supplies.setdefault(master.id, {"product_id": mv.product_id.id, "product_tmpl_id": master.id, "name": self.env["stock.picking"]._plant_short_name(master.name, line_rules), "kind": mv.plant_kind_code or "supply",
                                                     "unit": mv.product_uom.name, "cells": {}, "total": 0.0, "products": set(), "checks": {}})
                sp["cells"][key] = sp["cells"].get(key, 0.0) + mv.product_uom_qty
                sp["total"] += mv.product_uom_qty
                sp["products"].add(mv.product_id.id)
                check = check_by_move.get(mv.id)
                if check:
                    sp["checks"].setdefault(key, {}).setdefault(check.id, check.done)
        for row in rows.filtered("parent_id"):   # kit components receive the kit quantity × factor
            for key, qty in cells.get(row.parent_id.id, {}).items():
                cells[row.id][key] = cells[row.id].get(key, 0.0) + qty * row.factor

        locations = self._plant_locations(plant_id)
        has_inventory = sheet == "tiendas"
        has_boxes = sheet == "attenza"
        Product = self.env["product.product"]
        supply_products = Product.browse([pid for sp in supplies.values() for pid in sp["products"]])
        stock = self._stock_by_product([p for row in rows for p in row_products.get(row.id, [])] + list(supply_products), locations)
        for sp in supplies.values():
            raw = sum(stock.get(pid, 0.0) for pid in sp["products"])
            sp.update({"stock_raw": raw, "stock": max(raw, 0.0), "negative": raw < -1e-9, "to_buy": max(sp["total"] - max(raw, 0.0), 0.0), "products": len(sp["products"]),
                       "checks": {key: [sum(1 for d in items.values() if d), len(items), list(items)] for key, items in sp["checks"].items()}})
        out_rows = []
        for row in rows:
            products = row_products.get(row.id, [])
            total = sum(cells[row.id].values())
            r = {"id": row.id, "name": row.name, "line": row.line or "", "color": row.color or "#FFFFFF", "block": row.block, "grams": row.grams, "note": row.note or "",
                 "indent": bool(row.parent_id), "is_kit": bool(row.child_ids), "auto": row.is_auto, "cells": cells[row.id], "total": total, "products": len(products),
                 "checks": {key: [sum(1 for d in items.values() if d), len(items), list(items)] for key, items in checks[row.id].items()},   # [done, total, ids]
                 "net_color": row.net_color or row.color or "#FFFFFF"}
            if row.block == "coffee":
                if has_inventory:
                    auto_raw = sum(row._units(p, stock.get(p.id, 0.0), p.uom_id) for p in products)
                    auto_qty = max(auto_raw, 0.0)   # a negative stock in Odoo never adds to what has to be made: shown as a warning
                    manual_inv = bool(row.inventory_manual_date)
                    inventory = row.inventory_manual if manual_inv else auto_qty
                    bulk = [p for p in products if row._is_weight(p.uom_id)]
                    detail = None
                    if bulk and len(bulk) < len(products):   # bulk grams and bags in the same row: shown apart
                        gram = row._plant_gram()
                        detail = {"bulk_kg": sum(p.uom_id._compute_quantity(stock.get(p.id, 0.0), gram, round=False) for p in bulk) / 1000.0,
                                  "bags": sum(stock.get(p.id, 0.0) for p in products if p not in bulk)}
                    r.update({"inventory": inventory, "inventory_auto": auto_qty, "inventory_raw": auto_raw, "negative": auto_raw < -1e-9, "inventory_manual": manual_inv,
                              "inventory_detail": detail, "to_make": max(total - max(inventory, 0.0), 0.0)})
                else:
                    r.update({"inventory": None, "inventory_auto": None, "inventory_raw": None, "negative": False, "inventory_manual": False, "to_make": total})
                r["kg"] = row.grams * r["to_make"] / 1000.0 if row.grams and not row.child_ids else 0.0
            else:
                r.update({"inventory": None, "inventory_auto": None, "inventory_raw": None, "negative": False, "inventory_manual": False, "to_make": total, "kg": 0.0})
            if has_boxes:
                lots, expiry = row._lots(locations)
                r.update({"boxes": row._boxes(total), "lots": lots, "expiry": expiry})
            out_rows.append(r)

        groups, ready = [], []
        for r in out_rows:
            if r["block"] != "coffee":
                ready.append(r)
                continue
            if groups and groups[-1]["line"] == r["line"]:
                groups[-1]["rows"].append(r)
            else:
                # TOTAL NETO X TOSTAR takes the line colour, except in ATTENZA where it is white
                groups.append({"line": r["line"], "color": r["color"], "net_color": "#FFFFFF" if sheet == "attenza" else r["net_color"], "rows": [r]})
        for g in groups:
            g["kg"] = sum(r["kg"] for r in g["rows"])
            g["total"] = sum(r["total"] for r in g["rows"])
            g["to_make"] = sum(r["to_make"] for r in g["rows"])
        coffee_rows = [r for g in groups for r in g["rows"]]
        green = self.env["plant.coffee.line"]._plant_green_allocation(plant_id=plant_id)
        return {
            "mode": "stores" if sheet == "tiendas" else "orders", "has_inventory": has_inventory, "has_boxes": has_boxes,
            "columns": [c for c in columns if not c.get("hidden")],   # a hidden column is not drawn; its orders still count in the totals
            "groups": groups, "ready": ready,
            "unmapped": sorted(unmapped.values(), key=lambda u: u["name"]),
            "supplies": sorted(supplies.values(), key=lambda sp: (sp["kind"] != "supply", sp["name"])),
            "green": green,
            "bom_available": "mrp.bom" in self.env,
            "bom_supplies": self._plant_bom_supplies(plant_id, plan_rows),
            "totals": {"total": sum(r["total"] for r in coffee_rows), "to_make": sum(r["to_make"] for r in coffee_rows), "kg": sum(g["kg"] for g in groups),
                       "supply_units": sum(sp["total"] for sp in supplies.values())},
            "orders_total": len({mv.picking_id.id for mv in moves}),
        }

    @api.model
    def _plant_bom_supplies(self, plant_id=None, plan_rows=None):
        """The supplies the pending production needs, from the bills of materials of what has to be made (bags,
        valves, labels…), against the stock at the plant, with the same alert: enough, below the minimum, missing.
        Empty when mrp is not installed or nothing has a bill of materials."""
        if "mrp.bom" not in self.env:
            return []
        Bom = self.env["mrp.bom"].sudo()
        Product = self.env["product.product"]
        kinds = {k.id: k.code for k in self.env["plant.kind"].search([])}
        needs, uses = {}, {}
        if plan_rows is None:
            plan_rows = self.env["plant.production.plan"]._compute_rows(plant_id=plant_id)
        for r in plan_rows:
            if r["to_produce"] <= 0 or kinds.get(r["plant_kind_id"]) not in ("packed", "ready"):
                continue
            product = Product.browse(r["product_id"])
            bom = Bom._bom_find(product).get(product)
            if not bom:
                continue
            factor = r["to_produce"] / (bom.product_qty or 1.0)
            for line in bom.bom_line_ids:
                comp = line.product_id
                if comp.product_tmpl_id._plant_values()["kind"] in ("prepare", "packed", "green"):
                    continue   # the coffee inside is the green coffee's business
                qty = line.product_uom_id._compute_quantity(line.product_qty * factor, comp.uom_id, round=False) if line.product_uom_id != comp.uom_id else line.product_qty * factor
                needs[comp.id] = needs.get(comp.id, 0.0) + qty
                uses.setdefault(comp.id, []).append("%s ×%g" % (product.display_name, r["to_produce"]))
        if not needs:
            return []
        products = Product.browse(list(needs))
        stock = self._stock_by_product(products, self._plant_locations(plant_id))
        minimum = self.env["res.config.settings"]._plant_get_float("plant_supply_minimum")
        rows = []
        for comp in products:
            needed = needs[comp.id]
            raw = stock.get(comp.id, 0.0)
            available = max(raw, 0.0)
            missing = max(needed - available, 0.0)
            remaining = available - needed
            rows.append({"product_id": comp.id, "name": comp.display_name, "unit": comp.uom_id.name, "needed": needed, "stock": available, "stock_raw": raw, "negative": raw < -1e-9,
                         "missing": missing, "remaining": remaining, "status": "red" if missing > 1e-9 else "yellow" if remaining < minimum - 1e-9 else "green",
                         "for": ", ".join(sorted(set(uses[comp.id])))[:200]})
        return sorted(rows, key=lambda r: ({"red": 0, "yellow": 1, "green": 2}[r["status"]], r["name"]))

    @api.model
    def _stock_by_product(self, products, locations):
        """{product id: quantity on hand} at the locations, in the product's unit, with one query."""
        ids = list({p.id for p in products})
        if not ids or not locations:
            return {}
        domain = [("product_id", "in", ids), ("location_id", "child_of", locations.ids), ("location_id.usage", "in", ("internal", "transit"))]
        return {product.id: qty for product, qty in self.env["stock.quant"]._read_group(domain, ["product_id"], ["quantity:sum"])}
