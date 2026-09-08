/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

/**
 * Asks for the number of customers when the payment screen is opened.
 *
 * The prompt used to be tied to the order validation
 * (`OrderPaymentValidation.askBeforeValidation`), so it appeared on the
 * "Validate" click, at the very end of the payment flow.  The operation wants
 * the count captured up front, as soon as the cashier enters the payment
 * screen and before any payment method is chosen or processed.  `onMounted` is
 * the same hook the core terminal integrations use to run once the screen is
 * ready.
 *
 * The validation-time ask is kept only as a fallback: if the cashier dismissed
 * the prompt on entry, the count is still required before the order can be
 * validated (the feature is "obligatory").  When it was already answered on
 * entry, neither hook asks twice, because both gate on `hasCustomerCount`.
 */
/**
 * One-shot check per order.  `customer_count` cannot be used for this: pos_restaurant
 * defaults it to 1 on order creation (`this.customer_count = this.customer_count || 1`),
 * so it is truthy even when the cashier was never asked.  A non-serialised flag on the
 * order record marks that the question was already answered in this payment flow; the
 * validation fallback only fires when the entry prompt was dismissed.
 */
function shouldAsk(pos, order) {
    return Boolean(
        pos.config.enable_obligatory_ask_number_customers &&
            order &&
            !order._customersAsked
    );
}

async function askNumberOfCustomers(pos, order) {
    const config = pos.config;
    const minimum = config.number_customers_min || 1;
    const maximum = config.number_customers_max || 20;

    const value = await makeAwaitable(pos.dialog, NumberPopup, {
        title: _t("Número de clientes"),
        subtitle: _t("¿Para cuántos clientes es este pedido?"),
        startingValue: String(order.getCustomerCount?.() || 0),
    });

    if (value === undefined) {
        // Dismissed or cancelled.  On entry the cashier can still proceed and
        // will be asked again at validation; at validation it blocks, leaving
        // the order unpaid.
        return false;
    }

    const count = parseInt(value, 10);
    if (Number.isNaN(count) || count < minimum || count > maximum) {
        pos.dialog.add(AlertDialog, {
            title: _t("Acción bloqueada"),
            body: _t(
                "El número de clientes debe estar entre %(min)s y %(max)s.",
                { min: minimum, max: maximum }
            ),
        });
        return false;
    }

    order.setCustomerCount(count);
    order._customersAsked = true;
    return true;
}

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // this.dialog and this.currentOrder are provided by the core screen.
        onMounted(() => {
            if (shouldAsk(this.pos, this.currentOrder)) {
                this._askNumberOfCustomersOnOpen();
            }
        });
    },

    async _askNumberOfCustomersOnOpen() {
        await askNumberOfCustomers(this.pos, this.currentOrder);
    },
});

patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        if ((await super.askBeforeValidation(...arguments)) === false) {
            return false;
        }
        // Only reached when the count was never captured (the entry prompt was
        // dismissed, or the order was validated without opening the payment
        // screen, e.g. a quick validation).
        if (!shouldAsk(this.pos, this.order)) {
            return true;
        }
        return askNumberOfCustomers(this.pos, this.order);
    },
});
