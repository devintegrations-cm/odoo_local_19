from odoo import _, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    custom_receipt_block_ids = fields.One2many(
        'pos.receipt.custom.block',
        'config_id',
        string='Bloques del ticket',
        copy=True,
        help='Bloques de información adicional que se imprimen en el ticket de este punto de venta.',
    )

    def action_open_custom_receipt_blocks(self):
        """Abre la lista de bloques del punto de venta actual.

        Se usa desde Ajustes → Punto de Venta, donde no editamos el One2many
        directamente (los One2many `related` en `res.config.settings` son frágiles
        al guardar); en su lugar navegamos al modelo hijo ya filtrado.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ticket – Información adicional: %s', self.name),
            'res_model': 'pos.receipt.custom.block',
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
            'context': {
                'default_config_id': self.id,
                'active_test': False,
            },
        }
