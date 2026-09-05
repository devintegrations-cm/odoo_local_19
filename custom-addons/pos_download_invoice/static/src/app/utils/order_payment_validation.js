import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    /**
     * El PDF de la factura solo se descarga al validar el pedido si la
     * configuracion del PdV lo habilita. Si no, se factura igual pero sin
     * abrir la descarga.
     */
    shouldDownloadInvoice() {
        if (!this.pos.config.enable_download_invoice) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },
});
