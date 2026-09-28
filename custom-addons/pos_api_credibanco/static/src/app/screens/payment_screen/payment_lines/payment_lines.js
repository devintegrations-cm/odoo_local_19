import { patch } from "@web/core/utils/patch";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreenPaymentLines.prototype, {
    getSendButtonLabel(line) {
        if (line.payment_method_id.use_payment_terminal === 'credibanco') {
            // The button recovers instead of charging while a sale is pending
            // (see PaymentCredibanco.sendPaymentRequest).
            if (line.credibanco_pending_sale) {
                return _t("Recuperar venta");
            }
            return _t("Enviar a Datafono");
        }
        return _t("Send");
    },

    canForceDone(line) {
        return line.payment_method_id.use_payment_terminal !== 'credibanco';
    },
});

