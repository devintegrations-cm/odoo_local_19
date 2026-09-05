/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ConnectionLostError } from "@web/core/network/rpc";
import { uuidv4 } from "@point_of_sale/utils";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

/**
 * Cash In/Out popup: movement limit, last-movement warning and idempotency key.
 *
 * EXTENSION SEAMS used by pos_cash_in_out_message (which patches this same
 * component and calls `super.confirm()`):
 *
 *   getCashMoveControl()        -> { count, limit }   count === null: unknown
 *   isCashMoveBlocked()         -> limit reached or the server refused the data
 *   isLastCashMove()            -> this movement would consume the last slot
 *   _isLastMovement()           -> legacy alias of isLastCashMove()
 *   setLastMoveWarningSkipped(v) -> suppress the last-movement warning once
 *   state.isLimitReached / state.loadError / state.offline
 *
 * The popup fetches its own data instead of relying on the store: a popup that
 * silently assumes "0 movements" would disable the control altogether.
 */
patch(CashMovePopup.prototype, {
    setup() {
        super.setup(...arguments);

        // One uuid per popup instance == one logical movement.  Confirming
        // again after a failed request, or the offline queue replaying the
        // same payload, reuses it, so the server can recognise the retry
        // instead of writing a second movement.
        this.cashMoveUuid = uuidv4();
        this.cashMoveControl = {
            count: null,
            limit: this.pos.config.maximum_cash_in_out_moves || 0,
        };
        this.closingValidation = this.pos.closingValidationInfo || null;
        this._skipCashMoveWarning = false;
        this._offlineAcknowledged = false;

        this.state.isLimitReached = false;
        this.state.loadError = false;
        this.state.offline = false;

        onWillStart(async () => {
            try {
                const control = await this.pos.data.call(
                    "pos.session",
                    "get_cash_in_out_control_data",
                    [[this.pos.session.id]]
                );
                this.cashMoveControl = { count: control.count, limit: control.limit };
                this.state.isLimitReached = control.count >= control.limit;
            } catch (error) {
                if (error instanceof ConnectionLostError) {
                    // Unknown count: warn and let the cashier proceed, the
                    // server enforces the limit when the movement syncs.
                    this.state.offline = true;
                } else {
                    // The server answered and refused: fail closed.
                    this.state.loadError = true;
                    this.state.isLimitReached = true;
                }
            }
        });
    },

    getCashMoveControl() {
        return this.cashMoveControl;
    },

    isCashMoveBlocked() {
        return this.state.isLimitReached || this.state.loadError;
    },

    isLastCashMove() {
        const { count, limit } = this.getCashMoveControl();
        return count !== null && count + 1 === limit;
    },

    _isLastMovement() {
        return this.isLastCashMove();
    },

    setLastMoveWarningSkipped(skipped) {
        this._skipCashMoveWarning = skipped;
    },

    _prepareTryCashInOutPayload(type, amount, reason, partnerId, extras) {
        return super._prepareTryCashInOutPayload(type, amount, reason, partnerId, {
            ...(extras || {}),
            cash_move_uuid: this.cashMoveUuid,
        });
    },

    async confirm() {
        if (this.isCashMoveBlocked()) {
            return;
        }

        if (this.state.offline && !this._offlineAcknowledged) {
            const confirmed = await ask(this.dialog, {
                title: _t("Sin conexión con el servidor"),
                body: _t(
                    "El límite de movimientos de efectivo de esta sesión no se " +
                    "pudo verificar.\n\n" +
                    "El movimiento se guardará localmente y se comprobará el " +
                    "límite cuando haya conexión."
                ),
                confirmLabel: _t("Registrar de todos modos"),
                cancelLabel: _t("Cancelar"),
            });
            if (!confirmed) {
                return;
            }
            this._offlineAcknowledged = true;
        }

        if (this.isLastCashMove() && !this._skipCashMoveWarning) {
            const { count, limit } = this.getCashMoveControl();
            const confirmed = await ask(this.dialog, {
                title: _t("Último movimiento de efectivo"),
                body: _t(
                    "Este será el último movimiento Cash In/Out permitido para " +
                    "esta sesión.\n\n" +
                    "Movimientos: %(current)s/%(limit)s\n\n" +
                    "¿Desea continuar?",
                    { current: count + 1, limit: limit }
                ),
                confirmLabel: _t("Confirmar"),
                cancelLabel: _t("Cancelar"),
            });
            if (!confirmed) {
                return;
            }
        }

        return super.confirm(...arguments);
    },
});
