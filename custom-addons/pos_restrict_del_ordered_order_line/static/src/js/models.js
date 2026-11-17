/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Referencia compartida al PosStore, fijada por el patch de PosStore
// (ver pos_store.js). Permite que los modelos de datos accedan al
// cashier, la configuracion y el router sin tener `this.pos`.
// `internalOps` > 0 mientras corre la parte sincronica de una operacion
// interna del nucleo (unir/separar mesas, transferir pedido): esas
// operaciones reacomodan cantidades entre pedidos y no deben pasar por el
// permiso del cajero. Ver pos_store.js.
export const posRestrictState = { pos: null, internalOps: 0 };

function restrictErrorMessage() {
    return {
        title: _t("Operacion no permitida"),
        body: _t("La cantidad de este producto ya fue enviada a cocina y no puede reducirse ni eliminarse."),
    };
}

patch(PosOrderline.prototype, {
    /**
     * En Odoo 19 setQuantity devuelve `true` si tuvo exito o un objeto
     * `{title, body}` con el error; el llamador muestra el dialogo.
     * Bloqueamos reducciones por debajo de la cantidad ya ordenada
     * (enviada a cocina) salvo empleado autorizado, pantalla de split u
     * operacion interna del nucleo (unir/separar mesas).
     *
     * Un aumento (quant >= qty actual) nunca se bloquea: si la linea quedo
     * con enviado > cantidad (p. ej. un autorizado la redujo), agregar el
     * mismo producto pasa por tryMergeOrderline -> merge -> setQuantity, que
     * ignora el error y borra la linea nueva: el producto no se agregaba y
     * nadie avisaba.
     */
    setQuantity(quantity, keep_price) {
        const quant =
            typeof quantity === "number" ? quantity : parseFloat("" + (quantity ? quantity : 0));
        if (
            quant < (this.ordered_quantities || 0) &&
            quant < this.qty &&
            !posRestrictState.internalOps &&
            !this.isCapableToDeletePosOrderLines() &&
            !this.isSplitBillScreen()
        ) {
            return restrictErrorMessage();
        }
        return super.setQuantity(quantity, keep_price);
    },

    /**
     * Fusionar dos lineas (unir mesas, transferir un pedido a una mesa
     * ocupada, agregar un producto que ya esta en el pedido) suma tambien lo
     * enviado a cocina: si no, lo enviado de la linea absorbida queda sin
     * proteger (en la mesa destino quedaba qty 3 / enviado 2).
     */
    merge(orderline) {
        // Lo enviado absorbido nunca supera la cantidad de la linea absorbida.
        const absorbedOrdered = Math.max(
            0,
            Math.min(orderline.ordered_quantities || 0, orderline.getQuantity())
        );
        const result = super.merge(...arguments);
        if (absorbedOrdered) {
            this.update({ ordered_quantities: (this.ordered_quantities || 0) + absorbedOrdered });
        }
        return result;
    },

    shouldShowOrderedQty() {
        return Boolean(this.ordered_quantities) && !this.is_reward_line;
    },

    isSplitBillScreen() {
        const pos = posRestrictState.pos;
        return pos?.router?.state?.current === "SplitBillScreen";
    },

    isCapableToDeletePosOrderLines() {
        const pos = posRestrictState.pos;
        if (!pos || !pos.config.module_pos_hr) {
            // Sin login de empleados el cajero es un res.users: su id no se
            // puede comparar con ids de hr.employee, asi que la regla no aplica
            // (ed0a689, Colombia). En staging/prod la unica caja sin pos_hr
            // tiene la lista vacia: no cambia el comportamiento de 17.
            return true;
        }
        const cashier = pos.getCashier();
        // Se lee `raw` (ids crudos): el getter relacional descarta los
        // empleados que el store no cargo (pos_hr solo carga los de la caja)
        // y una lista que queda vacia significaria "todos pueden".
        // Mismo patron que pos_del_order.
        const allowed =
            pos.config.raw?.able_del_pol_employee_ids ?? pos.config.able_del_pol_employee_ids ?? [];
        const allowedIds = (Array.isArray(allowed) ? allowed : [])
            .map((item) => (typeof item === "object" && item !== null ? item.id : item))
            .filter((id) => typeof id === "number");
        if (cashier && allowedIds.length > 0) {
            return allowedIds.includes(cashier.id);
        }
        // Lista vacia: todos los empleados pueden (comportamiento por defecto)
        return true;
    },
});

patch(PosOrder.prototype, {
    /**
     * En Odoo 19 el boton de borrar linea ("remove") no pasa por
     * setQuantity: llama directamente a removeOrderline. Bloqueamos
     * aqui la eliminacion de lineas ya ordenadas.
     */
    removeOrderline(line) {
        const lines = line.getAllLinesInCombo ? line.getAllLinesInCombo() : [line];
        const hasOrderedQty = lines.some((l) => (l.ordered_quantities || 0) > 0);
        if (
            hasOrderedQty &&
            !line.isCapableToDeletePosOrderLines() &&
            !line.isSplitBillScreen()
        ) {
            const pos = posRestrictState.pos;
            pos?.dialog.add(AlertDialog, restrictErrorMessage());
            return false;
        }
        return super.removeOrderline(line);
    },
});

patch(OrderSummary.prototype, {
    /**
     * Odoo 19 tiene un flujo nativo de reduccion de lineas ya sincronizadas
     * que crea una linea de correccion negativa en lugar de bajar la cantidad
     * (handleDecreaseLine). Ese flujo no pasa por el guard de setQuantity,
     * asi que lo bloqueamos aqui para empleados no autorizados.
     */
    async updateQuantityNumber(newQuantity) {
        if (newQuantity !== null) {
            let selectedLine = this.currentOrder?.getSelectedOrderline();
            selectedLine = selectedLine?.combo_parent_id || selectedLine;
            if (
                selectedLine &&
                newQuantity < (selectedLine.ordered_quantities || 0) &&
                !selectedLine.isCapableToDeletePosOrderLines() &&
                !selectedLine.isSplitBillScreen()
            ) {
                this.dialog.add(AlertDialog, restrictErrorMessage());
                return false;
            }
        }
        return super.updateQuantityNumber(...arguments);
    },
});
