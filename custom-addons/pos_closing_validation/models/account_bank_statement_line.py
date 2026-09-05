from odoo import fields, models


class AccountBankStatementLine(models.Model):
    """Flag statement lines created as POS Cash In/Out movements."""

    _inherit = "account.bank.statement.line"

    pos_cash_move = fields.Boolean(
        string="POS Cash In/Out",
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help="Indicates that this statement line was created as a POS Cash In/Out movement.",
    )
    pos_cash_move_uuid = fields.Char(
        string="POS Cash In/Out Ref",
        readonly=True,
        copy=False,
        help="Client-generated identifier of the Cash In/Out request.  The "
             "Point of Sale retries a queued movement with the same value when "
             "the connection drops, so the retry can be recognised and ignored "
             "instead of writing a second movement.",
    )

    _pos_cash_move_uuid_uniq = models.Constraint(
        "unique(pos_session_id, pos_cash_move_uuid)",
        "This cash movement has already been registered.",
    )
