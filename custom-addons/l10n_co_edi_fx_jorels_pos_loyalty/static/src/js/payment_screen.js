/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.enableOdooInvoice();
    },

    async toggleIsToInvoice() {
        // Con Jorels la factura siempre queda seleccionada (igual que en 17). Se encadena primero para que
        // corran los demás parches (aviso de obligatory_invoice_msg, guarda de pos_settle_due, aviso del
        // núcleo si la caja no tiene diario de facturas) y después se restablece la marca.
        await super.toggleIsToInvoice(...arguments);
        this.enableOdooInvoice();
    },

    enableOdooInvoice() {
        const order = this.currentOrder;
        if (order && !order.finalized) {
            order.setToInvoice(true);
        }
    },
});
