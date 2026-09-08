import json

from odoo import fields, models, tools

# Positions in the terminal answer that the flow depends on.
APPROVAL_CODE_POSITION = "1"
TRANSACTION_ID_POSITION = "2"

_DATA_FILE = "pos_api_credibanco/static/data/fields_credibanco.json"
_FIELD_LABELS = None


def _load_field_labels():
    """Position -> label of every field the terminal can answer with.

    Cached per process on purpose: the file ships with the code, so it only
    changes on upgrade (which restarts the workers).
    """
    global _FIELD_LABELS
    if _FIELD_LABELS is None:
        # Binary on purpose: json decodes UTF-8 itself, while file_open has no
        # encoding argument and would otherwise depend on the worker's locale.
        with tools.file_open(_DATA_FILE, "rb") as handle:
            _FIELD_LABELS = json.load(handle)
    return _FIELD_LABELS


class PosPaymentCredibanco(models.Model):
    _name = "pos.payment.credibanco"
    _description = "Información extra de pago brindada por el datafono"
    _order = "sequence, id"

    payment_order_id = fields.Many2one(
        "pos.payment",
        string="Pago",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=100)
    credibancoField = fields.Char(string="Concepto")
    credibancoValue = fields.Char(string="Valor")

    def _field_labels(self):
        return _load_field_labels()

    def _rows_from_answer(self, answer):
        """Build the readable breakdown rows out of a terminal answer.

        ``answer`` maps protocol positions to values. Positions without a
        documented label are skipped on purpose: the terminal answers with a
        variable set of fields, and an undocumented position must not break the
        payment synchronisation.
        """
        labels = self._field_labels()
        rows = []
        for position in answer:
            label = labels.get(str(position))
            if not label:
                continue
            sequence = int(position) if str(position).isdigit() else 100
            value = answer[position]
            rows.append((0, 0, {
                "credibancoField": label,
                "credibancoValue": "" if value is None else str(value),
                "sequence": sequence,
            }))
        return rows
