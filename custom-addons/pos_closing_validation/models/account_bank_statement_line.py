from odoo import fields, models


class AccountBankStatementLine(models.Model):
    """Flag statement lines created as POS Cash In/Out movements."""

    _inherit = "account.bank.statement.line"

    pos_cash_move = fields.Boolean(
        string="Pos Cash In/Out",
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help="Indica si esta línea de estado de cuenta fue creada como un movimiento de efectivo en el punto de venta.",
    )
    pos_cash_move_uuid = fields.Char(
        string="Pos Cash In/Out Ref",
        readonly=True,
        copy=False,
        help="Identificador generado por el cliente de la solicitud de Entrada/Salida de efectivo. El "
            "Punto de Venta reintenta un movimiento en cola con el mismo valor cuando "
            "se pierde la conexión, de modo que el reintento pueda reconocerse e ignorarse "
            "en lugar de registrar un segundo movimiento.",
    )

    _pos_cash_move_uuid_uniq = models.Constraint(
        "unique(pos_session_id, pos_cash_move_uuid)",
        "Este movimiento de efectivo ya ha sido registrado.",
    )
