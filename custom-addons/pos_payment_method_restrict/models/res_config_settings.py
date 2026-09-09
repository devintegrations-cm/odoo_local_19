from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_payment_restrict_enabled = fields.Boolean(
        related='pos_config_id.payment_restrict_enabled',
        readonly=False,
    )
    pos_payment_customer_restriction_ids = fields.One2many(
        related='pos_config_id.payment_customer_restriction_ids',
        readonly=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        # La optimización de res.config.settings.create() compara IDs de la
        # One2many y puede descartar la escritura cuando los IDs de restricción
        # no cambian, perdiendo cambios anidados en restriction_field_ids.
        # Extraemos los comandos antes del super() y los aplicamos directamente
        # sobre pos.config para garantizar que siempre se persistan.
        restriction_cmds_list = [
            vals.pop('pos_payment_customer_restriction_ids', None)
            for vals in vals_list
        ]
        result = super().create(vals_list)
        for record, cmds in zip(result, restriction_cmds_list):
            if cmds is not None and record.pos_config_id:
                record.pos_config_id.write({
                    'payment_customer_restriction_ids': cmds,
                })
        return result
