# -*- coding: utf-8 -*-
# MOD-VOUCHER DROP: elimina columnas huerfanas vaucher tras validar sin_copiar=0
# Ejecutar solo tras validar en psql que COUNT sin_copiar == 0 y voucher_con_dato == 621606
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("pos_voucher_num pre-migrate %s: DROP huerfanas vaucher", version)
    # DROP IF EXISTS es seguro en reintentos y en instalacion limpia
    cr.execute("ALTER TABLE pos_payment DROP COLUMN IF EXISTS vaucher_num")
    _logger.info("  pos_payment.vaucher_num DROP IF EXISTS OK")
    cr.execute("ALTER TABLE account_move_line DROP COLUMN IF EXISTS vaucher_num_account")
    _logger.info("  account_move_line.vaucher_num_account DROP IF EXISTS OK")
    # voucher_num_account sin prefijo vaucher es columna distinta historica; no se toca aqui
    # Su DROP debe ser manual tras confirmar que ya no se usa en reportes
