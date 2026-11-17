/** @odoo-module **/

import { SplitBillScreen } from "@pos_restaurant/app/screens/split_bill_screen/split_bill_screen";
import { patch } from "@web/core/utils/patch";

patch(SplitBillScreen.prototype, {
    /**
     * En Odoo 19 el metodo es `createSplittedOrder` (era `proceed` en v17).
     * Tras dividir la cuenta, las cantidades resultantes en ambas ordenes
     * pasan a ser las cantidades ya ordenadas.
     */
    async createSplittedOrder() {
        const originalOrder = this.currentOrder;
        const originalUuid = originalOrder?.uuid;

        await super.createSplittedOrder(...arguments);

        // super() selecciona la nueva orden como orden actual; si el split
        // no ocurrio (guard isSplitInProgress), la orden actual sigue siendo
        // la original y no hacemos nada.
        const newOrder = this.pos.getOrder();
        if (newOrder && newOrder.uuid !== originalUuid) {
            const original = this.updateOrderedQuantitiesByUuid(originalUuid);
            this.updateOrderedQuantities(newOrder);
            // super() ya sincronizo las dos ordenes (syncAllOrders) ANTES de este parche, asi que
            // las cantidades ordenadas nuevas no llegaban al servidor: al recargar volvian las
            // viejas. Se vuelven a sincronizar.
            const orders = [original, newOrder].filter(Boolean);
            if (orders.length) {
                await this.pos.syncAllOrders({ orders });
            }
        }
    },

    updateOrderedQuantitiesByUuid(uuid) {
        if (!uuid) {
            return;
        }
        const order = this.pos.models["pos.order"].find((o) => o.uuid === uuid);
        this.updateOrderedQuantities(order);
        return order;
    },

    updateOrderedQuantities(order) {
        if (!order) {
            return;
        }
        for (const line of order.getOrderlines()) {
            // update() marca la linea como modificada para que syncAllOrders la envie
            line.update({ ordered_quantities: line.getQuantity() });
        }
    },
});
