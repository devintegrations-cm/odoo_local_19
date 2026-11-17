# -*- coding: utf-8 -*-
# MOD-VOUCHER DROP: elimina columnas huerfanas vaucher.
# Hoy no corre (manifiesto en 19.0.1.1.x). Si algun dia corre, solo borra una
# columna vieja cuando no le queda ningun dato sin copiar a la nueva
# (POS-VOUCHER-NUM-DL-0002): antes borraba sin validar.
import logging

_logger = logging.getLogger(__name__)

# tabla, columna vieja, columna nueva
_PARES = (
    ("pos_payment", "vaucher_num", "voucher_num"),
    ("account_move_line", "vaucher_num_account", "voucher_num_account"),
)


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    _logger.info("pos_voucher_num pre-migrate %s: DROP huerfanas vaucher", version)
    for table, old, new in _PARES:
        if not _column_exists(cr, table, old):
            _logger.info("  %s.%s no existe -> nada", table, old)
            continue
        if not _column_exists(cr, table, new):
            _logger.warning("  %s.%s existe pero %s no: NO se borra", table, old, new)
            continue
        # Nombres constantes de _PARES, no entrada externa.
        cr.execute(f"""
            SELECT COUNT(*) FROM {table}
            WHERE COALESCE({old}, '') <> ''
              AND COALESCE({new}, '') IS DISTINCT FROM COALESCE({old}, '')
        """)
        pendientes = cr.fetchone()[0]
        if pendientes:
            _logger.warning(
                "  %s.%s tiene %s filas sin copiar o distintas de %s: NO se borra",
                table, old, pendientes, new,
            )
            continue
        cr.execute(f"ALTER TABLE {table} DROP COLUMN {old}")
        _logger.info("  %s.%s DROP OK", table, old)
