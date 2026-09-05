import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Oculta de la grilla de productos los que no estan asignados a este punto de venta.
     *
     * Por que un filtro VISUAL y no sacar registros del store: Odoo 19 agrega
     * productos DESPUES de aplicar el dominio de carga, por cinco vias distintas
     * (point_of_sale/models/product_template.py): items de combo, productos
     * especiales, producto de propina, productos opcionales y productos de los
     * pedidos abiertos. En restaurante, donde siempre hay mesas abiertas, esa
     * ultima via es la que mas pesa. Odoo 17 solo hacia lo de combos, asi que el
     * filtro por dominio, que alcanzaba entonces, en 19 ya no alcanza.
     *
     * Esos productos tienen que seguir CARGADOS: si se los quita del store, un
     * pedido abierto que los referencie se queda sin el registro y la mesa se
     * rompe. De ahi que el filtro sea visual, que es ademas lo que el modulo
     * persigue: que el cajero no vea lo que no corresponde a su local, sin
     * alterar el pedido.
     *
     * getExcludedProductIds() es el gancho del propio nucleo: devuelve ids de
     * product.template y productsToDisplay los saltea al armar la grilla.
     */
    getExcludedProductIds() {
        const configId = this.config.id;
        // Set y no array: el nucleo ya aporta Tips y los productos especiales, que
        // tampoco estan asignados a ninguna configuracion, asi que sin deduplicar la
        // lista los traeria dos veces.
        const excluidos = new Set(super.getExcludedProductIds(...arguments));

        // Se recorre todo el catalogo cargado en cada llamada. Esta acotado: el POS
        // nunca carga mas de DEFAULT_LIMIT_LOAD_PRODUCT plantillas (5000, en
        // point_of_sale/models/pos_config.py:15). No se cachea a proposito, porque el
        // catalogo del cliente crece durante la sesion -"Search more" y la busqueda en
        // servidor agregan registros- y una cache mal invalidada mostraria productos
        // ajenos, que es justo lo que este modulo evita.
        for (const tmpl of this.models["product.template"].getIterator()) {
            // Se lee de `raw` y no del getter relacional: el m2m apunta a pos.config y
            // el store solo tiene cargada la configuracion actual, asi que el getter no
            // resolveria las demas. El id crudo esta siempre.
            if (!(tmpl.raw?.ro_pos_config_ids || []).includes(configId)) {
                excluidos.add(tmpl.id);
            }
        }

        return [...excluidos];
    },
});
