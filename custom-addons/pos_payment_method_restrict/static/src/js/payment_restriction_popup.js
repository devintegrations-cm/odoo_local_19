/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Popup con campos configurables que aparece al seleccionar un método de pago
 * con restricción en el PaymentScreen.
 *
 * Odoo 19 eliminó `AbstractAwaitablePopup` y el servicio `popup`: un diálogo es
 * ahora un Component plano renderizado por el servicio `dialog`, que responde a
 * través de la prop `getPayload`. Las props deben declararse (OWL 2 rechaza las
 * desconocidas). El llamante usa `makeAwaitable(this.dialog, ...)`: resuelve con
 * el valor que entregue `getPayload`, o `undefined` al cerrar con Esc/backdrop.
 *
 * Props:
 *   title      {string}    Título del popup.
 *   fields     {Array}     [{key, name, type, required}, ...]
 *   getPayload {Function}  Canal de respuesta (lo provee makeAwaitable).
 *   close      {Function}  Cierra el diálogo (lo provee el servicio dialog).
 */
export class PaymentRestrictionPopup extends Component {
    static template = "pos_payment_method_restrict.PaymentRestrictionPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        fields: { type: Array, optional: true },
        getPayload: { type: Function, optional: true },
        close: Function,
    };
    static defaultProps = {
        title: "Información adicional",
        fields: [],
    };

    setup() {
        const values = {};
        const errors = {};
        for (const field of this.props.fields) {
            values[field.key] = "";
            errors[field.key] = false;
        }
        this.state = useState({ values, errors });
    }

    updateValue(key, value) {
        this.state.values[key] = value;
        if (this.state.errors[key] && value.trim()) {
            this.state.errors[key] = false;
        }
    }

    _buildResult() {
        const result = {};
        for (const field of this.props.fields) {
            const raw = this.state.values[field.key];
            result[field.key] = field.type === "integer" ? (parseInt(raw, 10) || 0) : raw;
        }
        return result;
    }

    confirm() {
        let hasErrors = false;
        for (const field of this.props.fields) {
            if (field.required && !this.state.values[field.key].toString().trim()) {
                this.state.errors[field.key] = true;
                hasErrors = true;
            }
        }
        if (hasErrors) {
            return;
        }
        this.props.getPayload?.(this._buildResult());
        this.props.close();
    }

    cancel() {
        this.props.getPayload?.(undefined);
        this.props.close();
    }
}