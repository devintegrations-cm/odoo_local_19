# -*- coding: utf-8 -*-
"""Carga el código de dispersión en los bancos creados por el módulo.

19.0.1.0.4 añade `res.bank.dispersal_code` y lo declara en
`data/res_bank_data.xml` (bloque noupdate="0"), pero los 68 bancos de
producción se crearon en 17 con noupdate=1: Odoo conserva el noupdate
guardado en ir.model.data y SALTA la actualización aunque el XML ahora diga
noupdate="0" (orm/models.py: `if not (update and d_noupdate)`). Sin este
script los bancos quedarían sin código y la validación bloquearía todos los
lotes con "Bancos sin Código de Dispersión".

La fuente de verdad es el propio XML del módulo: se parsea en cada corrida,
así que si se agregan bancos en el XML, este script los cubre sin cambios.

Idempotente: solo escribe donde `dispersal_code` esté vacío (nunca pisa un
código cargado a mano, p.ej. el 001809 que tesorería asignará a NU).

También corrige el BIC de HSBC: el declarado (BCMRMXMMPYM) es de HSBC
México, no de Colombia. Se vacía en el XML y aquí en la base (el registro
también es noupdate=1, el XML por sí solo no lo corregiría).

Regla del proyecto: los conteos van al log con _logger (en odoo.sh el log
del upgrade es el del logger, no la salida estándar).
"""
import logging
import xml.etree.ElementTree as ET

from odoo.tools.misc import file_open

_logger = logging.getLogger(__name__)

MODULE = 'account_payment_dispersion'
HSBC_MX_BIC = 'BCMRMXMMPYM'


def _read_dispersal_codes():
    """{xmlid local: dispersal_code} declarado en data/res_bank_data.xml."""
    codes = {}
    with file_open('%s/data/res_bank_data.xml' % MODULE, 'rt') as handle:
        root = ET.parse(handle).getroot()
    for record in root.iter('record'):
        field = record.find("./field[@name='dispersal_code']")
        if field is not None and (field.text or '').strip():
            codes[record.get('id')] = field.text.strip()
    return codes


def migrate(cr, version):
    if not version:
        # Instalación limpia: el XML (con noupdate=0 y sin registro previo)
        # ya aplicó los códigos al crear los bancos.
        return

    written = 0
    for xmlid_local, code in _read_dispersal_codes().items():
        cr.execute(
            """
            UPDATE res_bank b
               SET dispersal_code = %s
              FROM ir_model_data d
             WHERE d.model = 'res.bank'
               AND d.module = %s
               AND d.name = %s
               AND b.id = d.res_id
               AND (b.dispersal_code IS NULL OR b.dispersal_code = '')
            """,
            (code, MODULE, xmlid_local),
        )
        written += cr.rowcount

    # BIC de HSBC México: se vacía solo si nadie lo reemplazó a mano.
    cr.execute(
        "UPDATE res_bank SET bic = NULL WHERE bic = %s",
        (HSBC_MX_BIC,),
    )
    hsbc_fixed = cr.rowcount

    cr.execute(
        """
        SELECT count(*) FROM res_bank b
         JOIN ir_model_data d ON d.model = 'res.bank' AND d.module = %s AND d.res_id = b.id
        WHERE b.dispersal_code IS NULL OR b.dispersal_code = ''
        """,
        (MODULE,),
    )
    pending = cr.fetchone()[0]
    _logger.info(
        "account_payment_dispersion 19.0.1.0.4: %s bancos con código de "
        "dispersión cargado, %s con BIC HSBC México corregido, %s pendientes "
        "(se espera 1: HSBC res_bank_1010, sin código en el XML)",
        written, hsbc_fixed, pending,
    )
