/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

// Odoo 19: la línea ya no se serializa a mano (la serialización de 17 desapareció).
// `reward_related_product_line_id` es un campo de pos.order.line
// que el backend publica en `_load_pos_data_fields`, así que el modelo del POS lo
// carga y lo envía solo al sincronizar la orden. Se asigna en
// `updateRelatedRewards` (order_payment_validation.js).

// Factura obligatoria: las órdenes nuevas nacen marcadas para facturar.
patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        // Solo órdenes editables: una orden pagada/cancelada cargada del servidor
        // no se toca (setToInvoice lanzaría error y además quedaría sucia).
        if (this.config?.enable_obligatory_invoice && !this.finalized) {
            this.to_invoice = true;
        }
    },
});
