/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { posRestrictState } from "@pos_restrict_del_ordered_order_line/js/models";

patch(PosStore.prototype, {
    async setup(...args) {
        // Exponemos el store a los modelos de datos (guards de cantidad)
        posRestrictState.pos = this;
        return super.setup(...args);
    },

    /**
     * Guarda la cantidad actual de cada linea como "cantidad ordenada"
     * (enviada a cocina), igual que hacia el patch de submitOrder en v17.
     */
    _captureOrderedQuantities() {
        const order = this.getOrder();
        if (!order) {
            return;
        }
        for (const line of order.getOrderlines()) {
            if (!line.is_reward_line) {
                line.ordered_quantities = line.getQuantity();
            }
        }
    },

    // Boton "Order" (enviar a cocina) en modo restaurante
    async submitOrder() {
        this._captureOrderedQuantities();
        return super.submitOrder(...arguments);
    },

    // Boton "Payment": en v17 ambos botones pasaban por submitOrder
    async pay() {
        this._captureOrderedQuantities();
        return super.pay(...arguments);
    },
});
