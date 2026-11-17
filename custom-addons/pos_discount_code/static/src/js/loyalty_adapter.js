/** @odoo-module **/

/**
 * Adaptador de pos_loyalty (Odoo 19).
 *
 * Único archivo del módulo que accede al estado interno de pos_loyalty
 * (`order.uiState.codeActivatedProgramRules`, `disabledRewards`,
 * `couponPointChanges`, `order._code_activated_coupon_ids`) y a sus métodos
 * internos (`order._applyReward`, `pos.activateCode`, `pos.updateRewards`...).
 * El popup y el resto del módulo solo llaman las funciones exportadas aquí.
 *
 * Ese estado no es una interfaz pública y puede cambiar entre versiones de
 * Odoo. `checkLoyaltyCompatibility` verifica su estructura antes de abrir el
 * popup y detiene el flujo si no coincide.
 */

import { _t } from "@web/core/l10n/translation";

/** Tipos de programa que se canjean con este botón (los mismos del "Enter Code" nativo). */
export const CODE_PROGRAM_TYPES = [
    "coupons",
    "promotion",
    "gift_card",
    "promo_code",
    "next_order_coupons",
];

// ---------------------------------------------------------------- contrato

/** Métodos del PosStore (pos_loyalty) que usa este adaptador. */
const STORE_METHODS = ["getOrder", "activateCode", "orderUpdateLoyaltyPrograms", "updateRewards"];

/** Métodos de la orden (pos_loyalty) que usa este adaptador. */
const ORDER_METHODS = ["_applyReward", "getClaimableRewards", "_get_reward_lines"];

/** Estado de lealtad en `order.uiState` y la forma que debe tener. */
const ORDER_UI_STATE = {
    codeActivatedProgramRules: (v) => Array.isArray(v),
    couponPointChanges: (v) => Boolean(v) && typeof v === "object",
    disabledRewards: (v) => v instanceof Set,
};

/** Modelos de lealtad cargados en el POS. */
const LOYALTY_MODELS = ["loyalty.program", "loyalty.rule", "loyalty.reward", "loyalty.card"];

/**
 * Revisa que pos_loyalty tenga la forma que este adaptador espera.
 * @returns {string[]} lista de problemas; vacía si todo es compatible.
 */
export function checkLoyaltyCompatibility(pos) {
    const order = pos.getOrder?.();
    if (!order) {
        return [_t("No hay una orden abierta.")];
    }
    const problems = [];
    for (const method of STORE_METHODS) {
        if (typeof pos[method] !== "function") {
            problems.push(`pos.${method}() no existe`);
        }
    }
    for (const method of ORDER_METHODS) {
        if (typeof order[method] !== "function") {
            problems.push(`order.${method}() no existe`);
        }
    }
    for (const [key, isValid] of Object.entries(ORDER_UI_STATE)) {
        if (!isValid(order.uiState?.[key])) {
            problems.push(`order.uiState.${key} no tiene la forma esperada`);
        }
    }
    if (typeof order._code_activated_coupon_ids?.find !== "function") {
        problems.push("order._code_activated_coupon_ids no tiene la forma esperada");
    }
    for (const model of LOYALTY_MODELS) {
        if (!pos.models?.[model]) {
            problems.push(`el modelo ${model} no está cargado`);
        }
    }
    return problems;
}

// ------------------------------------------------------------- consultas

/** Regla con código del programa (promociones). Igual criterio que pos.activateCode. */
export function findCodeRule(order, code) {
    return order.models["loyalty.rule"].find(
        (rule) => rule.mode === "with_code" && (rule.promo_barcode === code || rule.code === code)
    );
}

/**
 * Programa del código si ya está activado en la orden (por regla o por
 * cupón/tarjeta), o null.
 * @returns {{program: object, couponId: number|false}|null}
 */
export function getActivatedProgram(order, code) {
    const rule = findCodeRule(order, code);
    if (rule && order.uiState.codeActivatedProgramRules.includes(rule.id)) {
        return { program: rule.program_id, couponId: false };
    }
    const coupon = order._code_activated_coupon_ids.find((c) => c.code === code);
    if (coupon?.program_id) {
        return { program: coupon.program_id, couponId: coupon.id };
    }
    return null;
}

/** Líneas de recompensa (descuento) de un programa en la orden. */
export function getProgramRewardLines(order, programId) {
    return order._get_reward_lines().filter((line) => line.reward_id?.program_id?.id === programId);
}

export function programHasRewardLine(order, programId) {
    return getProgramRewardLines(order, programId).length > 0;
}

/** Valor (positivo, con impuestos) que descuenta un programa en la orden. */
export function getProgramDiscountAmount(order, programId) {
    if (!programId) {
        return 0;
    }
    const total = getProgramRewardLines(order, programId).reduce(
        (sum, line) => sum + line.priceIncl,
        0
    );
    return Math.abs(total);
}

