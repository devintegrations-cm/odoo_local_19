/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { TextInputPopup } from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

// Solo letras y numeros, maximo 11 caracteres.
const VOUCHER_RE = /^[a-zA-Z0-9]{1,11}$/;

patch(PaymentScreen.prototype, {
    /**
     * Si el metodo de pago pide numero de aprobacion, lo pregunta ANTES de crear
     * la linea de pago y lo guarda en `pos.payment.voucher_num` (el store
     * relacional lo sincroniza solo: no hay serializacion manual en Odoo 19).
     *
     * Se llama a `super` en todos los caminos que crean una linea de pago.
     * El unico camino que no llama a `super` es el aborto explicito
     * (cancelacion o voucher invalido), donde crear la linea contradiria el
     * proposito del modulo. Es el mismo patron del core en
     * addons/pos_razorpay/static/src/app/screens/payment_screen/payment_screen.js
     * (return false sin super cuando la operacion no es admisible).
     */
    async addNewPaymentLine(paymentMethod) {
        if (!paymentMethod.ask_for_approval_number) {
            return await super.addNewPaymentLine(...arguments);
        }

        const payload = await makeAwaitable(this.dialog, TextInputPopup, {
            title: _t("Ingrese el número de aprobación"),
            placeholder: _t("Ingrese aquí"),
        });

        if (payload === undefined) {
            // El cajero cancelo el popup: no se agrega la linea de pago.
            return false;
        }

        const voucher = payload.trim();
        if (!this.isValidVoucherNumber(voucher)) {
            this.notification.add(
                _t("Voucher inválido: máximo 11 caracteres entre números y letras"),
                { title: _t("Advertencia"), type: "warning", sticky: true }
            );
            return false;
        }

        const added = await super.addNewPaymentLine(...arguments);
        const newLine = this.selectedPaymentLine;
        if (added && newLine) {
            // `voucher_num` es el nombre real del campo en Python.
            // Tiene que coincidir exacto o el store no lo persiste.
            newLine.voucher_num = voucher;
        }
        return added;
    },

    isValidVoucherNumber(value) {
        return typeof value === "string" && VOUCHER_RE.test(value);
    },
});
