/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

// Statuses in which the core itself sends the protocol cancellation on delete.
const TERMINAL_BUSY_STATUSES = ["waiting", "waitingCard", "timeout", "waitingCancel"];

/**
 * A Credibanco line whose sale never got a final answer: the terminal may have
 * approved it, so it must be recovered before the order moves on.
 */
function isPendingCredibancoLine(line) {
    return Boolean(
        line.payment_method_id.use_payment_terminal === "credibanco" &&
            line.credibanco_pending_sale &&
            !line.isDone()
    );
}

/**
 * Credibanco on the payment screen: recovery and the anulación guard.
 *
 * - Recovery: the terminal may approve a sale whose answer never reached the
 *   browser (page reload, network drop). The line stays pending in the order, so
 *   on mount the cashier is asked before anything else: charging again would bill
 *   the customer twice, and walking away leaves money in the terminal without a
 *   payment in Odoo.
 * - Anulación guard: cancelling a Credibanco payment registers a compensating
 *   negative line (the Odoo 17 way, kept for the bank statement and accounting).
 *   That line has no electronic status, so the core would otherwise show its
 *   delete button; deleting it would undo the reversal in Odoo while the acquirer
 *   keeps the cancellation. It is refused here.
 */
patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // this.dialog is already provided by the core screen.
        onMounted(() => this._recoverCredibancoPendingLine());
    },

    deletePaymentLine(uuid) {
        const line = this.paymentLines.find((line) => line.uuid === uuid);
        if (line && line.credibanco_anulation_of) {
            this.dialog.add(AlertDialog, {
                title: _t("No puede eliminar la anulación"),
                body: _t(
                    "Esta línea compensa una anulación ya registrada en el " +
                        "datáfono. Eliminarla dejaría la venta pagada en Odoo " +
                        "mientras el adquirente mantiene la devolución. Registre " +
                        "la corrección con el datáfono o avise a IT."
                ),
            });
            return;
        }
        if (
            line &&
            isPendingCredibancoLine(line) &&
            !TERMINAL_BUSY_STATUSES.includes(line.getPaymentStatus())
        ) {
            return this._deletePendingCredibancoLine(line, arguments);
        }
        return super.deletePaymentLine(...arguments);
    },

    /**
     * Deleting a line with a pending sale drops the only record of a charge that
     * may be approved on the terminal. It is only allowed after the cashier
     * states that the terminal shows the sale was NOT approved.
     */
    async _deletePendingCredibancoLine(line, args) {
        const confirmed = await ask(this.dialog, {
            title: _t("Venta pendiente en el datáfono"),
            body: _t(
                "Este pago tiene una venta sin respuesta final: puede estar " +
                    "aprobada en el terminal. Use «Recuperar venta» para conocer " +
                    "su estado.\n\n" +
                    "Elimínelo solo si ya verificó en el datáfono (TECLA 3 y luego " +
                    "TECLA 9) que la venta NO fue aprobada."
            ),
            confirmLabel: _t("Verifiqué que no fue aprobada: eliminar"),
            cancelLabel: _t("Volver"),
        });
        if (!confirmed) {
            return;
        }
        line.credibanco_pending_sale = "";
        return super.deletePaymentLine(...args);
    },

    async _recoverCredibancoPendingLine() {
        // Not `pos.getPendingPaymentLine`: the core skips lines in `retry`, which
        // is exactly where a sale without answer is left.
        const line = this.paymentLines.find(isPendingCredibancoLine);
        const terminal = line?.payment_method_id.payment_terminal;
        if (!terminal) {
            return;
        }
        const wantsRecovery = await ask(this.dialog, {
            title: _t("Venta pendiente en el datáfono"),
            body: _t(
                "Hay una venta Credibanco sin respuesta final. Recupere su " +
                    "estado antes de continuar: en el datáfono, TECLA 3 y luego " +
                    "TECLA 9."
            ),
            confirmLabel: _t("Recuperar"),
            cancelLabel: _t("Más tarde"),
        });
        if (wantsRecovery) {
            await terminal.recoverPendingPayment(line);
        }
    },

    async sendForceDone(line) {
        if (line.payment_method_id.use_payment_terminal === 'credibanco') {
            //Para credibanco no se permite forzar el pago, ya que puede generar inconsistencias entre el POS y el datáfono.
            this.dialog.add(AlertDialog, { 
                title: _t("No se puede forzar el pago"),
                body: _t("Use Recuperar venta pendiente para sincronizar el estado del pago con el datáfono."),
            });
            return;
        }
        return super.sendForceDone(line);
    },

});

/**
 * The core validation silently removes every payment line that is not `done`.
 * For a Credibanco line with a pending sale that would erase a charge that may
 * be approved on the terminal (e.g. the cashier completes the order in cash), so
 * the order cannot be validated until the sale is recovered or discarded.
 */
patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        if (this.order.payment_ids.some(isPendingCredibancoLine)) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Venta pendiente en el datáfono"),
                body: _t(
                    "Hay un pago Credibanco sin respuesta final. Use «Recuperar " +
                        "venta» en esa línea antes de validar el pedido, para no " +
                        "cobrar dos veces ni dejar un cobro sin registrar."
                ),
            });
            return false;
        }
        return super.askBeforeValidation(...arguments);
    },
});
