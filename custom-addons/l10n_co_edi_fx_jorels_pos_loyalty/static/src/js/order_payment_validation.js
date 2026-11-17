/** @odoo-module */

import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Odoo 19: la validación de la orden salió de PaymentScreen.validateOrder a
// OrderPaymentValidation (la usan la pantalla de pago y la validación rápida).
// pos_loyalty parchea este mismo método; como este módulo depende de pos_loyalty,
// este parche queda por fuera y corre antes, igual que en 17.

function isEmptyValue(value) {
    if (!value) {
        return true;
    }
    if (typeof value === "string" && value.trim() === "") {
        return true;
    }
    if (Array.isArray(value) && value.length === 0) {
        return true;
    }
    return false;
}

patch(OrderPaymentValidation.prototype, {
    // Campos obligatorios del cliente para la factura electrónica.
    // En 19 los many2one llegan como registro (si el modelo está cargado en el POS)
    // o como id entero (si no lo está); vacío es undefined/false en ambos casos.
    validateFields(customer) {
        const fieldMapping = {
            type_liability_id: "Responsabilidad",
            type_regime_id: "Regimen",
            vat: "Número de documento",
            name: "Nombre",
            municipality_id: "Municipalidad",
            l10n_latam_identification_type_id: "Tipo documento",
            email: "Correo Electrónico",
            country_id: "País",
        };
        return Object.keys(fieldMapping)
            .filter((field) => isEmptyValue(customer[field]))
            .map((field) => fieldMapping[field]);
    },

    async checkCompleteCustomerInfo() {
        const customer = this.order.getPartner();
        if (!customer) {
            // Igual que en 17: sin cliente no se valida.
            console.error("El cliente no está definido.");
            return false;
        }

        const missingFields = this.validateFields(customer);
        if (missingFields.length > 0) {
            console.error("CAMPOS FALTANTES", missingFields);
            await makeAwaitable(this.pos.dialog, SelectionPopup, {
                title: _t("Obligatorio: Agregar estos datos del cliente"),
                list: missingFields.map((field) => ({
                    id: field,
                    label: field,
                    isSelected: false,
                    item: field,
                })),
            });
            return false;
        }
        return true;
    },

    // Enlaza cada línea de recompensa con el producto que la origina.
    // `_reward_product_id` (pos_loyalty 19, local) es el product.product premiado.
    // Se guarda el id de la VARIANTE: el backend lo compara con `product_id.id`
    // (_compute_reward_related_order_line_id). En 17 se guardaba el id de plantilla,
    // que solo coincidía por casualidad.
    updateRelatedRewards() {
        const lines = this.order.getOrderlines();
        for (const rewardLine of lines) {
            if (!rewardLine?.is_reward_line || !rewardLine._reward_product_id) {
                continue;
            }
            const rewardProductId = rewardLine._reward_product_id.id;
            const correspondingLine = lines.find(
                (line) => !line.is_reward_line && line.getProduct()?.id === rewardProductId
            );
            if (correspondingLine) {
                rewardLine.reward_related_product_line_id = correspondingLine.getProduct().id;
            }
        }
    },

    async showProductsPopup(title, lines) {
        await makeAwaitable(this.pos.dialog, SelectionPopup, {
            title,
            list: lines.map((line) => {
                const product = line.getProduct();
                return {
                    id: line.uuid,
                    label: product?.display_name || line.getFullProductName(),
                    isSelected: false,
                    item: product?.id,
                };
            }),
        });
    },

    async checkZeroQuantityLines() {
        const zeroQtyLines = this.order.getOrderlines().filter((line) => line.getQuantity() === 0);
        if (zeroQtyLines.length > 0) {
            await this.showProductsPopup(_t("Productos con Cantidad en Cero"), zeroQtyLines);
            return false;
        }
        return true;
    },

    async checkZeroPriceLines() {
        return true; // Desactivado temporalmente (igual que en 17)
    },

    async validateOrder(isForceValidate) {
        this.updateRelatedRewards();
        const isCompletedCustomerInfo = await this.checkCompleteCustomerInfo();
        const isZeroQuantityLines = await this.checkZeroQuantityLines();
        const isZeroPriceLines = await this.checkZeroPriceLines();

        if (!isCompletedCustomerInfo || !isZeroQuantityLines || !isZeroPriceLines) {
            return false;
        }
        return super.validateOrder(...arguments);
    },
});
