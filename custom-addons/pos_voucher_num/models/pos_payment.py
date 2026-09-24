# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    voucher_num = fields.Char(string="Numero Voucher")

    # Odoo 19: `pos.payment` NO define `_load_pos_data_fields`, hereda el default
    # de `pos.load.mixin` ([]), y `read([])` devuelve TODOS los campos. Por eso
    # `voucher_num` viaja al POS y vuelve al servidor sin declarar nada mas.
    # Definir aqui `_load_pos_data_fields` seria un error grave: super() devuelve
    # [] y la lista pasaria a contener solo este campo, rompiendo el POS entero.

    # --- Legacy compatibility (vaucher_num -> voucher_num) -------------------
    # Adapter temporal: clientes POS con assets cacheados de antes del renombre
    # 19.0.1.1.0 siguen enviando `vaucher_num`. Sin esto, Odoo 19 lanza
    # ValueError: Invalid field y el pedido NO sincroniza (fallo duro en caja).
    # El log WARNING da visibilidad de consumidores legacy durante la fase de
    # observacion. Retirar en 19.0.1.2.0 cuando no quede ningun POS antiguo
    # (grep -Rni "vaucher" debe dar solo migrations/ y docs/).
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "vaucher_num" in vals:
                _logger.warning(
                    "legacy field vaucher_num received in pos.payment.create "
                    "(pos.order=%s) -> mapped to voucher_num",
                    vals.get("pos_order_id"),
                )
                if not vals.get("voucher_num"):
                    vals["voucher_num"] = vals.pop("vaucher_num")
                else:
                    vals.pop("vaucher_num")
        return super().create(vals_list)

    def write(self, vals):
        if "vaucher_num" in vals:
            _logger.warning(
                "legacy field vaucher_num received in pos.payment.write "
                "(ids=%s) -> mapped to voucher_num",
                self.ids,
            )
            if not vals.get("voucher_num"):
                vals["voucher_num"] = vals.pop("vaucher_num")
            else:
                vals.pop("vaucher_num")
        return super().write(vals)
