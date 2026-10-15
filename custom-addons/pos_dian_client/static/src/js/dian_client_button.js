/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { DianClientPopup } from "@pos_dian_client/js/dian_client_popup";

/**
 * Flujo del botón "Factura electrónica" — se invoca desde la columna de
 * control (desktop), la ActionPad (pantallas chicas) y la pantalla de pago
 * (justo debajo de Cliente / Recibo-Factura).
 * El componente llamante debe tener pos, dialog, orm y notification.
 */
export async function openDianClientPopup() {
    if (this._dianClientBusy) {
        return;
    }
    const currentOrder = this.pos.getOrder();
    if (currentOrder && currentOrder.getHasRefundLines()) {
        // Mismo guard que pos.selectPartner(): cambiar el cliente de un
        // reembolso dejaría la factura contra un adquirente equivocado.
        this.notification.add(
            _t("No se puede cambiar el cliente en una orden con devoluciones."),
            { type: "danger" }
        );
        return;
    }
    this._dianClientBusy = true;
    try {
        const docTypes = await this.orm.call("res.partner", "pos_dian_client_doc_types", []);
        if (!docTypes.length) {
            this.notification.add(_t("No hay tipos de documento colombianos disponibles."), {
                type: "danger",
            });
            return;
        }
        const payload = await makeAwaitable(this.dialog, DianClientPopup, { docTypes });
        if (!payload || !payload.partner_id) {
            return;
        }
        const partners = await this.pos.data.read("res.partner", [payload.partner_id]);
        const order = this.pos.getOrder();
        if (!partners.length || !order) {
            this.notification.add(_t("No se pudo cargar el cliente en el POS."), { type: "danger" });
            return;
        }
        this.pos.setPartnerToCurrentOrder(partners[0]);
        order.setToInvoice(true);
        this.notification.add(
            _t("Cliente %s asignado para factura electrónica.", partners[0].name),
            { type: "success" }
        );
    } catch (error) {
        console.error(error);
        const msg = error?.message || error?.data?.message || String(error);
        this.notification.add(_t("Error inesperado: %s", msg), { type: "danger" });
    } finally {
        this._dianClientBusy = false;
    }
}

/**
 * "Ocultar botón de cliente" solo aplica si el botón "Factura electrónica"
 * está activo: con los dos ajustes apagados la caja quedaría sin forma de
 * asignar cliente.
 */
export function dianHidesPartner(config) {
    return Boolean(config.show_dian_client_button && config.hide_partner_button);
}

patch(ControlButtons.prototype, {
    get dianHidesPartner() {
        return dianHidesPartner(this.pos.config);
    },
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },
    openDianClientPopup,
});

patch(ActionpadWidget.prototype, {
    get dianHidesPartner() {
        return dianHidesPartner(this.pos.config);
    },
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");
    },
    openDianClientPopup,
});

// Pantalla de pago: el botón "Factura electrónica" queda justo debajo de
// Cliente / Recibo-Factura (la plantilla PaymentScreenButtons se renderiza
// con t-call, así que el contexto es este componente).
patch(PaymentScreen.prototype, {
    get dianHidesPartner() {
        return dianHidesPartner(this.pos.config);
    },
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },
    openDianClientPopup,
});
