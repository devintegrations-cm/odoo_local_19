/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { TextInputPopup } from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { isValidVoucherNumber } from "@pos_voucher_num/app/payment_screen";

/**
 * El pago rapido de Odoo 19 (`use_fast_payment`) no pasa por
 * PaymentScreen.addNewPaymentLine: OrderPaymentValidation.setup agrega la
 * linea con order.addPaymentline (order_payment_validation.js:31-32), asi que
 * el popup del voucher no se mostraba. Los dos caminos de validacion terminan
 * en validateOrder, que empieza por askBeforeValidation (linea 104): ahi se
 * pide el voucher de toda linea que lo exija y no lo tenga. Mismo patron que
 * l10n_cl_edi_pos (Enterprise), que pide su voucher en este gancho.
 * Desde la PaymentScreen las lineas ya traen el voucher, asi que no se
 * pregunta dos veces.
 *
 * Portado de Costa Rica (fd91238). Cierra POS-FASTPAY-FE-0001 para el voucher.
 */
patch(OrderPaymentValidation.prototype, {
    setup(vals) {
        super.setup(...arguments);
        // Linea creada por el pago rapido, para quitarla si no se registra el
        // voucher y no dejarla colgada en el pedido.
        this.voucherFastPaymentLine = vals.fastPaymentMethod
            ? this.order?.getSelectedPaymentline()
            : undefined;
    },

    async askBeforeValidation() {
        const order = this.order;
        const missing = (order?.payment_ids || []).filter(
            (line) =>
                line.payment_method_id?.ask_for_approval_number &&
                !line.voucher_num &&
                line.amount !== 0
        );
        for (const line of missing) {
            const payload = await makeAwaitable(this.pos.dialog, TextInputPopup, {
                title: _t("Ingrese el número de aprobación (%s)", line.payment_method_id.name),
                placeholder: _t("Ingrese aquí"),
            });
            const voucher = payload === undefined ? undefined : payload.trim();
            if (voucher !== undefined && !isValidVoucherNumber(voucher)) {
                this.pos.notification.add(
                    _t("Voucher inválido: máximo 11 caracteres entre números y letras"),
                    { title: _t("Advertencia"), type: "warning", sticky: true }
                );
            }
            if (voucher === undefined || !isValidVoucherNumber(voucher)) {
                // Cancelado o invalido: no se valida, como en la PaymentScreen.
                if (line === this.voucherFastPaymentLine && !order.finalized) {
                    order.removePaymentline(line);
                }
                return false;
            }
            // `voucher_num` es el nombre real del campo en Python (19.0.1.1.0).
            line.voucher_num = voucher;
        }
        return await super.askBeforeValidation(...arguments);
    },
});
