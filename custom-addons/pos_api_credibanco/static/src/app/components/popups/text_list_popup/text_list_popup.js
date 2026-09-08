/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Read-only list of text lines with an optional cancel button.
 *
 * Awaited through makeAwaitable(): it answers `{ confirmed: true }` when
 * accepted, `{ confirmed: false }` when cancelled, and nothing when dismissed
 * with the escape key or the backdrop.
 *
 * Odoo 19 removed `AbstractAwaitablePopup` and the `popup` service: a dialog is
 * a plain Component rendered by the `dialog` service and answered through the
 * `getPayload` prop. Props must be declared, OWL 2 rejects the unknown ones.
 */
export class TextListPopup extends Component {
    static template = "pos_api_credibanco.TextListPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        body: { type: String, optional: true },
        list: { type: Array, optional: true },
        confirmText: { type: String, optional: true },
        // false hides the button, which is how the callers ask for a
        // single-action dialog.
        cancelText: { type: [String, Boolean], optional: true },
        getPayload: { type: Function, optional: true },
        close: Function,
    };
    static defaultProps = {
        title: "",
        body: "",
        list: [],
        confirmText: _t("Aceptar"),
        cancelText: false,
    };

    confirm() {
        this.props.getPayload?.({ confirmed: true });
        this.props.close();
    }

    cancel() {
        this.props.getPayload?.({ confirmed: false });
        this.props.close();
    }
}
