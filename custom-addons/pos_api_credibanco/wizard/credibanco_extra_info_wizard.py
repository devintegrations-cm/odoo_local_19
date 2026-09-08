from odoo import fields, models

from ..models.pos_payment_credibanco import _load_field_labels


def _field_options():
    """Concept options for the manual-completion wizard."""
    return [(label, label) for label in _load_field_labels().values()]


class CredibancoExtraInfoWizard(models.TransientModel):
    _name = "credibanco.extra.info.wizard"
    _description = "Agregar información extra del pago entregada por el datáfono"

    payment_order_id = fields.Many2one(
        "pos.payment",
        string="Pago",
        required=True,
        ondelete="cascade",
    )
    credibancoExtraField = fields.Selection(
        selection=_field_options,
        string="Concepto",
        required=True,
    )
    credibancoExtraValue = fields.Char(string="Valor", required=True)

    def action_confirm(self):
        for wizard in self:
            wizard.payment_order_id.write({
                "credibanco_extra_info": [(0, 0, {
                    "credibancoField": wizard.credibancoExtraField,
                    "credibancoValue": wizard.credibancoExtraValue,
                })]
            })
        return {"type": "ir.actions.act_window_close"}
