# -*- coding: utf-8 -*-
"""Renombra `type_of_account` → `co_account_type` en las vistas de Studio.

En 17, Studio agregó la columna «Tipo de cuenta» a la lista de cuentas
bancarias (vista 5868 "Odoo Studio: res.partner.bank.tree customization",
xmlid `studio_customization.*`, hereda `base.view_partner_bank_tree`). Esa vista
no es de este módulo, así que la limpieza de 19.0.1.0.4 no la toca y el upgrade
no la valida: queda activa apuntando a un campo que en 19 ya no existe.

Efecto en 19: toda pantalla que carga la lista de cuentas bancarias falla en el
navegador con `"res.partner.bank"."type_of_account" field is undefined`. El
caso visible es el POS: Crear o Editar un cliente abre el formulario de
contacto y el POS se cae con «¡Vaya!» (evidencias PM9 y PM9b).

Se renombra el campo en el arch (la columna sigue mostrando el tipo de cuenta,
ahora desde `co_account_type`, al que 19.0.1.0.4 ya copió los datos) en vez de
borrar la vista, para no perder la personalización.

Alcance: vistas de `res.partner.bank` que NO son de este módulo (las propias se
recargan desde el XML). Solo `ir_ui_view`, ninguna tabla de negocio.
Idempotente: después de correr ya no hay vistas que contengan el nombre viejo.
"""
import logging

_logger = logging.getLogger(__name__)

OLD_FIELD = 'type_of_account'
NEW_FIELD = 'co_account_type'


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT v.id, v.name
          FROM ir_ui_view v
         WHERE v.model = 'res.partner.bank'
           AND v.arch_db::text LIKE %s
           AND NOT EXISTS (
                SELECT 1 FROM ir_model_data d
                 WHERE d.model = 'ir.ui.view'
                   AND d.res_id = v.id
                   AND d.module = 'account_payment_dispersion')
        """,
        ('%' + OLD_FIELD + '%',),
    )
    views = cr.fetchall()
    _logger.info(
        "account_payment_dispersion 19.0.1.0.5 post-migrate: %s vistas de "
        "res.partner.bank (Studio u otras) con %s antes del cambio",
        len(views), OLD_FIELD,
    )
    if not views:
        return
    # arch_db es jsonb (un arch por idioma): se reemplaza en todas las traducciones.
    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = replace(arch_db::text, %s, %s)::jsonb
         WHERE id IN %s
        """,
        (OLD_FIELD, NEW_FIELD, tuple(vid for vid, _name in views)),
    )
    for vid, name in views:
        _logger.info(
            "account_payment_dispersion 19.0.1.0.5 post-migrate: vista %s "
            "(%s): %s -> %s", vid, name, OLD_FIELD, NEW_FIELD,
        )
    cr.execute(
        """
        SELECT count(*) FROM ir_ui_view
         WHERE model = 'res.partner.bank' AND arch_db::text LIKE %s
        """,
        ('%' + OLD_FIELD + '%',),
    )
    _logger.info(
        "account_payment_dispersion 19.0.1.0.5 post-migrate: vistas de "
        "res.partner.bank que aún mencionan %s después del cambio: %s "
        "(se espera 0)", OLD_FIELD, cr.fetchone()[0],
    )
