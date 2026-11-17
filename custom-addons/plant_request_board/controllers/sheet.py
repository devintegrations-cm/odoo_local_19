import io

import xlsxwriter

from odoo import fields, http
from odoo.http import request

YELLOW, CYAN, BLUE, GOLD, BAND = "#FFFF00", "#00B0F0", "#2F5496", "#FFD966", "#00FFFF"


class PlantSheetController(http.Controller):
    """The plant's workbook as an Excel file: the order tabs, with their colours, merged cells and frozen panes."""

    @http.route("/plant_request_board/sheet.xlsx", type="http", auth="user")
    def sheet_xlsx(self, scope="open", plant_id=None, **kw):
        Sheet = request.env["plant.sheet"]
        plant_id = int(plant_id) if plant_id and str(plant_id).isdigit() else None
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        fmt = _Formats(wb)
        for sheet, _title in Sheet.get_tabs():
            self._orders(wb, fmt, Sheet.get_data(sheet=sheet, scope=scope, plant_id=plant_id))
        wb.close()
        return request.make_response(buf.getvalue(), headers=[
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", http.content_disposition("PEDIDOS PLANTA %s.xlsx" % data_date(Sheet))),
        ])

    def _orders(self, wb, fmt, d):
        ws = wb.add_worksheet(d["title"][:31])
        columns = d["columns"] or ([{"key": "_", "name": "ATTENZA", "date": None}] if d["sheet"] == "attenza" else [])
        show_total = not (d["sheet"] == "attenza" and len(columns) == 1)
        right = (["TOTAL BOLSAS"] if show_total else []) + (["INVENTARIO", "POR FABRICAR"] if d["has_inventory"] else []) + [" TOSTAR", "TOTAL NETO X TOSTAR "] + (["CAJAS", "lotes", "fecha vencimiento"] if d["has_boxes"] else [])
        c0 = 1   # column B, like their sheet
        ws.write(0, c0, "FECHA DE PEDIDO", fmt.get(bg=YELLOW, bold=True))
        ws.write(1, c0, "ITEM ", fmt.get(bg=CYAN, color="#FFFFFF", bold=True))
        for j, col in enumerate(columns):
            ws.write(0, c0 + 1 + j, col.get("date") or "", fmt.get(bg=YELLOW, align="center"))
            ws.write(1, c0 + 1 + j, col["name"], fmt.get(bg=col.get("color") or BLUE, color="#FFFFFF", bold=True, align="center", wrap=True))
        rc = c0 + 1 + len(columns)
        idx = {name: rc + i for i, name in enumerate(right)}
        for name, j in idx.items():
            ws.write(0, j, "", fmt.get(bg=YELLOW))   # the date row is yellow end to end
            ws.write(1, j, name, fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center", wrap=True))
        ws.set_column(0, 0, 3)
        ws.set_column(c0, c0, 32)
        ws.set_column(c0 + 1, rc - 1, 11)
        ws.set_column(rc, rc + len(right) - 1, 14)
        r = 2
        for g in d["groups"]:
            first = r
            for row in g["rows"]:
                item = fmt.get(bg=row["color"], bold=not row["indent"], indent=1 if row["indent"] else 0)
                ws.write(r, c0, row["name"], item)
                for j, col in enumerate(columns):
                    v = row["cells"].get(col["key"])
                    ws.write(r, c0 + 1 + j, v if v else "", fmt.get(num="#,##0.##"))
                if show_total:
                    ws.write(r, idx["TOTAL BOLSAS"], row["total"], fmt.get(num="#,##0.##", bg=YELLOW))
                if d["has_inventory"]:
                    ws.write(r, idx["INVENTARIO"], row["inventory"] or 0, fmt.get(num="#,##0.##", bg="#FCE4D6" if row.get("negative") else ("#FFF2CC" if row["inventory_manual"] else None)))
                    if row.get("negative"):
                        ws.write_comment(r, idx["INVENTARIO"], "Inventario negativo en Odoo (%s): falta registrar producción/empaque. Se cuenta como cero." % ("%g" % row["inventory_raw"]))
                    ws.write(r, idx["POR FABRICAR"], row["to_make"], fmt.get(num="#,##0.##", bg=GOLD, bold=True))
                ws.write(r, idx[" TOSTAR"], row["kg"] if row["grams"] else "", fmt.get(num="#,##0.###"))
                if d["has_boxes"]:
                    ws.write(r, idx["CAJAS"], row.get("boxes") or "", fmt.get(num="0"))
                    ws.write(r, idx["lotes"], row.get("lots") or "", fmt.get())
                    ws.write(r, idx["fecha vencimiento"], row.get("expiry") or "", fmt.get())
                if row["note"]:
                    ws.write(r, rc + len(right), row["note"])
                r += 1
            net = idx["TOTAL NETO X TOSTAR "]
            if r - 1 > first:
                ws.merge_range(first, net, r - 1, net, g["kg"], fmt.get(num="#,##0.###", bold=True, align="center", valign="vcenter", bg=g["net_color"]))
            else:
                ws.write(first, net, g["kg"], fmt.get(num="#,##0.###", bold=True, align="center", valign="vcenter", bg=g["net_color"]))
        bold = fmt.get(num="#,##0.###", bold=True, bg=YELLOW)
        for j in range(c0, rc + len(right)):   # totals row yellow end to end
            ws.write(r, j, "", fmt.get(bg=YELLOW))
        if show_total:
            ws.write(r, idx["TOTAL BOLSAS"], d["totals"]["total"], bold)
        if d["has_inventory"]:
            ws.write(r, idx["POR FABRICAR"], d["totals"]["to_make"], bold)
        ws.write(r, idx["TOTAL NETO X TOSTAR "], d["totals"]["kg"], bold)
        r += 2
        if d["ready"]:   # capsules and drips framed by cyan bands
            ws.write(r, c0, "", fmt.get(bg=BAND))
            if show_total:
                ws.write(r, idx["TOTAL BOLSAS"], "", fmt.get(bg=BAND))
            r += 1
        for row in d["ready"]:
            ws.write(r, c0, row["name"], fmt.get(bg=row["color"], bold=True))
            for j, col in enumerate(columns):
                v = row["cells"].get(col["key"])
                ws.write(r, c0 + 1 + j, v if v else "", fmt.get(num="#,##0"))
            if show_total:
                ws.write(r, idx["TOTAL BOLSAS"], row["total"], fmt.get(num="#,##0", bg=YELLOW))
            r += 1
        if d["ready"]:
            for j in range(c0 + 1, (idx["TOTAL BOLSAS"] if show_total else rc - 1) + 1):
                ws.write(r, j, "", fmt.get(bg=BAND))
            r += 1
        if d["unmapped"]:
            r += 2
            ws.write(r, c0, "Pedido pero sin fila en la hoja", fmt.get(bold=True, bg="#FFF8E5"))
            r += 1
            for u in d["unmapped"]:
                ws.write(r, c0, "%s (%s)" % (u["name"], u["unit"]), fmt.get())
                for j, col in enumerate(columns):
                    v = u["cells"].get(col["key"])
                    ws.write(r, c0 + 1 + j, v if v else "", fmt.get(num="#,##0.##"))
                if show_total:
                    ws.write(r, idx["TOTAL BOLSAS"], u["total"], fmt.get(num="#,##0.##"))
                r += 1
        status_bg = {"green": "#E2F0D9", "yellow": "#FFF2CC", "red": "#FCE4D6"}
        if d.get("supplies"):   # supplies ordered by the stores: their unit, never kg
            r += 2
            ws.write(r, c0, "INSUMOS PEDIDOS", fmt.get(bg=BLUE, color="#FFFFFF", bold=True))
            for j, col in enumerate(columns):
                ws.write(r, c0 + 1 + j, col["name"], fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center", wrap=True))
            for i, name in enumerate(("TOTAL", "UNIDAD", "EN PLANTA", "POR COMPRAR")):
                ws.write(r, rc + i, name, fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center"))
            r += 1
            for sp in d["supplies"]:
                ws.write(r, c0, sp["name"], fmt.get())
                for j, col in enumerate(columns):
                    v = sp["cells"].get(col["key"])
                    ws.write(r, c0 + 1 + j, v if v else "", fmt.get(num="#,##0"))
                ws.write(r, rc, sp["total"], fmt.get(num="#,##0", bg=YELLOW))
                ws.write(r, rc + 1, sp["unit"] or "", fmt.get())
                ws.write(r, rc + 2, sp["stock"], fmt.get(num="#,##0", bg="#FCE4D6" if sp["negative"] else None))
                if sp["negative"]:
                    ws.write_comment(r, rc + 2, "Inventario negativo en Odoo (%g): falta registrar producción/empaque. Se cuenta como cero." % sp["stock_raw"])
                ws.write(r, rc + 3, sp["to_buy"], fmt.get(num="#,##0", bg=GOLD if sp["to_buy"] else None, bold=bool(sp["to_buy"])))
                r += 1
        green = d.get("green") or {}
        if green.get("lines"):
            r += 2
            for i, name in enumerate(("CAFÉ VERDE", "MERMA %", "KG A TOSTAR", "VERDE NECESARIO", "VERDE EN PLANTA", "SALDO", "ESTADO")):
                ws.write(r, c0 + i, name, fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center"))
            r += 1
            for g in green["lines"]:
                ws.write(r, c0, g["line"], fmt.get(bg=g["color"], bold=True))
                ws.write(r, c0 + 1, g["shrinkage_pct"], fmt.get(num="0.00"))
                ws.write(r, c0 + 2, g["to_roast_kg"], fmt.get(num="#,##0.###"))
                ws.write(r, c0 + 3, g["green_needed_kg"], fmt.get(num="#,##0.###"))
                ws.write(r, c0 + 4, g["green_stock_kg"], fmt.get(num="#,##0.###", bg="#FCE4D6" if g["green_raw_kg"] < 0 else None))
                if g["green_raw_kg"] < 0:
                    ws.write_comment(r, c0 + 4, "Inventario negativo en Odoo (%.2f kg): falta registrar producción/empaque. Se cuenta como cero." % g["green_raw_kg"])
                ws.write(r, c0 + 5, g["remaining_kg"], fmt.get(num="#,##0.###", bg=status_bg[g["status"]], bold=True))
                ws.write(r, c0 + 6, {"red": "Falta café verde", "yellow": "Por debajo del mínimo (%g kg)" % g["minimum_kg"], "green": "Alcanza"}[g["status"]], fmt.get(bg=status_bg[g["status"]]))
                r += 1
            if green.get("requests"):
                r += 1
                for i, name in enumerate(("ALERTAS POR SOLICITUD", "FECHA", "TIENDA / CLIENTE", "LÍNEA", "TOSTAR KG", "VERDE KG", "SALDO KG", "MENSAJE")):
                    ws.write(r, c0 + i, name, fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center"))
                r += 1
                for rq in green["requests"]:
                    for k, a in enumerate(rq["alerts"]):
                        ws.write(r, c0, rq["name"] if k == 0 else "", fmt.get())
                        ws.write(r, c0 + 1, rq["date"] if k == 0 else "", fmt.get())
                        ws.write(r, c0 + 2, rq["counterparty"] if k == 0 else "", fmt.get())
                        ws.write(r, c0 + 3, a["line"], fmt.get(bg=a["color"], bold=True))
                        ws.write(r, c0 + 4, a["to_roast_kg"], fmt.get(num="#,##0.###"))
                        ws.write(r, c0 + 5, a["green_needed_kg"], fmt.get(num="#,##0.###"))
                        ws.write(r, c0 + 6, a["remaining_kg"], fmt.get(num="#,##0.###", bg=status_bg[a["status"]], bold=True))
                        ws.write(r, c0 + 7, a["message"], fmt.get(bg=status_bg[a["status"]]))
                        r += 1
        if d.get("bom_supplies"):
            r += 2
            for i, name in enumerate(("INSUMOS POR FABRICAR (BoM)", "NECESARIO", "UNIDAD", "EN PLANTA", "FALTAN", "PARA", "ESTADO")):
                ws.write(r, c0 + i, name, fmt.get(bg=BLUE, color="#FFFFFF", bold=True, align="center"))
            r += 1
            for b in d["bom_supplies"]:
                ws.write(r, c0, b["name"], fmt.get())
                ws.write(r, c0 + 1, b["needed"], fmt.get(num="#,##0.##"))
                ws.write(r, c0 + 2, b["unit"] or "", fmt.get())
                ws.write(r, c0 + 3, b["stock"], fmt.get(num="#,##0.##", bg="#FCE4D6" if b["negative"] else None))
                ws.write(r, c0 + 4, b["missing"], fmt.get(num="#,##0.##", bg=status_bg[b["status"]], bold=True))
                ws.write(r, c0 + 5, b["for"], fmt.get())
                ws.write(r, c0 + 6, {"red": "Falta", "yellow": "Por debajo del mínimo", "green": "Alcanza"}[b["status"]], fmt.get(bg=status_bg[b["status"]]))
                r += 1
        ws.freeze_panes(2, c0 + 1)

def data_date(env_model):
    return fields.Date.context_today(env_model).strftime("%d-%m-%Y")


class _Formats:
    """xlsxwriter formats are workbook objects; build each combination once."""

    def __init__(self, wb):
        self.wb = wb
        self.cache = {}

    def get(self, bg=None, color=None, bold=False, align=None, valign=None, num=None, wrap=False, indent=0):
        key = (bg, color, bold, align, valign, num, wrap, indent)
        if key not in self.cache:
            spec = {"border": 1, "border_color": "#BFBFBF", "font_name": "Calibri", "font_size": 11}
            if bg and bg.upper() != "#FFFFFF":
                spec["bg_color"] = bg
            if color:
                spec["font_color"] = color
            if bold:
                spec["bold"] = True
            if align:
                spec["align"] = align
            if valign:
                spec["valign"] = valign
            if num:
                spec["num_format"] = num
            if wrap:
                spec["text_wrap"] = True
            if indent:
                spec["indent"] = indent
            self.cache[key] = self.wb.add_format(spec)
        return self.cache[key]
