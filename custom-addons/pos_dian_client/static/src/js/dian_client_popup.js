/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Popup "Factura electrónica": fase 1 captura y consulta (pos_dian_lookup,
 * no escribe), fase 2 previsualiza los datos de la DIAN y aplica la acción
 * (pos_dian_confirm: assign | update | create).
 */
export class DianClientPopup extends Component {
    static template = "pos_dian_client.DianClientPopup";
    static components = { Dialog };
    static props = {
        docTypes: Array,
        getPayload: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        const cc = this.props.docTypes.find((t) => t.code === "national_citizen_id");
        this.state = useState({
            phase: "form",
            docCode: (cc || this.props.docTypes[0] || {}).code || "",
            number: "",
            dv: "",
            email: "",
            busy: false,
            res: null,
            confirmError: "",
            replace: false,
        });
    }

    get selectedType() {
        return this.props.docTypes.find((t) => t.code === this.state.docCode) || {};
    }

    get isNit() {
        return Boolean(this.selectedType.is_nit);
    }

    get isCompany() {
        // NIT / NIT de otro país => contribuyente con empresa a su nombre.
        return this.isNit;
    }

    get res() {
        return this.state.res || {};
    }

    get status() {
        return this.res.status || "";
    }

    get hasFillable() {
        return this.res.fillable && Object.keys(this.res.fillable).length > 0;
    }

    get hasDiff() {
        const diff = this.res.diff || {};
        return diff.name || diff.email;
    }

    get bannerClass() {
        switch (this.status) {
            case "found":
            case "create_ok":
                return "alert-success";
            case "needs_email":
            case "archived":
            case "ambiguous":
            case "incomplete":
            case "type_mismatch":
            case "unexpected_response":
            case "connection_error":
                return "alert-warning";
            default:
                return "alert-danger";
        }
    }

    mainMessage() {
        const res = this.res;
        const doc = `${this.selectedType.name || ""} ${res.docNumber || this.state.number}`.trim();
        switch (this.status) {
            case "not_registered":
                return _t(
                    `El cliente ${doc} no está habilitado como adquirente ante la DIAN. ` +
                        "Pídale registrar su facturación electrónica antes de asignarle una factura."
                );
            case "found":
                return _t("Cliente válido ante la DIAN: %s.", res.partner?.name || doc);
            case "create_ok":
                return _t("El cliente existe ante la DIAN y no en Odoo. Se creará con sus datos.");
            case "needs_email":
                return _t(
                    "La DIAN confirmó a %s pero no tiene correo registrado. " +
                        "Escriba el correo al que se enviará la factura electrónica.",
                    res.dian?.name || doc
                );
            case "archived":
            case "ambiguous":
            case "incomplete":
            case "type_mismatch":
            case "config_error":
            case "connection_error":
            case "unexpected_response":
            case "invalid":
            case "permission_error":
                return res.detail || _t("No se pudo completar la validación.");
            default:
                return this.state.confirmError || "";
        }
    }

    set(field, value) {
        this.state[field] = value;
    }

    backToForm() {
        this.state.phase = "form";
        this.state.res = null;
        this.state.confirmError = "";
        this.state.replace = false;
    }

    async validate() {
        if (this.state.busy) {
            return;
        }
        if (!this.state.number.trim()) {
            this.state.phase = "result";
            this.state.res = { status: "invalid", detail: _t("Digite el número de documento.") };
            return;
        }
        this.state.busy = true;
        let res = {};
        try {
            res = await this.orm.call("res.partner", "pos_dian_lookup", [
                this.state.docCode,
                this.state.number.trim(),
                this.isNit ? this.state.dv.trim() : false,
            ]);
        } catch (error) {
            res = { status: "connection_error", detail: _t("Error de comunicación con el servidor.") };
        }
        res.docNumber = this.state.number.trim();
        this.state.busy = false;
        this.state.confirmError = "";
        this.state.res = res;
        this.state.phase = "result";
    }

    async confirm(action) {
        const res = this.res;
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        let out = {};
        try {
            out = await this.orm.call("res.partner", "pos_dian_confirm", [
                this.state.docCode,
                this.state.number.trim(),
                this.isNit ? this.state.dv.trim() : false,
                action,
                res.dian?.name || false,
                res.dian?.email || false,
                this.state.email.trim() || false,
                action === "update" ? this.state.replace : false,
            ]);
        } catch (error) {
            out = { status: "connection_error", detail: _t("Error de comunicación con el servidor.") };
        }
        this.state.busy = false;
        if ((out.status === "assigned" || out.status === "created" || out.status === "updated") && out.partner_id) {
            this.props.getPayload?.({ partner_id: out.partner_id });
            this.props.close();
            return;
        }
        // El servidor rechazó algo en la fase 2: mantener la previsualización
        // y mostrar el motivo sin perder lo digitado.
        this.state.confirmError = out.detail || out.status || _t("No se pudo asignar el cliente.");
    }

    primaryButton() {
        if (this.state.phase === "form") {
            return { label: _t("Validar en DIAN"), cls: "btn-primary", action: () => this.validate() };
        }
        switch (this.status) {
            case "found":
                return {
                    label: this.hasFillable || this.hasDiff ? _t("Asignar y actualizar") : _t("Asignar cliente"),
                    cls: "btn-success",
                    action: () => this.confirm(this.hasFillable || this.hasDiff ? "update" : "assign"),
                };
            case "create_ok":
            case "needs_email":
                return { label: _t("Crear y asignar"), cls: "btn-success", action: () => this.confirm("create") };
            case "not_registered":
            case "incomplete":
            case "archived":
            case "ambiguous":
            case "type_mismatch":
                return { label: _t("Entendido"), cls: "btn-secondary", action: () => this.cancel() };
            case "connection_error":
            case "unexpected_response":
                return { label: _t("Reintentar"), cls: "btn-primary", action: () => this.validate() };
            case "config_error":
            case "permission_error":
                return { label: _t("Cerrar"), cls: "btn-secondary", action: () => this.cancel() };
            default:
                return { label: _t("Modificar datos"), cls: "btn-secondary", action: () => this.backToForm() };
        }
    }

    cancel() {
        this.props.getPayload?.(undefined);
        this.props.close();
    }
}
