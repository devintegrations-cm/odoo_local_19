from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    payment_restrict_enabled = fields.Boolean(
        string='Activar restricciones por cliente',
        default=False,
    )
    payment_customer_restriction_ids = fields.One2many(
        comodel_name='pos.payment.customer.restriction',
        inverse_name='config_id',
        string='Restricciones de métodos de pago',
    )

    @api.model
    def _load_pos_data_read(self, records, config):
        """Inyecta el dict plano de restricciones en el config que llega al POS.

        Odoo 19 eliminó `pos.session._get_pos_ui_pos_config` (Odoo 17): la
        carga al frontend se declara ahora en el modelo dueño del campo.
        `pos.config` no define `_load_pos_data_fields`, así que el mixin lee
        todos los campos; `payment_restrict_enabled` y
        `payment_customer_restriction_ids` viajan solos como campos reales.

        El dict con los detalles de cada restricción se expone en
        `this.pos.config._payment_restrictions`: la clave con prefijo `_` hace
        que el store JS cree un getter automático (patrón de `_server_version` /
        `_base_url` del core, ver related_models/index.js `_sanitizeRawData`).
        """
        read_records = super()._load_pos_data_read(records, config)
        if not read_records:
            return read_records

        restrictions = {}
        for line in records.payment_customer_restriction_ids:
            restrictions[line.payment_method_id.id] = {
                'restriction_db_id': line.id,
                'partner_ids': line.partner_ids.ids,
                'create_delivery': line.create_delivery,
                'to_invoice': line.to_invoice,
                'to_ei_invoice': line.to_ei_invoice,
                'fields': [
                    {
                        'key': f.field_key or str(f.id),
                        'name': f.name,
                        'type': f.field_type,
                        'required': f.required,
                    }
                    for f in line.restriction_field_ids
                ],
            }

        read_records[0]['_payment_restrictions'] = restrictions
        return read_records