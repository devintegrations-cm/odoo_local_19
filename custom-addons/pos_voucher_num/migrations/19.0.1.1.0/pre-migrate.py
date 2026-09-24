# -*- coding: utf-8 -*-
# MOD-VOUCHER: pos_voucher_num — renombre vaucher -> voucher
# Objetivo: corregir errata historica sin perder 621k registros staging
# Patron idempotente tomado de pos_obligatory_invoice/migrations/19.0.1.0.0/pre-migrate.py
import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    return bool(cr.fetchone())


def _migrate_column(cr, table, old, new):
    has_old = _column_exists(cr, table, old)
    has_new = _column_exists(cr, table, new)

    if not has_old and not has_new:
        _logger.info("  %s.%s/%s ninguna columna existe (instalacion limpia) -> nada", table, old, new)
        return

    if has_old and not has_new:
        _logger.info("  %s: %s -> %s (RENAME atomico)", table, old, new)
        cr.execute(f'ALTER TABLE {table} RENAME COLUMN {old} TO {new}')
        _logger.info("  RENAME %s.%s -> %s completado", table, old, new)
        return

    if has_old and has_new:
        # Ambos existen (upgrade parcial/reintento): copiar solo donde falta
        cr.execute(f"""
            SELECT COUNT(*) FROM {table}
            WHERE {old} IS NOT NULL AND {old} <> ''
              AND ({new} IS NULL OR {new} = '')
        """)
        pending = cr.fetchone()[0]
        if pending:
            _logger.info("  %s ambas columnas existen, copiando %s filas %s -> %s", table, pending, old, new)
            cr.execute(f"""
                UPDATE {table}
                SET {new} = {old}
                WHERE {old} IS NOT NULL AND {old} <> ''
                  AND ({new} IS NULL OR {new} = '')
            """)
            _logger.info("  UPDATE copio %s filas en %s", cr.rowcount, table)
        else:
            _logger.info("  %s ambas columnas existen pero nada pendiente -> idempotente OK", table)
        # No se borra columna vieja aqui: queda huerfana hasta 19.0.1.2.0 tras validacion
        return

    if not has_old and has_new:
        _logger.info("  %s solo %s existe (ya migrado) -> nada", table, new)
        return


def migrate(cr, version):
    _logger.info("pos_voucher_num pre-migrate %s: vaucher -> voucher", version)
    _migrate_column(cr, "pos_payment", "vaucher_num", "voucher_num")
    _migrate_column(cr, "account_move_line", "vaucher_num_account", "voucher_num_account")
    # voucher_num_account historica duplicada en staging: si existe y ya se migro, no hacer nada
    # Se deja huerfana para auditoria; DROP en 19.0.1.2.0
