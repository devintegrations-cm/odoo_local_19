/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { posRestrictState } from "@pos_restrict_del_ordered_order_line/js/models";

patch(PosStore.prototype, {
    async setup(...args) {
        // Exponemos el store a los modelos de datos (guards de cantidad)
        posRestrictState.pos = this;
        return super.setup(...args);
    },

    /**
     * Guarda la cantidad actual de cada linea como "cantidad ordenada"
     * (enviada a cocina), igual que hacia el patch de submitOrder en v17.
     * La linea de propina no se envia a cocina: no se fija.
     */
    _captureOrderedQuantities(order) {
        if (!order) {
            return;
        }
        for (const line of order.getOrderlines()) {
            if (!line.is_reward_line && !line.isTipLine()) {
                line.ordered_quantities = line.getQuantity();
            }
        }
    },

    // Todas las vias de envio a cocina de 19 pasan por aqui: el boton "Order" (submitOrder) y el
    // aviso "la orden no se envio" que 19 muestra al pulsar "Pago" o el pago rapido
    // (_askForPreparation). En 17 solo existia el boton, por eso se parcheaba submitOrder.
    async sendOrderInPreparationUpdateLastChange(order, opts = {}) {
        if (!opts.cancelled) {
            this._captureOrderedQuantities(order);
        }
        return super.sendOrderInPreparationUpdateLastChange(...arguments);
    },

    /**
     * Ejecuta la parte sincronica de una operacion interna del nucleo sin el
     * guard de permisos del cajero. Los metodos de pos_restaurant que se
     * envuelven (mergeOrders, restoreOrdersToOriginalTable) mueven todas las
     * lineas antes de su primer `await` (syncAllOrders), asi que la bandera
     * se baja en cuanto super() devuelve la promesa y no se filtra a otras
     * acciones del cajero mientras se espera al servidor. `cleanup` corre en
     * el mismo finally sincronico (p. ej. soltar la instantanea de separar).
     *
     * Ojo (Community 9b5c002): `_mergeOrders` hace `await this._mergeLines()`
     * por linea, asi que al unir mesas solo la primera linea corre con la
     * bandera arriba. No afecta: unir solo AUMENTA cantidades (merge ->
     * setQuantity hacia arriba, que el guard nunca bloquea) o crea lineas
     * nuevas sin setQuantity. Donde la bandera hace falta es al separar
     * (restoreOrdersToOriginalTable baja cantidades), y ahi el bucle no tiene
     * ningun `await` antes de syncRestoredOrders.
     */
    _restrictRunInternal(callback, cleanup) {
        posRestrictState.internalOps++;
        try {
            return callback();
        } finally {
            posRestrictState.internalOps--;
            cleanup?.();
        }
    },

    /**
     * Unir mesas / transferir pedido (pos_restaurant 19). La suma de lo
     * enviado la hace el parche de PosOrderline.merge; las lineas que no se
     * fusionan se copian con `raw` y conservan su `ordered_quantities`.
     * Aqui se recuerda, por cada linea absorbida (clave = uuid que el nucleo
     * guarda como `formerUuid` en uiState.unmerge), cuanto tenia enviado,
     * para repartirlo bien si luego se separan las mesas. Se escribe antes
     * de super() para que el dato ya este en uiState cuando el nucleo
     * sincroniza el pedido al final de su parte sincronica (en la prueba en
     * navegador, escribirlo despues de super() no lo dejo en uiState).
     */
    async mergeOrders(sourceOrder, destOrder) {
        if (destOrder?.uiState && sourceOrder?.lines?.length) {
            const orderedByFormerUuid = { ...(destOrder.uiState.restrictOrderedByFormerUuid || {}) };
            for (const line of sourceOrder.lines) {
                orderedByFormerUuid[line.uuid] = line.ordered_quantities || 0;
            }
            destOrder.uiState.restrictOrderedByFormerUuid = orderedByFormerUuid;
        }
        return await this._restrictRunInternal(() => super.mergeOrders(...arguments));
    },

    /**
     * Separar mesas (pos_restaurant 19). El nucleo crea la linea de la mesa
     * original copiando `line.raw` (con TODO lo enviado de la linea unida) y
     * baja la linea que queda con line.setQuantity(), sin mirar si devolvio
     * error. Se desactiva el guard durante esa parte y lo enviado se reparte
     * en handlePreparationHistory, que el nucleo llama justo despues de
     * crear/ajustar cada par de lineas y antes de syncAllOrders.
     */
    async restoreOrdersToOriginalTable(order, unmergeTable) {
        const snapshot = {};
        for (const [uuid, details] of Object.entries(order?.uiState?.unmerge || {})) {
            if (details.table_id !== unmergeTable?.id) {
                continue;
            }
            const line = order.lines.find((l) => l.uuid === uuid);
            if (line) {
                snapshot[uuid] = {
                    qty: line.qty,
                    ordered: line.ordered_quantities || 0,
                    sourceOrdered:
                        order.uiState.restrictOrderedByFormerUuid?.[details.formerUuid],
                };
            }
            // Ya se leyo: se limpia para que uiState no crezca con cada union.
            delete order.uiState.restrictOrderedByFormerUuid?.[details.formerUuid];
        }
        this._restrictUnmergeSnapshot = snapshot;
        // La instantanea se suelta en el finally sincronico, no tras el await al
        // servidor: una union hecha durante la espera no debe usarla.
        return await this._restrictRunInternal(
            () => super.restoreOrdersToOriginalTable(...arguments),
            () => {
                this._restrictUnmergeSnapshot = null;
            }
        );
    },

    handlePreparationHistory(srcPrep, destPrep, srcLine, destLine, qty) {
        const result = super.handlePreparationHistory(...arguments);
        const snap = this._restrictUnmergeSnapshot?.[srcLine?.uuid];
        if (snap && posRestrictState.internalOps) {
            this._restrictSplitOrdered(snap, srcLine, destLine, qty);
        }
        return result;
    },

    /**
     * Reparte lo enviado de la linea unida (snap.ordered) entre la linea que
     * vuelve a la mesa original (destLine, `movedQty` unidades) y la que se
     * queda (srcLine, snap.qty - movedQty unidades). La suma se conserva y
     * ninguna linea queda con enviado > cantidad:
     * - la que vuelve se lleva al menos lo que tenia enviado al unirse
     *   (sourceOrdered) y al menos lo que no cabe en la que se queda;
     * - si no hay registro del momento de unir (mesa unida antes de esta
     *   version), se lleva lo enviado hasta su cantidad.
     */
    _restrictSplitOrdered(snap, srcLine, destLine, movedQty) {
        const moved = Math.max(0, Math.min(movedQty, snap.qty));
        const remaining = Math.max(0, snap.qty - moved);
        const ordered = Math.max(0, Math.min(snap.ordered, snap.qty));
        const fromSource =
            typeof snap.sourceOrdered === "number" ? snap.sourceOrdered : Math.min(ordered, moved);
        const movedOrdered = Math.min(moved, ordered, Math.max(fromSource, ordered - remaining, 0));
        destLine.update({ ordered_quantities: movedOrdered });
        if (remaining > 0 && srcLine.order_id) {
            srcLine.update({ ordered_quantities: Math.min(ordered - movedOrdered, remaining) });
        }
    },

    // En 17 (Colombia y Mexico, origin/17.0 y origin/prod) el boton "Payment" llamaba a
    // order.pay() y NO fijaba cantidades: solo el boton "Order" del restaurante lo hacia. El
    // parche de pay() que se agrego al migrar bloqueaba lineas en retail al entrar a pagar. Se
    // quito para recuperar el comportamiento de 17 (QA 2026-09-17).
});
