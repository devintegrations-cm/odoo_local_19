/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    /**
     * El envío del recibo por correo no pasa por `PrinterService`: rasteriza el
     * ticket a JPEG con `renderer.toJpeg()`, que también usa `htmlToCanvas` y por
     * tanto su caché de recursos rota. Hay que incrustar los códigos antes.
     *
     * Se engancha en `_sendReceiptToCustomer` (no en `generateTicketImage`, que
     * en Odoo 19 es una *class field* y no se puede sobrescribir por prototipo).
     * Basta con calentar la caché del store: el `super` vuelve a renderizar el
     * recibo y esa segunda pasada ya recoge las imágenes incrustadas.
     */
    async _sendReceiptToCustomer(arg) {
        await this.pos.resolveCustomReceiptBlockImages(
            this.pos.getCustomReceiptBlocks(this.currentOrder)
        );
        return await super._sendReceiptToCustomer(...arguments);
    },
});