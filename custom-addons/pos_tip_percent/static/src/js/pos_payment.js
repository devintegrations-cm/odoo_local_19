/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    async addTip1() {
        await this.addTipPercent(this.pos.config.tip_percent1);
    },
    async addTip2() {
        await this.addTipPercent(this.pos.config.tip_percent2);
    },
    async addTip3() {
        await this.addTipPercent(this.pos.config.tip_percent3);
    },
    getTipX(tipPercent) {
        const order = this.currentOrder;
        return Math.round((order.priceIncl - order.amountTaxes - order.getTip()) * (tipPercent / 100));
    },
    shouldHighlight(tipPercent) {
        const order = this.currentOrder;
        return order.getTip() != 0 && order.getTip() == this.getTipX(tipPercent);
    },
    async addTipPercent(tipPercent) {
        const tipAmount = this.getTipX(tipPercent);
        if (tipAmount == 0) return;
        const previousTip = this.currentOrder.getTip();
        await this.pos.setTip(tipAmount);
        const pLine =
            this.selectedPaymentLine &&
            (!this.selectedPaymentLine.isElectronic() ||
                this.selectedPaymentLine.getPaymentStatus() === "pending")
                ? this.selectedPaymentLine
                : false;
        if (pLine) {
            const tipDifference = tipAmount - previousTip;
            pLine.setAmount(pLine.getAmount() + tipDifference);
        }
    },
});