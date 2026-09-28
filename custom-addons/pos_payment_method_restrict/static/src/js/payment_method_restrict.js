/** @odoo-module */

/**
 * Restricción de métodos de pago por cliente en el PaymentScreen.
 *
 * Datos en `this.pos.config._payment_restrictions`:
 *   {
 *     [payment_method_id: string]: {
 *       restriction_db_id: number,
 *       partner_ids: number[],
 *       to_invoice: boolean,
 *       to_ei_invoice: boolean,
 *       create_delivery: boolean,
 *       fields: [{key, name, type, required}, ...]
 *     }
 *   }
 *
 * En Odoo 19 el diccionario viaja como campo EXTRA del raw de `pos.config`.
 * `_sanitizeRawData` (related_models/index.js) solo crea getters para claves
 * crudas que no son campos reales a partir de un único guion bajo (igual que
 * `_server_version`/`_base_url`), por eso la clave es `_payment_restrictions`.
 *
 * Lógica de visibilidad (requiere payment_restrict_enabled=True):
 *   - Sin cliente / cliente sin restricción → solo métodos sin restricción.
 *   - Cliente con restricción               → solo su(s) método(s) asignado(s).
 *
 * Popup de datos adicionales (independiente de payment_restrict_enabled):
 *   Si el método de pago tiene `fields` configurados en su restricción, al
 *   hacer clic aparece un popup pidiendo los datos requeridos.
 *   Los valores se guardan en `order.restriction_data` (JSON) y en
 *   `order.restriction_id` (FK a la restricción), ambos persistidos en BD.
 *
 * Detección de duplicados:
 *   Tras confirmar el popup se llama al backend para verificar si ya existe
 *   otra orden hoy con la misma restricción y algún valor coincidente.
 *   Si se detectan posibles duplicados, se muestra un aviso de confirmación
 *   (no bloquea, solo advierte).
 *
 * Persistencia (Odoo 19):
 *   `pos.order` no define `_load_pos_data_fields`, así que `restriction_data`
 *   (json) y `restriction_id` (many2one) viajan con el resto de campos. Pero
 *   `deepSerialization` descarta los campos whose modelo relacionado no está
 *   cargado en el store (el modelo `pos.payment.customer.restriction` no se
 *   carga), por lo que `restriction_id` se re-inyecta en `serializeForORM`.
 */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { makeAwaitable, ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PaymentRestrictionPopup } from "@pos_payment_method_restrict/js/payment_restriction_popup";

// ─── PosOrder: exportar restriction_data y restriction_id al backend ──────────

patch(PosOrder.prototype, {
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        // `deepSerialization` (related_models/serialization.js) saltea los
        // campos cuyo modelo relacionado no está en el store del POS, así que
        // `restriction_id` se perdería; se re-inyecta con su valor crudo.
        // `restriction_data` (json, sin relación) se conserva igualmente para
        // mantener el mismo payload que la versión Odoo 17 del módulo.
        data.restriction_data = this.restriction_data || null;
        data.restriction_id = this.restriction_id || false;
        return data;
    },
});

// ─── Helpers compartidos ──────────────────────────────────────────────────────

function getPartnerRestriction(pos, order) {
    if (!pos || !order) return null;
    const restrictions = pos.config._payment_restrictions;
    if (!restrictions || typeof restrictions !== "object") return null;
    const partner = order.getPartner();
    if (!partner) return null;
    for (const [, data] of Object.entries(restrictions)) {
        if (data.partner_ids && data.partner_ids.includes(partner.id)) {
            return data;
        }
    }
    return null;
}

/**
 * Aplica los flags to_invoice / to_ei_invoice de la restricción del cliente.
 *
 * - Cliente CON restricción: se escribe el valor configurado, sea true o false
 *   (igual que en Odoo 17). Un cliente con método especial (p. ej. hotel a
 *   crédito) configurado sin factura no se factura en el POS: sus pedidos quedan
 *   "Pagados" sin factura y se facturan después con "Crear factura agrupada".
 *   Esto prevalece sobre la factura obligatoria del POS.
 * - Cliente SIN restricción (o sin cliente): no se desmarca nada, para respetar
 *   la factura obligatoria y la electrónica de los clientes normales. Si el POS
 *   exige factura (`enable_obin` de pos_obligatory_invoice, opcional) se vuelve
 *   a marcar, por si antes se eligió un cliente con restricción sin factura.
 */
function applyRestrictionFlags(pos, order) {
    if (!order || order.finalized) return;
    const data = getPartnerRestriction(pos, order);
    if (!data) {
        if (pos.config.enable_obin && pos.config.canInvoice && !order.isToInvoice()) {
            order.setToInvoice(true);
        }
        return;
    }
    order.setToInvoice(Boolean(data.to_invoice));
    const toEiInvoice = Boolean(data.to_ei_invoice);
    if (typeof order.setToElectronicInvoice === "function") {
        order.setToElectronicInvoice(toEiInvoice);
    } else if (typeof order.set_to_electronic_invoice === "function") {
        order.set_to_electronic_invoice(toEiInvoice);
    }
}

