/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Restricts order deletion to the employees configured on the point of sale.
 *
 * The guard belongs to `beforeDeleteOrder` (the core hook that every deletion
 * path goes through) and not to the ticket screen: the delete button of the
 * product screen calls `pos.onDeleteOrder` directly, so a ticket-screen-only
 * check left a bypass.  `shouldHideDeleteButton` is patched as well so the icon
 * disappears instead of answering with an error.
 */
patch(PosStore.prototype, {
    async beforeDeleteOrder(order, options) {
        if (!this.isEmployeeAllowedToDeleteOrders()) {
            this.dialog.add(AlertDialog, {
                title: _t("Advertencia"),
                body: _t(
                    "No tiene permisos para eliminar una orden, contacte al líder de tienda."
                ),
            });
            return false;
        }
        return super.beforeDeleteOrder(order, options);
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
        const allowed = this._allowedDeletionEmployeeIds();
        if (!allowed.length) {
            // Empty configuration keeps the historical behaviour: everyone.
            return true;
        }
        const cashier = this.cashier ?? this.getCashier();
        return Boolean(cashier && allowed.includes(cashier.id));
    },
});
