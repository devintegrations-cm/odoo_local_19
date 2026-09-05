/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { CashMoveListPopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_list_popup/cash_move_list_popup";

/**
 * Hides the delete control of a Cash In/Out movement for plain cashiers.
 *
 * Deleting a movement releases a slot of the per-session limit, so the
 * restriction belongs to the cash control rules of this module.
 * `pos.session.delete_cash_in_out` enforces the same condition server side;
 * this only keeps the cashier from discovering it by trial and error.
 *
 * Odoo grants `has_cash_delete_perm` to POS managers and to users with any
 * accounting group, which is why the manager flag of the session snapshot is
 * checked on top of it.
 */
patch(CashMoveListPopup.prototype, {
    get hasCashDeletePerm() {
        return (
            super.hasCashDeletePerm &&
            Boolean(this.pos.closingValidationInfo && this.pos.closingValidationInfo.is_manager)
        );
    },
});
