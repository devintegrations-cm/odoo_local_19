/** @odoo-module **/

import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { patch } from "@web/core/utils/patch";

patch(PrinterService.prototype, {
    setup(env) {
        super.setup(...arguments);
        // El core no guarda `env`, y aquí hace falta para llegar al store del POS.
        // No se resuelve el servicio `pos` ahora: `printer` no depende de `pos`, así
        // que en este momento puede no estar arrancado todavía. Al imprimir sí lo está.
        this.ptcEnv = env;
    },

    /**
     * Incrusta los códigos del ticket antes de rasterizarlo.
     *
     * Por aquí pasan las formas de imprimir del POS (pantalla de pago, pantalla
     * de recibo, botón de reimprimir y pantalla de reimpresión), así que es el
     * único punto que hay que cubrir para la impresora. En Odoo 19 el recibo
     * llega como `props.order` (el `PoSOrder` vivo, no datos serializados).
     *
     * Es obligatorio hacerlo ANTES de `super.print()`: es quien llama a
     * `htmlToCanvas`, cuya caché de recursos ignora la query string y confundiría
     * unos códigos con otros. Ver `fetchImageDataUrl` en `receipt_block_utils.js`.
     */
    async print(component, props, options) {
        const pos = this.ptcEnv?.services?.pos;
        if (pos?.resolveCustomReceiptBlockImages && props?.order) {
            await pos.resolveCustomReceiptBlockImages(pos.getCustomReceiptBlocks(props.order));
        }
        return await super.print(...arguments);
    },
});