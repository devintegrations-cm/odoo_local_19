/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { CashMoveConfirmPopup } from "@pos_cash_in_out_message/js/cash_move_confirm_popup";

/**
 * Asks for confirmation, showing the configured message, before a Cash In/Out
 * movement is registered.
 *
 * The cash-control state (limit reached, offline, last movement) is owned by
 * pos_closing_validation, which patches this same component and documents these
 * seams: isCashMoveBlocked(), isLastCashMove() and setLastMoveWarningSkipped().
 * This module only renders the branded confirmation on top of them, so a change
 * in those names must be done in both modules at once.
 */
patch(CashMovePopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.cashInOutMessage = this.pos.config.cash_in_out_message_enabled
            ? (this.pos.config.cash_in_out_message || "")
            : "";
    },

    async confirm() {
        if (this.isCashMoveBlocked()) {
            return;
        }

        const amount = parseFloat(this.state.amount);
        if (!amount) {
            // Nothing to confirm: let the standard popup report the ignored amount.
            return super.confirm(...arguments);
        }

        const response = await makeAwaitable(this.dialog, CashMoveConfirmPopup, {
            title: _t("Confirmar movimiento de efectivo"),
            type: this.state.type,
            formattedAmount: this.env.utils.formatCurrency(amount),
            isLastMovement: this.isLastCashMove(),
            configMessage: this.cashInOutMessage,
            confirmLabel: _t("Sí, registrar"),
            cancelLabel: _t("Cancelar"),
        });

        if (!response || !response.confirmed) {
            return;
        }

        // The last-movement warning is already part of this dialog, so the plain
        // one that pos_closing_validation shows on the standard path is skipped.
        this.setLastMoveWarningSkipped(true);
        try {
            await super.confirm(...arguments);
        } finally {
            this.setLastMoveWarningSkipped(false);
        }
    },
});
