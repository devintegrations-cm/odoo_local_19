# -*- coding: utf-8 -*-
"""El comprobante deja de ser un binario del soporte y pasa a ser un adjunto
de la operacion (attachment_id).

Hasta 17.0.1.3.x el archivo se guardaba en un ir.attachment del soporte
(res_model stock.operation.support, res_field support_file), invisible desde
la recepcion. Aqui ese mismo adjunto se pasa a la operacion y el soporte
apunta a el: no se copia ningun archivo.
"""
import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    has_filename = column_exists(cr, "stock_operation_support", "support_filename")
    cr.execute("""
        UPDATE ir_attachment a
           SET res_model = 'stock.picking',
               res_id = s.picking_id,
               res_field = NULL,
               name = %s
          FROM stock_operation_support s
         WHERE a.res_model = 'stock.operation.support'
           AND a.res_field = 'support_file'
           AND a.res_id = s.id
     RETURNING a.id, s.id
    """ % ("COALESCE(NULLIF(s.support_filename, ''), a.name)" if has_filename else "a.name"))
    moved = cr.fetchall()
    for attachment_id, support_id in moved:
        cr.execute("UPDATE stock_operation_support SET attachment_id = %s WHERE id = %s",
                   (attachment_id, support_id))
    _logger.info("[SOS] Migracion: %s comprobantes pasados a adjuntos de la operacion",
                 len(moved))
