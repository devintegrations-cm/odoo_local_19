/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ConnectionLostError } from "@web/core/network/rpc";
import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Cash validation gates for the POS interface.
 *
 * In Odoo 19 the navbar template calls `pos.cashMove()` and
 * `pos.closeSession()` directly (see point_of_sale navbar.xml), so the store is
 * the only place where both the navbar button and the closing popup's own
 * "Cash In/Out" button are intercepted with a single patch.
 *
 * Every rule is decided by the server (`get_closing_validation_info`); this
 * layer only translates the answer into UI and never relaxes it.
 */

// `ClosePosPopup.cashMove()` closes itself and starts the closing flow without
// looking at the result of `pos.cashMove()`. Returning this sentinel lets that
// caller keep the closing popup open when the movement was refused.
const CASH_MOVE_BLOCKED = "pos_closing_validation.blocked";

patch(PosStore.prototype, {
    async setup() {
        // Snapshot consumed by cash_move_popup_patch.js and by the closing
        // popup template extension. Declared before super.setup() so it always
        // exists: a missing summary hides itself instead of breaking the popup.
        this.closingValidationInfo = null;
        await super.setup(...arguments);
    },

    /**
     * @returns {Promise<{info: Object|null, offline: boolean}>}
     */
    async _getCashValidationSnapshot() {
        try {
            const info = await this.data.call(
                "pos.session",
                "get_closing_validation_info",
                [[this.session.id]]
            );
            return { info, offline: false };
        } catch (error) {
            return { info: null, offline: error instanceof ConnectionLostError };
        }
    },

    _alertReload(title, body) {
        this.dialog.add(AlertDialog, {
            title,
            body,
            confirmLabel: _t("Actualizar la página"),
            confirm: () => window.location.reload(),
        });
        return CASH_MOVE_BLOCKED;
    },

    _alert(title, body) {
        this.dialog.add(AlertDialog, { title, body });
        return CASH_MOVE_BLOCKED;
    },

    async cashMove() {
        const { info, offline } = await this._getCashValidationSnapshot();

        if (!info && !offline) {
            return this._alert(
                _t("Error de conexión"),
                _t(
                    "No se pudo obtener la información de la sesión. " +
                    "Verifique su conexión e intente de nuevo."
                )
            );
        }

        this.closingValidationInfo = info || null;

        if (offline) {
            // Fail open on purpose: the movement is queued by the POS and the
            // server enforces the limit when it synchronises. Refusing to touch
            // the drawer while the line is down would stop a store from
            // handling cash exactly when it needs to.
            const confirmed = await ask(this.dialog, {
                title: _t("Sin conexión con el servidor"),
                body: _t(
                    "No es posible verificar cuántos movimientos de efectivo " +
                    "lleva registrados en esta sesión.\n\n" +
                    "El movimiento se guardará localmente y el límite se " +
                    "comprobará cuando haya conexión.\n\n" +
                    "¿Desea registrar el movimiento de todos modos?"
                ),
                confirmLabel: _t("Registrar de todos modos"),
                cancelLabel: _t("Cancelar"),
            });
            if (!confirmed) {
                return CASH_MOVE_BLOCKED;
            }
        } else if (info.is_rescue) {
            return this._alertReload(
                _t("Sesión no sincronizada"),
                _t(
                    "El Punto de Venta no está sincronizado con la sesión " +
                    "actual. Actualice la página y vuelva a intentarlo."
                )
            );
        } else if (info.state !== "opened") {
            return this._alertReload(
                _t("Sesión no disponible"),
                _t(
                    "Esta sesión no está disponible para operaciones de " +
                    "efectivo. Actualice la página para continuar."
                )
            );
        }

        return super.cashMove(...arguments);
    },

    async closeSession() {
        const { info } = await this._getCashValidationSnapshot();

        if (!info) {
            return this._alert(
                _t("Error de conexión"),
                _t(
                    "No se pudo obtener la información de cierre. Verifique su " +
                    "conexión e intente de nuevo."
                )
            );
        }

        this.closingValidationInfo = info;

        if (info.is_rescue) {
            return this._alertReload(
                _t("Actualice la página"),
                _t(
                    "Esta sesión es de rescate y tiene órdenes pendientes. " +
                    "Actualice la página para sincronizar los datos correctamente."
                )
            );
        }

        if (!info.can_close) {
            const reasons = (info.blocking_reasons || []).join("\n\n");
            return this._alert(
                _t("No se puede cerrar la sesión"),
                reasons || _t("Esta sesión no puede cerrarse en este momento.")
            );
        }

        return super.closeSession(...arguments);
    },
});

patch(ClosePosPopup.prototype, {
    /**
     * Keep the closing popup open when the cash movement was refused, instead of
     * falling through to the closing flow (core ignores the returned value).
     */
    async cashMove() {
        const result = await this.pos.cashMove();
        if (result === CASH_MOVE_BLOCKED) {
            return;
        }
        this.dialog.closeAll();
        this.pos.closeSession();
    },

    /**
     * Renders our closing errors with the actions that fit them.
     *
     * Odoo's handler assumes every unsuccessful answer means "there are orders
     * left open" and offers Cancel Orders as the secondary button, which
     * cancels every non-finalized order of this terminal and retries the
     * closing.  For a cash-difference message that button is a data loss trap:
     * the cashier only wants to go back and count again.  The server tells us
     * which case it is through `cash_validation` / `show_orders_action`.
     */
    handleClosingError(response) {
        if (!response.cash_validation) {
            return super.handleClosingError(...arguments);
        }

        if (response.redirect) {
            return this.pos.router.close();
        }

        const title = response.title || _t("No se puede cerrar la sesión");

        if (!response.show_orders_action) {
            // Nothing to review in the orders: acknowledge and stay on the popup.
            return this.dialog.add(AlertDialog, {
                title,
                body: response.message,
                confirmLabel: _t("Entendido"),
            });
        }

        return this.dialog.add(ConfirmationDialog, {
            title,
            body: response.message,
            confirmLabel: _t("Revisar órdenes"),
            cancelLabel: _t("Cancelar"),
            confirm: () => {
                this.props.close();
                this.pos.navigate("TicketScreen");
            },
            cancel: () => {
                const cashId = this.props.default_cash_details.id;
                if (this.state.payments[cashId]) {
                    this.state.payments[cashId].counted = "0";
                }
            },
        });
    },
});
