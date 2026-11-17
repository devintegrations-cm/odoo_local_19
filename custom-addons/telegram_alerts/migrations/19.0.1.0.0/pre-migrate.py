# -*- coding: utf-8 -*-
"""Desactiva la vista de ajustes del POS que Jorels 17 deja en la base.

No tiene que ver con Telegram: está aquí por el orden de carga. Jorels es un
tercero (submódulo) y no se parchea, y su 19.0 no trae scripts para venir de 17.

Jorels 17 (`8dafcf3`) declaraba en `l10n_co_edi_jorels_pos` la vista
`res_config_settings_view_form_l10n_co_edi_jorels_pos`, que agrega
`pos_electronic_invoice_journal_id` e `invoice_type` a los ajustes del POS.
Jorels 19 (`b89e2ac`) quitó la vista y los dos campos, y trae otra con otro
xmlid. Al validar esa vista nueva en el upgrade, Odoo 19 arma el formulario con
todas las vistas hijas de los módulos ya cargados, la vieja incluida, y el
upgrade se cae con "El campo `pos_electronic_invoice_journal_id` no existe"
(build de staging 41322505, 2026-11-05).

Odoo 19 carga por (fase, profundidad, nombre) (`odoo/modules/module_graph.py`).
`telegram_alerts` depende solo de `base` y `product`, y `point_of_sale` depende
de `stock_account` -> `stock` -> `product`: este módulo siempre carga antes que
`l10n_co_edi_jorels_pos`.

Se desactiva en vez de borrarla, igual que `account_payment_dispersion`:
`_process_end` la elimina al terminar el upgrade porque ningún XML declara ya su
xmlid. Idempotente: si la vista no está o ya está inactiva, no toca nada.
"""
import logging

_logger = logging.getLogger(__name__)

JORELS_POS_ORPHAN_VIEWS = (
    ('l10n_co_edi_jorels_pos', 'res_config_settings_view_form_l10n_co_edi_jorels_pos'),
    # POS-INVENTORY-QUEUE-VIEWS-0001 (auditoría 2026-11-13): pos_inventory_queue 17.0.1.2.1 (instalado en prod desde
    # ~2026-11-10) declaraba esta vista sobre point_of_sale.res_config_settings_view_form con el campo
    # res.config.settings.pos_inventory_queue_enabled. En 19.0.1.2.0 el campo pasó a pos.inventory.queue.config y
    # views/res_config_settings_views.xml salió del manifiesto: la vista queda huérfana con un campo inexistente,
    # el mismo caso que tumbó el build 41322505. Nunca se ensayó porque staging no tenía el módulo.
    ('pos_inventory_queue', 'res_config_settings_view_form_pos_inventory_queue'),
)


def migrate(cr, version):
    if not version:
        return
    for module, name in JORELS_POS_ORPHAN_VIEWS:
        cr.execute(
            """
            UPDATE ir_ui_view v
               SET active = false
              FROM ir_model_data d
             WHERE d.model = 'ir.ui.view'
               AND d.module = %s
               AND d.name = %s
               AND v.id = d.res_id
               AND v.active
            """,
            (module, name),
        )
        _logger.info(
            "telegram_alerts 19.0.1.0.0 pre-migrate: %s vista(s) huérfana(s) %s.%s desactivada(s)",
            cr.rowcount, module, name,
        )
