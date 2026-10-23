# -*- coding: utf-8 -*-
"""Copia el tipo de cuenta de la versión 17 al campo rediseñado de la 19.

19.0.1.0.4 renombra de facto `res.partner.bank.type_of_account` (17) a
`co_account_type` (19 rediseñado) sin script de migración. Sin este pre-migrate
las 1.627 cuentas de terceros quedarían sin tipo al hacer el upgrade y la
validación del módulo bloquearía todos los lotes con "Cuentas Bancarias sin
Tipo".

Claves compartidas: `savings_account` y `current_account` se copian 1 a 1.
`no_account`, `payroll_account` y vacío quedan NULL: el selection nuevo no los
admite (en producción solo hay 1 cuenta `no_account`, sin uso en 12 meses, y 1
vacía; ambas quedan para el saneo manual de datos).

Idempotente: solo escribe donde `co_account_type` esté vacío y solo si la
columna vieja existe (bases ya rediseñadas no tocan nada).

También desactiva la vista de contactos de la v17
(`account_payment_dispersion_inherit_view_partner_property_form`), que agrega
`type_of_account` al formulario de contactos y ya no está en el XML de la 19.
Mientras siga activa, cualquier módulo que se actualice después y herede ese
formulario falla con "Field type_of_account does not exist". Se desactiva en
vez de borrarla: no hay conflicto con vistas hijas (`inherit_id` es
ondelete='restrict') y `_process_end` la elimina al terminar el upgrade porque
su xmlid ya no se carga. El form de cuentas bancarias NO se toca: el XML nuevo
declara el mismo xmlid y le reemplaza el arch.

Regla del proyecto: todo renombre deja conteos de antes y después en el log.
"""
import logging

_logger = logging.getLogger(__name__)

ORPHAN_PARTNER_VIEW = 'account_payment_dispersion_inherit_view_partner_property_form'


def _deactivate_orphan_partner_view(cr):
    """Desactiva la vista de contactos de la v17 (referencia type_of_account)."""
    cr.execute(
        """
        UPDATE ir_ui_view v
           SET active = false
          FROM ir_model_data d
         WHERE d.model = 'ir.ui.view'
           AND d.module = 'account_payment_dispersion'
           AND d.name = %s
           AND v.id = d.res_id
           AND v.active
        """,
        (ORPHAN_PARTNER_VIEW,),
    )
    _logger.info(
        "account_payment_dispersion 19.0.1.0.4 pre-migrate: %s vista de "
        "contactos huérfana desactivada", cr.rowcount,
    )


def migrate(cr, version):
    if not version:
        # Instalación limpia: no hay columna vieja que copiar.
        return
    _deactivate_orphan_partner_view(cr)
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'res_partner_bank'
           AND column_name = 'type_of_account'
        """
    )
    if not cr.fetchone():
        return
    # La columna nueva puede no existir todavía: este script corre ANTES de que
    # el ORM registre el campo. Si ya existe (base ya rediseñada), no se toca.
    cr.execute(
        """
        ALTER TABLE res_partner_bank
            ADD COLUMN IF NOT EXISTS co_account_type varchar
        """
    )
    # Conteo antes: filas copiables (savings/current sin tipo nuevo).
    cr.execute(
        """
        SELECT count(*) FROM res_partner_bank
         WHERE co_account_type IS NULL
           AND type_of_account IN ('savings_account', 'current_account')
        """
    )
    to_copy = cr.fetchone()[0]
    cr.execute(
        """
        UPDATE res_partner_bank
           SET co_account_type = type_of_account
         WHERE co_account_type IS NULL
           AND type_of_account IN ('savings_account', 'current_account')
        """
    )
    copied = cr.rowcount
    # Conteo después: quedan sin tipo nuevo solo valores no admitidos por el
    # selection nuevo (no_account, payroll_account, vacío) — en producción: la
    # cuenta 5221 y la 5424 si tesorería no definió su tipo.
    cr.execute(
        """
        SELECT count(*) FROM res_partner_bank
         WHERE type_of_account IS NOT NULL AND co_account_type IS NULL
        """
    )
    skipped = cr.fetchone()[0]
    _logger.info(
        "account_payment_dispersion 19.0.1.0.4 pre-migrate: %s cuentas "
        "candidatas, %s copiadas a co_account_type, %s con tipo antiguo "
        "no admitido en el selection nuevo (quedan NULL)",
        to_copy, copied, skipped,
    )
