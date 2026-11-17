from odoo import fields, models

from ..models.pos_payment_credibanco import _load_field_labels


def _field_options(model):
    """Concept options for the manual-completion wizard.

    Odoo calls a callable ``selection`` with the model as its only argument
    (``odoo.orm.fields.determine``), so the signature must accept it even
    though the options do not depend on it.  Without it the wizard cannot even
    be opened: ``TypeError: _field_options() takes 0 positional arguments``.
    """
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