// ─── PosStore: re-aplicar flags al cambiar el cliente ─────────────────────────
// En Odoo 19 el botón de cliente del PaymentScreen llama a `pos.selectPartner()`
// (servicio común a todas las pantallas, ya no es un método del PaymentScreen).

patch(PosStore.prototype, {
    async selectPartner(currentOrder = this.getOrder()) {
        const result = await super.selectPartner(currentOrder);
        if (currentOrder && this.config.payment_restrict_enabled) {
            applyRestrictionFlags(this, currentOrder);
        }
        return result;
    },
});

// ─── Parche en PaymentScreen ──────────────────────────────────────────────────

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);

        this.orm = useService("orm");

        const restrictions = this.pos.config._payment_restrictions;
        this._restrictions =
            restrictions && typeof restrictions === "object"
                ? restrictions
                : null;

        // El popup se activa para cualquier método con campos, sin importar
        // si payment_restrict_enabled está encendido (igual que en Odoo 17).
        if (this._restrictions && this.pos.config.payment_restrict_enabled) {
            // `payment_methods_from_config` se recalcula en cada lectura: la
            // plantilla de pago itera sobre él y OWL re-renderiza al cambiar
            // el cliente, manteniendo la visibilidad siempre al día.
            Object.defineProperty(this, "payment_methods_from_config", {
                get: () => this._computeAllowedMethods(this._restrictions),
                configurable: true,
            });

            // La factura obligatoria (pos_obligatory_invoice) marca "Facturar"
            // en el setup de esta pantalla. Si el cliente ya venía elegido, la
            // restricción se vuelve a aplicar una vez montada la pantalla, para
            // que su configuración prevalezca como en Odoo 17.
            onMounted(() => applyRestrictionFlags(this.pos, this.currentOrder));
        }
    },

    _computeAllowedMethods(restrictions) {
        const order = this.pos.getOrder();
        const partner = order ? order.getPartner() : null;
        const partnerId = partner ? partner.id : null;

        const restrictedMethodIds = new Set(Object.keys(restrictions).map(Number));
        const allMethods = this.pos.config.payment_method_ids;

        if (!partnerId) {
            return allMethods.filter((m) => !restrictedMethodIds.has(m.id));
        }

        const partnerMethodIds = new Set();
        for (const [methodId, data] of Object.entries(restrictions)) {
            if (data.partner_ids && data.partner_ids.includes(partnerId)) {
                partnerMethodIds.add(Number(methodId));
            }
        }

        if (partnerMethodIds.size > 0) {
            return allMethods.filter((m) => partnerMethodIds.has(m.id));
        }

        return allMethods.filter((m) => !restrictedMethodIds.has(m.id));
    },

    /**
     * Muestra el popup de datos adicionales si el método tiene campos
     * configurados, luego agrega la línea de pago normalmente.
     */
    async addNewPaymentLine(paymentMethod) {
        if (this._restrictions) {
            const data =
                this._restrictions[paymentMethod.id] ??
                this._restrictions[String(paymentMethod.id)];

            if (data && data.fields && data.fields.length > 0) {
                return this._addPaymentLineWithPopup(paymentMethod, data);
            }
        }

        return super.addNewPaymentLine(paymentMethod);
    },

    /**
     * Muestra el popup, verifica duplicados y agrega la línea de pago.
     *
     * @param {Object} paymentMethod  — método de pago seleccionado
     * @param {Object} restrictionData — entrada completa del dict de restricciones
     *   (incluye restriction_db_id, fields, partner_ids, etc.)
     */
    async _addPaymentLineWithPopup(paymentMethod, restrictionData) {
        applyRestrictionFlags(this.pos, this.pos.getOrder());

        const payload = await makeAwaitable(this.dialog, PaymentRestrictionPopup, {
            title: paymentMethod.name,
            fields: restrictionData.fields,
        });

        // Cancelado (Esc, backdrop o botón Cancelar) → se aborta la operación.
        if (payload === undefined) {
            return false;
        }

        // Verificar si ya existe una orden hoy con la misma restricción
        // y algún valor coincidente en el popup
        let duplicates = [];
        try {
            duplicates = await this.orm.call(
                "pos.order",
                "check_restriction_duplicate",
                [restrictionData.restriction_db_id, payload],
            );
        } catch (_e) {
            // Si la verificación falla, continuar sin bloquear la operación
        }

        if (duplicates && duplicates.length > 0) {
            const lines = duplicates.map((d) => `• ${d.name}  ${d.time}`).join("\n");
            const proceed = await ask(this.dialog, {
                title: _t("Posible registro duplicado"),
                body: `Ya existe(n) ${duplicates.length} orden(es) hoy con la misma restricción y datos coincidentes:\n${lines}\n\n¿Desea registrar igualmente?`,
                confirmLabel: _t("Registrar igualmente"),
                cancelLabel: _t("Cancelar"),
            });
            if (!proceed) {
                return false;
            }
        }

        const order = this.currentOrder;
        order.restriction_data = payload;
        order.restriction_id = restrictionData.restriction_db_id || false;
        return super.addNewPaymentLine(paymentMethod);
    },
});