# Copyright 2026 Libertario Coffee Roasters
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html)
import logging

_logger = logging.getLogger(__name__)

TERMINAL_SWITCHES = (
    # column that marked the method as Credibanco, old to newest
    "enable_pos_credibanco",
)


def _column(cr, table, column):
    cr.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone()


# 17 settings view that shows ``module_pos_credibanco``; 19 has neither of them
ORPHAN_SETTINGS_VIEW = "res_config_settings_view_credibanco_inherit"


def _deactivate_orphan_settings_view(cr):
    """Turn off the 17 settings view before this module's data is loaded.

    While it stays active, Odoo 19 adds it to the POS settings form of every
    module validated afterwards, and the upgrade stops with "El campo
    `module_pos_credibanco` no existe".  ``_process_end`` deletes it at the end
    of the upgrade because no XML declares its xmlid any more.
    """
    cr.execute(
        """
        UPDATE ir_ui_view v
           SET active = false
          FROM ir_model_data d
         WHERE d.model = 'ir.ui.view'
           AND d.module = 'pos_api_credibanco'
           AND d.name = %s
           AND v.id = d.res_id
           AND v.active
        """,
        (ORPHAN_SETTINGS_VIEW,),
    )
    _logger.info(
        "pos_api_credibanco 19.0.1.0.0 pre-migration: %s orphan settings view(s) deactivated",
        cr.rowcount,
    )


def migrate(cr, version):
    """Move the old per-method flag onto Odoo 19's terminal selection.

    ``enable_pos_credibanco`` was the switch before this module used the core
    payment-terminal framework.  It is read with SQL because the field is gone
    from the model once the new code is loaded, and the column does not exist on
    a fresh install.

    ``use_payment_terminal`` must be a text/selection column: in older major
    versions it was a boolean, and writing 'credibanco' there would abort the
    whole upgrade, so the mapping is skipped when the types do not match.
    """
    if not version:
        return
    _deactivate_orphan_settings_view(cr)

    if not _column(cr, "pos_payment_method", "enable_pos_credibanco"):
        return
    terminal_type = _column(cr, "pos_payment_method", "use_payment_terminal")
    if not terminal_type or "char" not in terminal_type[0]:
        return

    # payment_method_type only exists from Odoo 17 on; building the SET clause
    # from the columns that are actually there keeps the upgrade from aborting.
    extra_set = ""
    if _column(cr, "pos_payment_method", "payment_method_type"):
        extra_set = ", payment_method_type = 'terminal'"

    for switch in TERMINAL_SWITCHES:
        cr.execute(
            f"""
            UPDATE pos_payment_method
               SET use_payment_terminal = 'credibanco'{extra_set}
             WHERE {switch} IS TRUE
               AND (use_payment_terminal IS NULL OR use_payment_terminal = '')
            """
        )
