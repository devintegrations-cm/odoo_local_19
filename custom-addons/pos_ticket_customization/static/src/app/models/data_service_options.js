/** @odoo-module **/

import { DataServiceOptions } from "@point_of_sale/app/models/data_service_options";
import { patch } from "@web/core/utils/patch";

/**
 * Los bloques del ticket se guardan en la IndexedDB del navegador y, al volver a
 * entrar al POS, el núcleo solo pide al servidor los registros modificados desde
 * la última carga (`pos.load.mixin._server_date_to_domain`) y los SUMA a los que
 * ya tenía (`data_service.js`, `loadInitialData`). Un bloque archivado o borrado
 * ya no llega, pero tampoco se quita del navegador: seguiría imprimiéndose.
 *
 * Los modelos de `cleanupModels` pasan por `pos.session.filter_local_data`, que
 * devuelve los ids que ya no existen o que `_unrelevant_records` descarta, y el
 * núcleo los borra de la IndexedDB. Es el mismo mecanismo que usa `pos_loyalty`
 * para `loyalty.program` (`pos_loyalty/static/src/app/models/data_service_options.js`).
 */
patch(DataServiceOptions.prototype, {
    get cleanupModels() {
        return [...super.cleanupModels, "pos.receipt.custom.block"];
    },
});
