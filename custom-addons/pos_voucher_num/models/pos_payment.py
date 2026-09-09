# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    # OJO: el nombre del campo tiene una errata historica ("vaucher" en vez de
    # "voucher"). NO se renombra: hay datos en la columna y renombrarlo exige
    # una migracion aparte. El JS del POS escribe exactamente este nombre.
    vaucher_num = fields.Char(string="Numero Voucher")

    # Odoo 19: `pos.payment` NO define `_load_pos_data_fields`, hereda el default
    # de `pos.load.mixin` ([]), y `read([])` devuelve TODOS los campos. Por eso
    # `vaucher_num` viaja al POS y vuelve al servidor sin declarar nada mas.
    # Definir aqui `_load_pos_data_fields` seria un error grave: super() devuelve
    # [] y la lista pasaria a contener solo este campo, rompiendo el POS entero.
