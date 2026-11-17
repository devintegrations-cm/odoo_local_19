import logging

from psycopg2 import sql

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

# the national id columns of versions before 2.0.0: the cardholder's and the receipt issuer's
NATIONAL_ID_COLUMNS = (
    ("clara_transaction", ("cardholder_vat", "receipt_issuer_vat")),
)


def migrate(cr, version):
    """Drops the national id columns that earlier versions kept on the transactions. Only those columns: no other
    column and no other table is touched. Odoo drops the columns of removed fields at the end of an update; this
    makes sure of it on any database, whatever version it comes from."""
    for table, columns in NATIONAL_ID_COLUMNS:
        present = [column for column in columns if column_exists(cr, table, column)]
        if not present:
            continue
        cr.execute(sql.SQL("ALTER TABLE {} {}").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.SQL("DROP COLUMN IF EXISTS {}").format(sql.Identifier(column)) for column in present)))
        _logger.info("Clara: dropped %s from %s", ", ".join(present), table)
