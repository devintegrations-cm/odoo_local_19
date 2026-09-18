import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Cliente por defecto configurado en `pos.config.pos_customer_id`.
     *
     * El core llama a este metodo en dos lugares (pos_store.js:1309 y :1357):
     * al construir un pedido nuevo en `createNewOrder`, y en `getEmptyOrder`
     * para reconocer un pedido vacio como reutilizable. Por eso devolvemos el
     * **id** y no el registro: `getEmptyOrder` compara `order.partner_id.id`
     * contra este valor.
     *
     * Se lee de `config.raw` porque el many2one solo resuelve a registro si el
     * partner esta cargado en el POS; el id crudo esta siempre. La comprobacion
     * contra `this.models["res.partner"]` evita devolver un id que el store no
     * puede resolver (dejaria el pedido sin cliente en silencio).
     */
    getDefaultPartnerId() {
        const partnerId = this.config.raw?.pos_customer_id;
        if (partnerId && this.models["res.partner"].get(partnerId)) {
            return partnerId;
        }
        return super.getDefaultPartnerId(...arguments);
    },
});
