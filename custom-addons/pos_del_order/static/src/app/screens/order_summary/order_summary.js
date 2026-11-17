/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";

/**
 * "Release table" (pos_restaurant) cancels the order through `deleteOrders`,
 * without `beforeDeleteOrder`.  An employee without permission could empty an
 * order already saved on the server and cancel it this way.
 *
 * Only orders that exist on the server are guarded: a table opened by mistake
 * and never saved is still released, as the core does.  pos_restaurant is a
 * dependency so that this patch wraps its `unbookTable`.
 */
patch(OrderSummary.prototype, {
    async unbookTable() {
        const order = this.pos.getOrder();
        if (order?.isSynced && !this.pos.isEmployeeAllowedToDeleteOrders()) {
            this.pos.alertDeleteOrderNotAllowed();
            return;
        }
        return super.unbookTable(...arguments);
    },
});
