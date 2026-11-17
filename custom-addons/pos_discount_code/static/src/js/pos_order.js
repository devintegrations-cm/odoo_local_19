/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

const { DateTime } = luxon;

/**
 * Datos del canje en la orden.
 *
 * Los campos `discount_*` son campos de `pos.order`: Odoo 19 los carga, los
 * guarda en la orden local y los sincroniza solos (en 17 había que
 * serializarlos a mano). Aquí solo se asignan; el servidor los valida al
 * sincronizar (`_process_order` / `_process_saved_order`).
 * `discount_amount` y `discount_state` se calculan en el servidor.
 */
patch(PosOrder.prototype, {
    setDiscountCode({ program, code, docType, docNumber }) {
        this.discount_program_id = program;
        this.discount_name = program.name;
        this.discount_code = code;
        this.discount_vigencia = program.date_to || false;
        this.discount_doc_type = docType;
        this.discount_doc_number = docNumber;
        // La serialización lo envía en UTC, como lo espera el servidor.
        this.discount_redeem_date = DateTime.now();
    },
    clearDiscountCode() {
        this.discount_program_id = false;
        this.discount_name = false;
        this.discount_code = false;
        this.discount_vigencia = false;
        this.discount_doc_type = false;
        this.discount_doc_number = false;
        this.discount_redeem_date = false;
    },
});
