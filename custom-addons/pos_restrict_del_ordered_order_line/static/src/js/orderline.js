/** @odoo-module */

import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";

patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
        this.dialogService = useService("dialog");
    },

    isProductScreenFun() {
        return ["ProductScreen", "PaymentScreen"].includes(this.pos.router.state.current);
    },

    _changeQuantity(delta) {
        const line = this.props.line;
        if (!line) {
            return;
        }
        const result = line.setQuantity(line.getQuantity() + delta);
        if (result !== true && result) {
            this.dialogService.add(AlertDialog, result);
        }
    },

    addQuantity() {
        this._changeQuantity(1);
    },

    subsQuantity() {
        this._changeQuantity(-1);
    },
});
