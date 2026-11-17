import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/**
 * Botones de propina por porcentaje en la pantalla de pago.
 *
 * Ninguno de estos metodos existe en PaymentScreen (19.0), asi que no hay super()
 * que llamar. El unico metodo del core con nombre parecido es `addTip()`
 * (payment_screen.js:224), que NO se pisa: se sigue usando cuando el POS no tiene
 * porcentajes configurados.
 */
patch(PaymentScreen.prototype, {
    /**
     * Linea del producto de propina del pedido en curso, si existe.
     */
    getTipLine() {
        const tipProduct = this.pos.config.tip_product_id;
        if (!tipProduct) {
            return null;
        }
        return this.currentOrder.lines.find((line) => line.getProduct() === tipProduct) || null;
    },

    /**
     * Propina ya cargada, medida en la misma unidad que la base elegida.
     *
     * Importa que coincidan: `order.getTip()` (pos_order.js:309) devuelve el importe
     * SIN impuestos de la linea de propina. Si la base es el total CON impuestos y el
     * producto de propina tuviera impuestos configurados, restar el importe sin
     * impuestos dejaria la base inflada. La linea expone las dos medidas.
     */
    getTipAmount(withTax) {
        const line = this.getTipLine();
        if (!line) {
            return 0;
        }
        const prices = line.prices;
        if (withTax) {
            return prices.total_included_currency ?? prices.total_excluded_currency ?? 0;
        }
        return prices.total_excluded_currency ?? 0;
    },

    /**
     * Base sobre la que se aplica el porcentaje, segun `tip_percent_base`.
     *
     * En ambos casos se descuenta la propina ya cargada: `priceExcl` y `priceIncl`
     * incluyen la linea de propina, asi que sin restarla aplicar 10% dos veces
     * capitalizaria sobre la propina anterior.
     */
    getTipBase() {
        const order = this.currentOrder;
        const withTax = this.pos.config.tip_percent_base === "with_tax";
        const total = withTax ? order.priceIncl : order.priceExcl;
        // Se redondea a la precision de la moneda. Sin esto, la resta arrastra residuo
        // binario -66,13 - 8,63 da 57.49999999999999- y el porcentaje cae del lado
        // equivocado del medio centavo: pulsar el mismo boton dos veces cambiaba lo
        // que se le cobra al cliente, oscilando entre 8,63 y 8,62.
        return this.pos.currency.round(total - this.getTipAmount(withTax));
    },

    /**
     * Redondeo configurable por punto de venta (`tip_percent_decimals`).
     *
     * Con 0 decimales redondea a la unidad, que es lo adecuado en COP, CLP y CRC:
     * un cafe ronda los 8.000 / 3.000 / 2.000, asi que el redondeo es imperceptible
     * y evita propinas con decimales incomodos de cobrar. En monedas donde el
     * porcentaje da importes chicos conviene subirlo, porque con 0 decimales los
     * botones de 10% y 15% pueden terminar dando el mismo importe, o cero.
     */
    roundTip(amount) {
        const decimals = Math.min(6, Math.max(0, this.pos.config.tip_percent_decimals || 0));
        // roundDecimals del nucleo y no Math.round a mano: maneja el epsilon y parsea
        // notacion cientifica para que 8,625 redondee a 8,63 y no a 8,62
        // (web/core/utils/numbers.js:107). Es el mismo helper que usa el POS en la balanza.
        return roundDecimals(amount, decimals);
    },

    /**
     * Importe de propina que corresponde a `tipPercent`.
     */
    getTipX(tipPercent) {
        // Se multiplica antes de dividir por prolijidad, pero no es lo que arregla el
        // problema del medio centavo: medido, con la base sucia los dos ordenes dan
        // 8,62. Lo que lo arregla es el redondeo de la base en getTipBase().
        return this.roundTip((this.getTipBase() * tipPercent) / 100);
    },

    /**
     * Se compara contra el precio unitario de la linea porque es exactamente lo que
     * `pos.setTip()` escribe (pos_store.js:818, `line.setUnitPrice(tip)`). Comparar
     * contra el importe sin impuestos fallaria si el producto de propina tuviera
     * impuestos configurados.
     */
    shouldHighlight(tipPercent) {
        const line = this.getTipLine();
        if (!line) {
            return false;
        }
        const currency = this.pos.currency;
        return (
            !currency.isZero(line.price_unit) &&
            currency.equal(line.price_unit, this.getTipX(tipPercent))
        );
    },

    /**
     * `setTip` se movio al store en 19 (app/services/pos_store.js:811): crea o
     * actualiza la linea del producto de propina del pedido en curso.
     */
    async addTipPercent(tipPercent) {
        const tipAmount = this.getTipX(tipPercent);
        if (!tipAmount) {
            // No se agrega una propina de 0: dejaria una linea de propina vacia.
            return;
        }
        // Como en la 17 (solo set_tip): no se toca la linea de pago. Sumarle la propina
        // con efectivo y cambio inflaba el pago registrado y descuadraba la caja
        // (POS-TIP-PERCENT-FE-0001, C5); el cambio del pedido ya se recalcula solo.
        await this.pos.setTip(tipAmount);
    },

    async addTip1() {
        await this.addTipPercent(this.pos.config.tip_percent1);
    },
    async addTip2() {
        await this.addTipPercent(this.pos.config.tip_percent2);
    },
    async addTip3() {
        await this.addTipPercent(this.pos.config.tip_percent3);
    },
});
