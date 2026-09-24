# -*- coding: utf-8 -*-
# MOD-001: pos_obligatory_invoice — renombre enable_msg_obli_invoice -> enable_obin
# Referencia v17: col/dev_mb obligatory_invoice_msg/models/pos_config.py:5
# Destino  v19: odoo_col_19/custom-addons/pos_obligatory_invoice/models/pos_config.py:5
# Evidencia staging: 2 pos_config con enable_msg_obli_invoice=true (Burgerville-2, Respaldo Calle85)
# Objetivo: no perder facturacion obligatoria al migrar 17->19

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    _logger.info("pos_obligatory_invoice pre-migrate %s: migrando enable_msg_obli_invoice -> enable_obin", version)

    has_old = _column_exists(cr, "pos_config", "enable_msg_obli_invoice")
    has_new = _column_exists(cr, "pos_config", "enable_obin")

    if not has_old and not has_new:
        _logger.info("  ninguna columna existe (instalacion limpia) -> nada que migrar")
        return

    if has_old and not has_new:
        # RENAME preserva datos, indices y es atomico. Idempotente.
        _logger.info("  enable_obin no existe, renombrando enable_msg_obli_invoice -> enable_obin")
        cr.execute("ALTER TABLE pos_config RENAME COLUMN enable_msg_obli_invoice TO enable_obin")
        _logger.info("  RENAME completado")
        return

    if has_old and has_new:
        # Ambos existen (reintento o instalacion parcial): copiar solo donde falta
        cr.execute("""
            SELECT COUNT(*) FROM pos_config
            WHERE enable_msg_obli_invoice IS TRUE
              AND (enable_obin IS NULL OR enable_obin = false)
        """)
        pending = cr.fetchone()[0]
        if pending:
            _logger.info("  ambas columnas existen, copiando %s filas enable_msg_obli_invoice=true -> enable_obin", pending)
            cr.execute("""
                UPDATE pos_config
                SET enable_obin = true
                WHERE enable_msg_obli_invoice IS TRUE
                  AND (enable_obin IS NULL OR enable_obin = false)
            """)
            _logger.info("  UPDATE copio %s filas", cr.rowcount)
        else:
            _logger.info("  ambas columnas existen pero nada pendiente -> idempotente OK")
        # No se borra columna vieja aqui: queda huerfana documentada hasta validacion post
        return

    if not has_old and has_new:
        _logger.info("  solo enable_obin existe (ya migrado) -> nada que hacer")
        return
