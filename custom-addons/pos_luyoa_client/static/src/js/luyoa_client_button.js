/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { LuyoaClientPopup } from "@pos_luyoa_client/js/luyoa_client_popup";

/**
 * Flujo del botón "Luyoa" — se invoca desde la columna de control (desktop)
 * y la ActionPad (pantallas chicas). El componente llamante debe tener pos,
 * dialog y notification.
 */
export async function openLuyoaClientPopup() {
    if (this._luyoaClientBusy) {
        return;
    }
    const currentOrder = this.pos.getOrder();
    if (currentOrder && currentOrder.getHasRefundLines()) {
        // Mismo guard que pos.selectPartner(): cambiar el cliente de un
        // reembolso dejaría la operación contra un cliente equivocado.
        this.notification.add(
            _t("No se puede cambiar el cliente en una orden con devoluciones."),
            { type: "danger" }
        );
        return;
    }
    this._luyoaClientBusy = true;
    try {
        const payload = await makeAwaitable(this.dialog, LuyoaClientPopup, {});
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
            _t("Cliente %s asignado (Luyoa).", partners[0].name),
            { type: "success" }
        );
    } catch (error) {
        console.error(error);
        const msg = error?.message || error?.data?.message || String(error);
        this.notification.add(_t("Error inesperado: %s", msg), { type: "danger" });
    } finally {
        this._luyoaClientBusy = false;
    }
}

// ControlButtons y PaymentScreen ya traen dialog y notification.
patch(ControlButtons.prototype, { openLuyoaClientPopup });

patch(ActionpadWidget.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    },
    openLuyoaClientPopup,
});

// Pantalla de pago: el botón (solo logo) queda en PaymentScreenButtons,
// justo encima del teclado numérico.
patch(PaymentScreen.prototype, { openLuyoaClientPopup });
