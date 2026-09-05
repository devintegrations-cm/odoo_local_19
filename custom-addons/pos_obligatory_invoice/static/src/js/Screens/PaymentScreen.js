/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        // Otros modulos (pos_voucher_num, ar_partner_pos) parchean este mismo
        // metodo: la cadena de super() no se puede cortar nunca.
        super.setup();
        this.forceObligatoryInvoice();
    },

    /**
     * `enable_obin` llega al POS sin loader: pos.config no define
     * _load_pos_data_fields, el mixin devuelve [] y read([]) lee todos los
     * campos (odoo/orm/models.py:3484).
     * Se exige ademas `canInvoice` (pos_config.js:72): sin diario de facturas
     * el POS no puede facturar y forzar el flag dejaria el pedido imposible de
     * validar.
     */
    isObinEnable() {
        return Boolean(this.pos.config.enable_obin) && Boolean(this.pos.config.canInvoice);
    },

    forceObligatoryInvoice() {
        const order = this.currentOrder;
        // currentOrder puede no existir: useRouterParamsChecker redirige pero
        // el setup del componente termina igual (pos_router_hook.js:12-18).
        // Un pedido finalizado no admite setToInvoice (pos_order.js:287).
        if (!order || order.finalized || !this.isObinEnable()) {
            return;
        }
        if (!order.isToInvoice()) {
            order.setToInvoice(true);
        }
    },

    async toggleIsToInvoice() {
        // Encadenamos siempre y recien despues restablecemos el invariante,
        // en vez de cortar la cadena con un return anticipado.
        await super.toggleIsToInvoice(...arguments);
        const order = this.currentOrder;
        if (!order || order.finalized || !this.isObinEnable()) {
            return;
        }
        if (!order.isToInvoice()) {
            order.setToInvoice(true);
            this.notification.add(
                _t("Este punto de venta exige facturar todos los pedidos."),
                { type: "warning" }
            );
        }
    },
});
