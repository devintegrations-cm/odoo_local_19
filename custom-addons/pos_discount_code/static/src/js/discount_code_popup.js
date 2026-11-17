/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import {
    activateCode,
    checkCouponCode,
    deactivateCode,
    findCodeRule,
    getActivatedProgram,
    getProgramDiscountAmount,
    programHasRewardLine,
} from "./loyalty_adapter";

const { DateTime } = luxon;

// Tipo seleccionado por defecto (si existe en la lista que envía el servidor).
const DEFAULT_DOC_TYPE = "cc";

/**
 * Popup del Convenio To Plus: solo interfaz y reglas del canje.
 * Todo lo que toca la lealtad de Odoo pasa por `loyalty_adapter.js`.
 *
 * Se abre con `makeAwaitable(dialog, DiscountCodePopup, {})`; al aplicar el
 * código entrega `{ code }` por `getPayload` y se cierra.
 */
export class DiscountCodePopup extends Component {
    static template = "pos_discount_code.DiscountCodePopup";
    static components = { Dialog };
    static props = {
        getPayload: Function,
        close: Function,
    };

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        // La lista viene del servidor (pos.config._load_pos_data_read); no se repite aquí.
        this.docTypes = this.pos.config._discount_doc_types || [];
        const defaultDocType = this.docTypes.some((d) => d.value === DEFAULT_DOC_TYPE)
            ? DEFAULT_DOC_TYPE
            : this.docTypes[0]?.value || false;
        this.state = useState({
            phase: "form",
            docType: defaultDocType,
            docNumber: "",
            code: "",
            error: "",
            preview: null,
            replacing: "",
        });
        this.busy = false;
    }

    get title() {
        return this.state.phase === "form" ? _t("Convenio To Plus") : _t("Aplicar descuento");
    }

    get docTypeLabel() {
        const docType = this.docTypes.find((d) => d.value === this.state.docType);
        return docType ? docType.label : this.state.docType;
    }

    get docTypeIsNumeric() {
        return Boolean(this.docTypes.find((d) => d.value === this.state.docType)?.numeric);
    }

    async confirm() {
        if (this.busy) {
            return;
        }
        this.busy = true;
        try {
            if (this.state.phase === "form") {
                await this.validateCode();
            } else {
                await this.applyCode();
            }
        } finally {
            this.busy = false;
        }
    }

    cancel() {
        this.props.close();
    }

    backToForm() {
        this.state.error = "";
        this.state.replacing = "";
        this.state.phase = "form";
    }

    async validateCode() {
        const code = this.state.code.trim();
        const docNumber = this.state.docNumber.trim();
        this.state.error = "";
        this.state.replacing = "";
        if (!docNumber) {
            this.state.error = _t("Ingrese el número de documento.");
            return;
        }
        if (this.docTypeIsNumeric && !/^\d+$/.test(docNumber)) {
            this.state.error = _t(
                "El número de documento solo debe tener dígitos, sin puntos, espacios ni guiones."
            );
            return;
        }
        if (!code) {
            this.state.error = _t("Ingrese el código de descuento.");
            return;
        }
        const order = this.pos.getOrder();
        if (order.getHasRefundLines()) {
            this.state.error = _t(
                "No se pueden aplicar códigos de descuento en una orden con reembolsos."
            );
            return;
        }
        // Un código cuenta como aplicado solo si su descuento sigue en la orden.
        // Si el cajero quitó la línea del descuento, se permite volver a
        // aplicarlo para que el cliente no pierda el bono en esta misma orden.
        const activated = getActivatedProgram(order, code);
        if (activated && programHasRewardLine(order, activated.program.id)) {
            this.state.error = _t("Este código ya fue aplicado en la orden.");
            return;
        }
        if (order.discount_code && order.discount_code !== code) {
            this.state.replacing = order.discount_code;
        }
        const rule = findCodeRule(order, code);
        if (rule) {
            const error = this._checkRuleProgram(order, rule.program_id);
            if (error) {
                this.state.error = error;
                return;
            }
            this.state.preview = this._buildPreview(rule.program_id);
        } else if (activated) {
            // Cupón ya validado en esta orden (su descuento fue quitado).
            this.state.preview = this._buildPreview(activated.program);
        } else {
            // Cupón / tarjeta de regalo: se valida contra el servidor desde el
            // primer "Validar" (solo consulta, no gasta el cupón).
            const check = await checkCouponCode(this.pos, code);
            if (check.error) {
                this.state.error = check.error;
                return;
            }
            this.state.preview = this._buildPreview(check.program, check.points);
        }
        this.state.phase = "preview";
    }

    /** Vigencia y lista de precios de una promoción (datos del programa). */
    _checkRuleProgram(order, program) {
        const now = DateTime.now();
        if (program.date_from && now < program.date_from.startOf("day")) {
            return _t("Este código aún no está vigente.");
        }
        if (program.date_to && now > program.date_to.endOf("day")) {
            return _t("Este código está vencido.");
        }
        if (
            program.pricelist_ids.length > 0 &&
            (!order.pricelist_id ||
                !program.pricelist_ids.some((pricelist) => pricelist.id === order.pricelist_id.id))
        ) {
            return _t("Este código requiere una lista de precios específica.");
        }
        return "";
    }

    _buildPreview(program, points = null) {
        const discountReward = program.reward_ids.find((r) => r.reward_type === "discount");
        let valorLabel = _t("Según carrito");
        if (program.program_type === "gift_card" && points !== null) {
            valorLabel = _t("Saldo: %s", this.env.utils.formatCurrency(points));
        } else if (discountReward) {
            valorLabel =
                discountReward.discount_mode === "percent"
                    ? `${discountReward.discount}%`
                    : this.env.utils.formatCurrency(discountReward.discount);
        }
        return {
            name: program.name,
            valorLabel,
            vigenciaLabel: program.date_to
                ? program.date_to.toFormat("dd/MM/yyyy")
                : _t("Sin fecha de vencimiento"),
            estadoLabel: _t("Vigente"),
        };
    }

    async applyCode() {
        this.state.error = "";
        const order = this.pos.getOrder();
        const code = this.state.code.trim();
        if (order.discount_code && order.discount_code !== code) {
            await deactivateCode(this.pos, order.discount_code, order.discount_program_id?.id);
            order.clearDiscountCode();
            this.state.replacing = "";
        }
        const result = await activateCode(this.pos, code);
        if (result.error) {
            this.state.error = result.error;
            return;
        }
        const program = result.program;
        order.setDiscountCode({
            program,
            code,
            docType: this.state.docType,
            docNumber: this.state.docNumber.trim(),
        });
        const amount = getProgramDiscountAmount(order, program.id);
        if (amount > 0) {
            this.notification.add(
                _t("Descuento aplicado: %s", this.env.utils.formatCurrency(amount)),
                { type: "success" }
            );
        } else {
            // Activado pero sin descuento todavía (p. ej. monto mínimo): solo
            // se registra en el servidor si al cobrar hay línea de descuento.
            this.notification.add(
                _t(
                    "Código activado: el descuento se aplicará cuando la orden cumpla las condiciones del bono."
                ),
                { type: "info" }
            );
        }
        this.props.getPayload({ code });
        this.props.close();
    }
}
