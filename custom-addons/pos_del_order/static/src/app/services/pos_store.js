/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Restricts order deletion to the employees configured on the point of sale.
 *
 * The guard belongs to `beforeDeleteOrder` (the hook of `onDeleteOrder`) and
 * not to the ticket screen: the delete button of the product screen calls
 * `pos.onDeleteOrder` directly, so a ticket-screen-only check left a bypass.
 * "Release table" of pos_restaurant calls `deleteOrders` without that hook; it
 * is guarded in order_summary.js.  `shouldHideDeleteButton` is patched as well
 * so the icon disappears instead of answering with an error.
 */
patch(PosStore.prototype, {
    async beforeDeleteOrder(order, options) {
        if (!this.isEmployeeAllowedToDeleteOrders()) {
            this.alertDeleteOrderNotAllowed();
            return false;
        }
        return super.beforeDeleteOrder(order, options);
    },

    alertDeleteOrderNotAllowed() {
        this.dialog.add(AlertDialog, {
            title: _t("Advertencia"),
            body: _t("No tiene permisos para eliminar una orden, contacte al líder de tienda."),
        });
    },

    /**
     * Employee list of the config, as ids.
     *
     * Read from `raw`: the relation points to hr.employee and the store only
     * guarantees the ids of the currently logged cashier, so the relational
     * getter may return records of employees it never loaded.
     */
    _allowedDeletionEmployeeIds() {
        const raw =
            this.config.raw?.able_del_employee_ids ?? this.config.able_del_employee_ids ?? [];
        return (Array.isArray(raw) ? raw : [])
            .map((item) => (typeof item === "object" && item !== null ? item.id : item))
            .filter((id) => typeof id === "number");
    },

    isEmployeeAllowedToDeleteOrders() {
        if (!this.config.module_pos_hr) {
            // Sin login de empleados el cajero es un res.users: su id no se
            // puede comparar con ids de hr.employee, asi que la regla no aplica
            // (ed0a689, Colombia). En staging/prod la unica caja sin pos_hr
            // tiene la lista vacia: no cambia el comportamiento de 17.
            return true;
        }
        const allowed = this._allowedDeletionEmployeeIds();
        if (!allowed.length) {
            // Empty configuration keeps the historical behaviour: everyone.
            return true;
        }
        const cashier = this.cashier ?? this.getCashier();
        return Boolean(cashier && allowed.includes(cashier.id));
    },
});
