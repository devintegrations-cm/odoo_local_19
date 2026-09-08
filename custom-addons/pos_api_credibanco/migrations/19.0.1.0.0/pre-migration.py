# Copyright 2026 Libertario Coffee Roasters
# License LGPL-3 (https://www.gnu.org/licenses/lgpl-3.0.html)

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
