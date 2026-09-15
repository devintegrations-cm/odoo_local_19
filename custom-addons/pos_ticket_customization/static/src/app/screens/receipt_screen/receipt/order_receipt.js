/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

// En Odoo 19 el `OrderReceipt` no tiene `setup()` propio y recibe el `pos.order`
// vivo como `props.order`. Sin `setup()` no hay `this.pos` (el template heredado
// no puede usar hooks), así que lo creamos aquí; como la base de OWL es un no-op
// no hace falta llamar a `super.setup()`.
patch(OrderReceipt.prototype, {
    setup() {
        this.pos = usePos();
    },

    /**
     * Bloques aplicables al pedido, resueltos por el store. El template heredado
     * (`order_receipt.xml`) los referencia desde el nuevo método del store, que
     * en Odoo 19 recibe el `pos.order` vivo en lugar de datos serializados.
     */
    get customReceiptBlocks() {
        return this.pos.getCustomReceiptBlocks(this.order);
    },
});