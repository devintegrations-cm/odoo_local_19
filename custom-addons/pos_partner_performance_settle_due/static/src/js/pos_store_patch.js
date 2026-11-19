/** @odoo-module */
/**
 * pos_settle_due pide al servidor la deuda de TODOS los clientes cargados en el
 * POS: al abrir la caja (PosStore.setup) y después de cada búsqueda de clientes
 * (PartnerList.searchPartner). Con carteras grandes cada cálculo tarda decenas
 * de segundos y ocupa al servidor para todas las cajas.
 *
 * Si la caja tiene marcado "No calcular la deuda de los clientes"
 * (pos.config.skip_partner_due), no se llama al servidor. Ojo: la versión
 * original BORRA del POS los clientes que no vengan en la respuesta, por eso no
 * se simula una respuesta vacía: se devuelve lo mismo que devolvía, sin tocar
 * los clientes.
 */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setAllTotalDueOfPartners(partners) {
        if (!this.config.skip_partner_due) {
            return super.setAllTotalDueOfPartners(...arguments);
        }
        return [partners];
    },
});
