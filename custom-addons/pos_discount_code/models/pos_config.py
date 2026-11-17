from odoo import api, fields, models
from .pos_order import NUMERIC_DOC_TYPES


class PosConfig(models.Model):
    _inherit = "pos.config"

    show_discount_code_button = fields.Boolean(
        string="Mostrar botón de código de descuento",
        default=True,
        help="Muestra un botón en la pantalla del POS para capturar tipo de "
             "documento, número de documento y código de descuento (bono).",
    )

    @api.model
    def _load_pos_data_read(self, records, config):
        """Envía al POS los tipos de documento del canje.

        La lista vive en un solo lugar: el Selection de
        ``pos.order.discount_doc_type`` (``DISCOUNT_DOC_TYPES`` en
        pos_order.py). Odoo 19 no envía las opciones de los Selection al POS,
        así que se agregan al registro de la configuración; el popup las lee
        de ``pos.config._discount_doc_types``."""
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            field = self.env["pos.order"]._fields["discount_doc_type"]
            read_records[0]["_discount_doc_types"] = [
                {"value": value, "label": label, "numeric": value in NUMERIC_DOC_TYPES}
                for value, label in field._description_selection(self.env)
            ]
        return read_records


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_show_discount_code_button = fields.Boolean(
        related="pos_config_id.show_discount_code_button",
        readonly=False,
        string="Mostrar botón de código de descuento",
        help="Muestra un botón en la pantalla del POS para capturar tipo de "
             "documento, número de documento y código de descuento (bono).",
    )
