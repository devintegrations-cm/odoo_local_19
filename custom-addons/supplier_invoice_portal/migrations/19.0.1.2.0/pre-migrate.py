# -*- coding: utf-8 -*-
"""19.0.1.2.0: prepara la vista lista que en 17 se llamaba ``view_spr_request_tree``.

En Odoo 19 la carga de datos del ``-u`` NO recalcula ``ir.ui.view.type``: el
``write`` de ``ir.ui.view`` solo completa ``mode`` (``_compute_defaults``), asi
que una vista que en 17 quedo con ``type='tree'`` conserva ese tipo y, al
reescribirle el arch con ``<list>``, la validacion aborta el ``-u`` con
"root node ... should be a <tree>, not a <list>" (reproducido). Por eso aqui,
antes de cargar los datos:

1. se renombra el xmlid ``view_spr_request_tree`` -> ``view_spr_request_list``
   (solo si el nuevo todavia no existe: la unicidad module+name no lo permite);
2. se pasa a ``type='list'`` toda vista del modulo que siga en ``tree``;
3. se ajusta el nombre tecnico de la vista renombrada.

Idempotente: sin filas que coincidan, no toca nada.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data old
           SET name = 'view_spr_request_list'
         WHERE old.module = 'supplier_invoice_portal'
           AND old.model = 'ir.ui.view'
           AND old.name = 'view_spr_request_tree'
           AND NOT EXISTS (SELECT 1 FROM ir_model_data new
                            WHERE new.module = 'supplier_invoice_portal'
                              AND new.name = 'view_spr_request_list')
        """
    )
    renamed = cr.rowcount
    cr.execute(
        """
        UPDATE ir_ui_view
           SET type = 'list'
         WHERE type = 'tree'
           AND id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'supplier_invoice_portal'
                         AND model = 'ir.ui.view')
        """
    )
    retyped = cr.rowcount
    cr.execute(
        """
        UPDATE ir_ui_view
           SET name = 'supplier.payment.request.list'
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'supplier_invoice_portal'
                         AND model = 'ir.ui.view'
                         AND name = 'view_spr_request_list')
           AND name = 'supplier.payment.request.tree'
        """
    )
    _logger.info(
        "supplier_invoice_portal 19.0.1.2.0: xmlid de la lista renombrado: %s, "
        "vistas tree -> list: %s", renamed, retyped,
    )
