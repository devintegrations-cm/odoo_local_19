/** @odoo-module **/
// The plant's workbook inside Odoo: same tabs, rows, colours and columns as the Excel they keep, filled from the
// open orders and the stock at the plant. The only cell they may still type is INVENTARIO.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

export class PlantSheet extends Component {
    static template = "plant_request_board.PlantSheet";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.sheets = [];   // [code, title] of the tabs, as the server defines them
        this.plants = [];   // [{id, name}] of the plants; the selector shows when there is more than one
        this.scopes = [];   // [code, label]: pending, ready, delivered, all
        this.state = useState({ sheet: "tiendas", scope: "open", plantId: null, data: null, loading: true, editing: null });
        onWillStart(async () => {
            [this.sheets, this.plants, this.scopes] = await Promise.all([this.orm.call("plant.sheet", "get_tabs", []), this.orm.call("plant.sheet", "get_plants", []), this.orm.call("plant.sheet", "get_scopes", [])]);
            await this.load();
        });
        useBus(this.env.bus, "plant_request_board:changed", () => this.load(true));   // a new request, a tick or a delivery elsewhere: reload in place
    }

    async load(silent = false) {
        if (!silent) this.state.loading = true;
        this.state.data = await this.orm.call("plant.sheet", "get_data", [], { sheet: this.state.sheet, scope: this.state.scope, plant_id: this.state.plantId });
        this.state.loading = false;
    }
    // ticks of one cell (the lines of that row for that store or order): a visual guide, nothing else changes
    checkIcon(c) { return c[0] >= c[1] ? "fa-check-square x-check-done" : c[0] > 0 ? "fa-minus-square x-check-part" : "fa-square-o x-check-none"; }
    checkTitle(c) { return `${c[0]} de ${c[1]} líneas alistadas. Clic para ${c[0] >= c[1] ? "quitar" : "marcar"} el chuleo.`; }
    async toggleChecks(c) {
        await this.orm.call("plant.sheet", "toggle_checks", [c[2], c[0] < c[1]]);
        await this.load(true);
    }
    stageTitle(col) { return col.stage_label ? `${col.ref || ""} · ${col.stage_label} · ${col.progress || 0} % alistado` : (col.ref || (col.orders ? col.orders + " pedidos" : "")); }
    setSheet(s) { this.state.sheet = s; this.load(); }
    setScope(s) { this.state.scope = s; this.load(); }
    setPlant(v) { this.state.plantId = v ? Number(v) : null; this.load(); }
    exportUrl() { return `/plant_request_board/sheet.xlsx?scope=${this.state.scope}` + (this.state.plantId ? `&plant_id=${this.state.plantId}` : ""); }
    openRows() { this.action.doAction("plant_request_board.action_plant_sheet_rows"); }
    openProducts() { this.action.doAction("plant_request_board.action_plant_products"); }
    openPivot() { this.action.doAction("plant_request_board.action_plant_consolidation"); }
    openOrder(col) {
        if (col.picking_id) {
            this.action.doAction({ type: "ir.actions.act_window", res_model: "stock.picking", res_id: col.picking_id, views: [[false, "form"]] });
        }
    }

    // INVENTARIO: click to type, Enter/blur saves, empty goes back to the stock of Odoo
    inventoryTitle(row) {
        const parts = [];
        if (row.negative) parts.push(`Inventario negativo en Odoo (${this.n(row.inventory_raw, 2, true)}): falta registrar producción/empaque. Se cuenta como cero.`);
        if (row.inventory_manual) parts.push(`Digitado por la planta. Existencias en Odoo: ${this.n(row.inventory_auto, 2, true)}. Borra el valor para volver a Odoo.`);
        else parts.push("Existencias en planta según Odoo. Clic para digitar.");
        return parts.join(" ");
    }
    editInventory(row) { this.state.editing = row.id; }
    async saveInventory(row, ev) {
        const raw = (ev.target.value || "").trim().replace(",", ".");
        this.state.editing = null;
        if (raw !== "" && isNaN(Number(raw))) {
            this.notification.add("Escribe un número", { type: "warning" });
            return;
        }
        await this.orm.call("plant.sheet", "set_inventory", [row.id, raw === "" ? false : Number(raw)]);
        await this.load();
    }
    onInventoryKey(row, ev) {
        if (ev.key === "Enter") ev.target.blur();
        if (ev.key === "Escape") this.state.editing = null;
    }

    // number as the plant writes it: no decimals for bags, up to 3 for kilos; empty for zero unless asked
    n(v, dec = 0, showZero = false) {
        if (v === undefined || v === null || v === "" || (!showZero && Math.abs(v) < 1e-9)) return "";
        const rounded = Number(v);
        return rounded.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: dec });
    }
    // the workbook writes every item in black bold over its line colour, even on magenta or red
    rowStyle(row) { return `background-color: ${row.color || "#FFFFFF"}; color: #000;`; }
    get d() { return this.state.data; }
    get showTotal() { return this.d.mode !== "orders" || this.d.sheet !== "attenza" || this.d.columns.length !== 1; }
    get columns() {
        if (this.d.columns.length) return this.d.columns;
        return this.d.sheet === "attenza" ? [{ key: "_", name: "ATTENZA", date: null, picking_id: null }] : [];
    }
    get rightCols() {
        // TOTAL BOLSAS, INVENTARIO, POR FABRICAR, TOSTAR, TOTAL NETO, [CAJAS, lotes, vencimiento]
        let n = 2;   // TOSTAR + TOTAL NETO
        if (this.showTotal) n += 1;
        if (this.d.has_inventory) n += 2;
        if (this.d.has_boxes) n += 3;
        return n;
    }
}

registry.category("actions").add("plant_request_board.sheet", PlantSheet);
