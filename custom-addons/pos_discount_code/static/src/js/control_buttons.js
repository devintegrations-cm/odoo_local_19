/** @odoo-module **/

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DiscountCodePopup } from "./discount_code_popup";
import { CODE_PROGRAM_TYPES, checkLoyaltyCompatibility } from "./loyalty_adapter";

/**
 * Botón "Convenio To Plus" en el diálogo de acciones ("More…") del POS.
 * Reemplaza al "Enter Code" de pos_loyalty cuando está activo en la
 * configuración (ver control_buttons.xml).
 */
patch(ControlButtons.prototype, {
    showDiscountCodeButton() {
        return (
            this.pos.config.show_discount_code_button &&
            this.pos.models["loyalty.program"].some((p) =>
                CODE_PROGRAM_TYPES.includes(p.program_type)
            )
        );
    },
    async clickDiscountCode() {
        // Si una actualización de Odoo cambió pos_loyalty, se detiene aquí con
        // un aviso claro en vez de aplicar descuentos a medias.
        const problems = checkLoyaltyCompatibility(this.pos);
        if (problems.length) {
            console.error("[pos_discount_code] pos_loyalty incompatible:", problems);
            this.dialog.add(AlertDialog, {
                title: _t("Convenio To Plus no disponible"),
                body: _t(
                    "Este botón no es compatible con la versión actual de la lealtad de Odoo. " +
                        "Avise a soporte. Mientras tanto, un administrador puede desmarcar " +
                        "“Botón de descuento (Convenio To Plus)” en los Ajustes del punto de " +
                        "venta para volver al botón de códigos de Odoo.\n\nDetalle: %s",
                    problems.join("; ")
                ),
            });
            return;
        }
        await makeAwaitable(this.dialog, DiscountCodePopup, {});
    },
});
