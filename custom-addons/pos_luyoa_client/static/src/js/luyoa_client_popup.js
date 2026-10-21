/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { BarcodeDialog } from "@web/core/barcode/barcode_dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

/**
 * Abre la cámara (BarcodeDialog del core, con ZXing) y resuelve con el
 * código escaneado, o con null si el cajero cierra sin escanear.
 *
 * Tres particularidades del core obligan a este helper en vez del
 * `scanBarcode` de `barcode_dialog.js`:
 *
 * - Su promise queda colgada si el diálogo se cierra sin resultado (solo
 *   resuelve en onResult/onError), lo que dejaría el botón ocupado para
 *   siempre: el `onClose` del servicio de diálogos cubre el cancelar.
 * - `BarcodeDialog.onResult` llama a `props.close()` ANTES de
 *   `props.onResult(result)`, y `close` del servicio de diálogos es
 *   síncrono: el `onClose` se dispara con el código aún NO capturado.
 * - Una promise solo se resuelve una vez: si `onClose` resolviera null en
 *   ese momento, el código escaneado se pierde (el popup vuelve a la fase
 *   de escaneo tras leer el QR). Por eso `onClose` DIFIERE la resolución
 *   un macrotask (`setTimeout 0`): cuando corre, `onResult` ya capturó.
 *
 * Orden real al escanear: close() → onClose (agenda resolve) → onResult
 * (guarda el código) → setTimeout (resuelve con el código).
 */
function scanWithCamera(env) {
    return new Promise((resolve) => {
        let result = null;
        env.services.dialog.add(
            BarcodeDialog,
            {
                facingMode: "environment",
                onResult: (code) => {
                    result = code;
                },
                onError: () => {
                    // El BarcodeDialog ya muestra el motivo dentro del
                    // diálogo (permisos, sin cámara); al cerrarlo el
                    // onClose resuelve null y el popup se queda como
                    // estaba.
                },
            },
            {
                onClose: () => {
                    setTimeout(() => resolve(result), 0);
                },
            }
        );
    });
}

/**
 * Popup "Luyoa": fase 1 solo escanea el QR de la tarjeta de lealtad con la
 * cámara del dispositivo; fase 2 previsualiza los datos de Luyoa y el
 * contacto de Odoo, y aplica la acción (assign | create). No envía
 * transacciones a Luyoa.
 */
export class LuyoaClientPopup extends Component {
    static template = "pos_luyoa_client.LuyoaClientPopup";
    static components = { Dialog };
    static props = {
        getPayload: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            phase: "scan",
            code: "",
            busy: false,
            scanning: false,
            res: null,
            confirmError: "",
        });
    }

    get res() {
        return this.state.res || {};
    }

    get status() {
        return this.res.status || "";
    }

    get luyoa() {
        return this.res.luyoa || {};
    }

    get luyoaName() {
        return [this.luyoa.first_name, this.luyoa.last_name].filter(Boolean).join(" ");
    }

    get matchByLabel() {
        switch (this.res.match_by) {
            case "uid":
                return _t("tarjeta escaneada");
            case "email":
                return _t("correo");
            case "name_phone":
                return _t("nombre y teléfono");
            default:
                return "";
        }
    }

    get bannerClass() {
        switch (this.status) {
            case "found":
            case "created":
                return "alert-success";
            case "not_in_odoo":
            case "ambiguous":
            case "archived":
            case "uid_conflict":
                return "alert-warning";
            default:
                return "alert-danger";
        }
    }

    mainMessage() {
        const res = this.res;
        switch (this.status) {
            case "found":
                return _t("Cliente válido en Luyoa: %s. Coincide en Odoo por %s.",
                          this.luyoaName || this.luyoa.uid, this.matchByLabel);
            case "not_in_odoo":
                return _t("El cliente %s existe en Luyoa pero no en Odoo. Se creará con sus datos básicos.",
                          this.luyoaName || this.luyoa.uid);
            case "ambiguous":
                return res.detail || _t("Hay más de un contacto en Odoo que coincide.");
            case "archived":
            case "uid_conflict":
            case "invalid_uid":
            case "customer_not_found":
            case "unauthorized":
            case "forbidden":
            case "config_error":
            case "connection_error":
            case "unexpected_response":
            case "permission_error":
            case "invalid":
                return res.detail || _t("No se pudo completar la consulta.");
            default:
                return this.state.confirmError || "";
        }
    }

    set(field, value) {
        this.state[field] = value;
    }

    backToScan() {
        this.state.phase = "scan";
        this.state.res = null;
        this.state.confirmError = "";
    }

    async scan() {
        if (this.state.scanning || this.state.busy) {
            return;
        }
        this.state.scanning = true;
        try {
            const code = await scanWithCamera(this.env);
            if (code) {
                this.state.code = code;
                await this.lookup();
            }
        } finally {
            this.state.scanning = false;
        }
    }

    async lookup() {
        if (this.state.busy) {
            return;
        }
        const code = (this.state.code || "").trim();
        if (!code) {
            this.notification.add(_t("Escanee el QR de la tarjeta digital del cliente."), {
                type: "warning",
            });
            return;
        }
        this.state.busy = true;
        let res = {};
        try {
            res = await this.orm.call("res.partner", "pos_luyoa_lookup", [code, this.pos.config.id]);
        } catch (error) {
            res = { status: "connection_error", detail: _t("No hay conexión con el servidor de Odoo. Revise el internet de la tienda y reintente.") };
        }
        this.state.busy = false;
        this.state.confirmError = "";
        this.state.res = res;
        this.state.phase = "result";
    }

    async confirm(action) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        let out = {};
        try {
            out = await this.orm.call("res.partner", "pos_luyoa_assign", [
                (this.state.code || "").trim(),
                this.pos.config.id,
                action,
            ]);
        } catch (error) {
            out = { status: "connection_error", detail: _t("No hay conexión con el servidor de Odoo. Revise el internet de la tienda y reintente.") };
        }
        this.state.busy = false;
        if ((out.status === "assigned" || out.status === "created") && out.partner_id) {
            this.props.getPayload?.({ partner_id: out.partner_id });
            this.props.close();
            return;
        }
        // El servidor rechazó algo en la fase 2: mantener la previsualización
        // y mostrar el motivo.
        this.state.confirmError = out.detail || out.status || _t("No se pudo asignar el cliente.");
    }

    primaryButton() {
        switch (this.status) {
            case "found":
                return { label: _t("Asignar cliente"), cls: "btn-success", action: () => this.confirm("assign") };
            case "not_in_odoo":
                return { label: _t("Crear y asignar"), cls: "btn-success", action: () => this.confirm("create") };
            case "connection_error":
            case "unexpected_response":
                return { label: _t("Reintentar"), cls: "btn-primary", action: () => this.lookup() };
            case "ambiguous":
            case "archived":
            case "uid_conflict":
            case "invalid_uid":
            case "customer_not_found":
            case "unauthorized":
            case "forbidden":
            case "config_error":
            case "permission_error":
            case "invalid":
                return { label: _t("Escanear de nuevo"), cls: "btn-secondary", action: () => this.backToScan() };
            default:
                return null;
        }
    }

    cancel() {
        this.props.getPayload?.(undefined);
        this.props.close();
    }
}
