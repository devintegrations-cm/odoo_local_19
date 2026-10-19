/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Inyecta la configuración de la comanda en los datos del template.
     *
     * `getOrderData` es la única fuente del objeto `data` del template
     * `point_of_sale.OrderChangeReceipt`: todos los tickets de preparación
     * (nuevos, cancelados, actualización de notas y notas internas) pasan
     * por aquí antes de renderizarse. `pos_restaurant` también parcha este
     * método encadenando `super`, así que los dos patches conviven.
     *
     * Los valores llegan del frontend de `pos.config` sin loader (pos.config
     * no define `_load_pos_data_fields`, el mixin pasa `[]` y `read([])`
     * lee todos los campos). Se añaden defaults defensivos por si la
     * configuración de la sesión se abrió con una versión anterior del
     * módulo.
     */
    getOrderData(order, reprint) {
        const data = super.getOrderData(...arguments);
        data.comanda_opts = {
            padding_top: this.config.comanda_padding_top || 0,
            padding_bottom: this.config.comanda_padding_bottom || 0,
            show_employee: this.config.comanda_show_employee !== false,
            show_reference: this.config.comanda_show_reference !== false,
            spanish_labels: this.config.comanda_spanish_labels !== false,
        };
        return data;
    },
});