/**
 * Valida un cupón / tarjeta de regalo contra el servidor SIN gastarlo
 * (pos.config.use_coupon_code solo consulta; el cupón se gasta al cobrar).
 * @returns {Promise<{program: object, points: number}|{error: string}>}
 */
export async function checkCouponCode(pos, code) {
    const order = pos.getOrder();
    let result;
    try {
        result = await pos.data.call("pos.config", "use_coupon_code", [
            [pos.config.id],
            code,
            order.date_order,
            order.getPartner()?.id || false,
            order.pricelist_id?.id || false,
        ]);
    } catch {
        return { error: _t("No se pudo validar el código: revise la conexión e intente de nuevo.") };
    }
    if (!result.successful) {
        return { error: result.payload.error_message || _t("Este código no es válido.") };
    }
    const program = pos.models["loyalty.program"].get(result.payload.program_id);
    if (!program) {
        return { error: _t("El programa de este código no está disponible en este punto de venta.") };
    }
    // Las tarjetas de lealtad (puntos del cliente) no son bonos: pos.activateCode
    // solo asignaría el cliente a la orden, sin aplicar ningún descuento.
    if (!CODE_PROGRAM_TYPES.includes(program.program_type)) {
        return { error: _t("Este código no es un bono de descuento.") };
    }
    return { program, points: result.payload.points };
}

// ------------------------------------------------------------- acciones

/**
 * Activa un código en la orden actual y devuelve su programa.
 * - Si el código ya estaba activado pero el cajero quitó su descuento, vuelve
 *   a aplicar la recompensa (para que el cliente no pierda el bono).
 * - Si no, usa `pos.activateCode` de pos_loyalty (regla o cupón).
 * @returns {Promise<{program: object}|{error: string}>}
 */
export async function activateCode(pos, code) {
    const order = pos.getOrder();
    const activated = getActivatedProgram(order, code);
    if (activated) {
        if (!programHasRewardLine(order, activated.program.id)) {
            const reapplied = await reenableActivatedProgram(pos, order, activated);
            if (reapplied !== true) {
                return { error: reapplied };
            }
        }
        return { program: activated.program };
    }
    const res = await pos.activateCode(code);
    // `activateCode` puede devolver un mensaje aunque el código haya quedado
    // activado (p. ej. saldo de tarjeta de regalo): se decide por el estado.
    const nowActivated = getActivatedProgram(order, code);
    if (!nowActivated) {
        return { error: (res !== true && res) || _t("No fue posible aplicar el código.") };
    }
    return { program: nowActivated.program };
}

/**
 * Quita un código activado y sus líneas de descuento de la orden actual.
 * pos_loyalty no tiene un método público para desactivar un código: se
 * deshace lo que hizo `pos.activateCode` y se recalculan las recompensas.
 */
export async function deactivateCode(pos, code, programId) {
    const order = pos.getOrder();
    const rule = code ? findCodeRule(order, code) : null;
    if (rule) {
        const rules = order.uiState.codeActivatedProgramRules;
        const index = rules.indexOf(rule.id);
        if (index >= 0) {
            rules.splice(index, 1);
        }
    }
    const coupon = code ? order._code_activated_coupon_ids.find((c) => c.code === code) : null;
    if (coupon) {
        delete order.uiState.couponPointChanges[coupon.id];
        // Igual que pos_loyalty al quitar la línea de un cupón activado
        // (OrderSummary._setValue): se borra la tarjeta cargada en el POS.
        coupon.delete();
    }
    for (const line of getProgramRewardLines(order, programId)) {
        line.delete();
    }
    await pos.orderUpdateLoyaltyPrograms();
    pos.updateRewards();
}

/**
 * Vuelve a aplicar la recompensa de un código activado cuyo descuento quitó el
 * cajero (pos_loyalty la deja en `uiState.disabledRewards`). Replica lo que
 * hace `pos.activateCode` al activar un código: si hay una sola recompensa
 * reclamable, la aplica.
 * @returns {Promise<true|string>} true o el mensaje de error.
 */
async function reenableActivatedProgram(pos, order, activated) {
    for (const reward of activated.program.reward_ids) {
        order.uiState.disabledRewards.delete(reward.id);
    }
    await pos.orderUpdateLoyaltyPrograms();
    const claimable = activated.couponId
        ? order.getClaimableRewards(activated.couponId)
        : order.getClaimableRewards(false, activated.program.id);
    if (claimable.length !== 1) {
        return _t("No fue posible volver a aplicar el código: revise las recompensas de la orden.");
    }
    const { reward, coupon_id } = claimable[0];
    if (reward.reward_type === "product" && reward.multi_product) {
        return _t("Este bono requiere elegir el producto: use el botón Recompensas.");
    }
    const res = order._applyReward(reward, coupon_id);
    if (res !== true) {
        return res || _t("No fue posible aplicar el código.");
    }
    pos.updateRewards();
    return true;
}
