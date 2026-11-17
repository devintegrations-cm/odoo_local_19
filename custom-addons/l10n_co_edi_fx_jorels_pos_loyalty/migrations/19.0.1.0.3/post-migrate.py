# -*- coding: utf-8 -*-
"""Diario de facturas del POS: de Jorels 17 a Jorels 19 (hallazgo STG19-POSJ-0001).

En 17, Jorels (l10n_co_edi_jorels_pos 8dafcf3) facturaba cada caja con ``pos_config.electronic_invoice_journal_id``
cuando ``invoice_type`` era ``electronic`` o ``both``. Jorels 19 (b89e2ac) eliminó ese campo e ``invoice_type``: toda
factura del POS es electrónica y sale por el diario estándar ``pos_config.invoice_journal_id``, del que toma las
resoluciones (``account_move.py:1259-1299``). Sin este script cada caja queda facturando en su diario POS de 17
(resoluciones vencidas o sin resolución).

Momento: Odoo borra las columnas de los campos eliminados en ``ir.model.data._process_end``, después de los scripts
``pre``/``post``/``end`` de todos los módulos (``odoo/modules/loading.py:501-523``); este módulo depende de
``l10n_co_edi_jorels_pos``, así que aquí la columna todavía existe. Comprobado en el log del upgrade de staging
41847186: la columna llega viva de la plataforma de upgrade y se borra en la actualización local.

Idempotente: si la columna ya no existe (base actualizada o instalación nueva) no hace nada.
"""
import logging

_logger = logging.getLogger(__name__)


def _existe_columna(cr, tabla, columna):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (tabla, columna),
    )
    return bool(cr.fetchone())


TABLA_RESPALDO = "co19_bak_pos_config_jorels17"


def _respaldar(cr):
    """Guarda la configuración de Jorels 17 de cada caja antes de sobrescribirla (L10N-CO-EDI-FX-JORELS-POS-LOYALTY-DL-0001).

    Odoo borra después ``invoice_type`` y ``electronic_invoice_journal_id``, y el UPDATE de abajo pisa
    ``invoice_journal_id``: en las cajas 'both' el diario de la factura normal (ADXC, SUCLC, SML, ADPRO…) solo quedaría
    en el log. Esta tabla no la gestiona el ORM (Odoo no la toca ni la borra); sirve para la decisión D1. Idempotente:
    una segunda corrida no reemplaza lo ya guardado.
    """
    tipo = "invoice_type" if _existe_columna(cr, "pos_config", "invoice_type") else "NULL::varchar"
    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLA_RESPALDO} (
            pos_config_id integer PRIMARY KEY,
            company_id integer,
            name varchar,
            active boolean,
            invoice_type varchar,
            invoice_journal_id integer,
            electronic_invoice_journal_id integer,
            respaldado_en timestamp without time zone DEFAULT (now() at time zone 'UTC')
        )
        """
    )
    cr.execute(
        f"""
        INSERT INTO {TABLA_RESPALDO}
               (pos_config_id, company_id, name, active, invoice_type, invoice_journal_id, electronic_invoice_journal_id)
        SELECT id, company_id, name::varchar, active, {tipo}, invoice_journal_id, electronic_invoice_journal_id
          FROM pos_config
        ON CONFLICT (pos_config_id) DO NOTHING
        """
    )
    _logger.info("STG19-POSJ-0001: %s cajas respaldadas en %s", cr.rowcount, TABLA_RESPALDO)


def migrate(cr, version):
    if not version:
        return
    if not _existe_columna(cr, "pos_config", "electronic_invoice_journal_id"):
        _logger.info("STG19-POSJ-0001: pos_config.electronic_invoice_journal_id ya no existe; nada que migrar")
        return

    _respaldar(cr)

    filtro_tipo = ""
    if _existe_columna(cr, "pos_config", "invoice_type"):
        # 'normal' facturaba solo por el diario normal: se respeta y se reporta (decisión D1)
        filtro_tipo = "AND coalesce(c.invoice_type, 'electronic') <> 'normal'"

    # Solo diarios de venta de la misma compañía que la caja
    cr.execute(
        f"""
        SELECT c.id, c.invoice_journal_id, c.electronic_invoice_journal_id, je.code
          FROM pos_config c
          JOIN account_journal je ON je.id = c.electronic_invoice_journal_id
         WHERE c.electronic_invoice_journal_id IS NOT NULL
           AND c.electronic_invoice_journal_id IS DISTINCT FROM c.invoice_journal_id
           AND je.type = 'sale'
           AND je.company_id = c.company_id
           {filtro_tipo}
        """
    )
    filas = cr.fetchall()
    for config_id, anterior, electronico, codigo in filas:
        cr.execute(
            "UPDATE pos_config SET invoice_journal_id = %s WHERE id = %s",
            (electronico, config_id),
        )
        _logger.info(
            "STG19-POSJ-0001: pos_config %s invoice_journal_id %s -> %s (%s)",
            config_id, anterior, electronico, codigo,
        )

    if filtro_tipo:
        cr.execute(
            "SELECT id FROM pos_config WHERE invoice_type = 'normal' AND electronic_invoice_journal_id IS NOT NULL"
        )
        normales = [r[0] for r in cr.fetchall()]
        if normales:
            _logger.warning(
                "STG19-POSJ-0001: cajas con invoice_type 'normal' conservan su diario normal (Jorels 19 factura todo "
                "como electrónica; revisar decisión D1): %s", normales,
            )
    _logger.info("STG19-POSJ-0001: %s cajas reasignadas a su diario electrónico", len(filas))
