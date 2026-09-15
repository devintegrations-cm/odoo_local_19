from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Solo lectura: la edición real ocurre en el formulario de `pos.config` o en la
    # acción `action_open_pos_custom_receipt_blocks`. Un One2many `related` editable
    # en `res.config.settings` es frágil al guardar, por eso aquí solo informamos.
    pos_custom_receipt_block_count = fields.Integer(
        string='Bloques configurados',
        compute='_compute_pos_custom_receipt_block_count',
    )

    @api.depends('pos_config_id')
    def _compute_pos_custom_receipt_block_count(self):
        for settings in self:
            settings.pos_custom_receipt_block_count = self.env['pos.receipt.custom.block'].search_count(
                [('config_id', '=', settings.pos_config_id.id)]
            ) if settings.pos_config_id else 0

    def action_open_pos_custom_receipt_blocks(self):
        self.ensure_one()
        return self.pos_config_id.action_open_custom_receipt_blocks()
