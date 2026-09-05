/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Confirmation dialog shown before registering a Cash In/Out movement.
 *
 * Odoo 19 removed `AbstractAwaitablePopup` and the `popup` service: dialogs are
 * plain `Component`s rendered through the `dialog` service and answered through
 * the `getPayload` prop (same shape as core's NumberPopup/MoneyDetailsPopup).
 * Props must be declared: OWL 2 rejects unknown ones.
 */
export class CashMoveConfirmPopup extends Component {
    static template = "pos_cash_in_out_message.CashMoveConfirmPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        type: { type: String, optional: true },
        formattedAmount: { type: String, optional: true },
        isLastMovement: { type: Boolean, optional: true },
        configMessage: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        cancelLabel: { type: String, optional: true },
        getPayload: { type: Function, optional: true },
        close: Function,
    };
    static defaultProps = {
        title: _t("Confirmar movimiento"),
        type: "out",
        formattedAmount: "",
        isLastMovement: false,
        configMessage: "",
        confirmLabel: _t("Sí, registrar"),
        cancelLabel: _t("Cancelar"),
    };

    get movementTypeLabel() {
        return this.props.type === "in" ? _t("entrada de efectivo") : _t("salida de efectivo");
    }

    get movementTypeClass() {
        return this.props.type === "in" ? "cash-in" : "cash-out";
    }

    get iconClass() {
        return this.props.type === "in" ? "fa fa-arrow-down" : "fa fa-arrow-up";
    }

    confirm() {
        this.props.getPayload({ confirmed: true });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
