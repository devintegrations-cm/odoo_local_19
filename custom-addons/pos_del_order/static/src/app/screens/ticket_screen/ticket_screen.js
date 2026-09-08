/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

/**
 * Hides the delete icon for employees that are not allowed to delete orders.
 *
 * The prohibition itself lives in `beforeDeleteOrder` (pos_store_patch), which
 * every deletion path goes through; this only keeps the interface from offering
 * an action that would be refused.
 */
patch(TicketScreen.prototype, {
    shouldHideDeleteButton(order) {
        if (super.shouldHideDeleteButton(order)) {
            return true;
        }
        return !this.pos.isEmployeeAllowedToDeleteOrders();
    },
});
