import re
import unicodedata

from odoo import api, fields, models


def _slugify(text):
    """Convierte texto a snake_case sin tildes ni caracteres especiales."""
    text = unicodedata.normalize('NFD', text or '')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


class PosPaymentRestrictionField(models.Model):
    """Campo configurable del popup de restricción de pago."""
    _name = 'pos.payment.restriction.field'
    _description = 'Campo del popup de restricción de pago POS'
    _order = 'restriction_id, sequence, id'

    restriction_id = fields.Many2one(
        comodel_name='pos.payment.customer.restriction',
        string='Restricción',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Etiqueta', required=True)
    field_key = fields.Char(
        string='Clave',
        compute='_compute_field_key',
        store=True,
        help='Identificador técnico usado para almacenar el valor en la orden.',
    )
    field_type = fields.Selection(
        selection=[
            ('char', 'Texto corto'),
            ('text', 'Texto largo'),
            ('integer', 'Número entero'),
        ],
        string='Tipo',
        default='char',
        required=True,
    )
    required = fields.Boolean(string='Requerido', default=False)

    @api.depends('name')
    def _compute_field_key(self):
        for rec in self:
            rec.field_key = _slugify(rec.name) if rec.name else ''
