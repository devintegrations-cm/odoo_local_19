/** @odoo-module */
/**
 * Datos del popup de restricción debajo de la línea de pago.
 *
 * Cuando el cajero confirma el popup (p. ej. "Habitación: 101"), el dato se
 * muestra debajo de la línea del método en la pantalla de pago, para poder
 * revisarlo antes de validar (paridad con la versión Odoo 17 del módulo).
 *
 * En Odoo 17 el dato se guardaba también en la línea de pago; en esta versión
 * vive solo en el pedido (`order.restriction_data` + `order.restriction_id`,
 * ver payment_method_restrict.js). Por eso se muestra bajo la línea cuyo
 * método corresponde a la restricción guardada en el pedido, con las
 * etiquetas y el orden configurados en la restricción.
 */

import { patch } from "@web/core/utils/patch";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";

const isFilled = (value) =>
    value !== undefined && value !== null && String(value).trim() !== "";

patch(PaymentScreenPaymentLines.prototype, {
    /**
     * @param {Object} line — línea de pago (pos.payment)
     * @returns {Array<{key: string, label: string, value: *}>}
     */
    restrictionDataDisplay(line) {
        const order = line?.pos_order_id;
        const data = order?.restriction_data;
        const restrictions = this.pos.config._payment_restrictions;
        const methodId = line?.payment_method_id?.id;
        if (!data || typeof data !== "object" || !restrictions || !methodId) {
            return [];
        }

        const entry = restrictions[methodId] ?? restrictions[String(methodId)];
        // `restriction_id` puede llegar como id crudo o como registro.
        const orderRestrictionId = order.restriction_id?.id ?? order.restriction_id;
        if (!entry || !orderRestrictionId || orderRestrictionId !== entry.restriction_db_id) {
            return [];
        }

        const fields = entry.fields || [];
        if (fields.length) {
            return fields
                .filter((field) => isFilled(data[field.key]))
                .map((field) => ({ key: field.key, label: field.name, value: data[field.key] }));
        }
        return Object.entries(data)
            .filter(([, value]) => isFilled(value))
            .map(([key, value]) => ({ key, label: key, value }));
    },
});
