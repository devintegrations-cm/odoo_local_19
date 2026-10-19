from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Los campos de pos.config viajan al frontend sin declarar nada: el modelo
    # no define `_load_pos_data_fields`, el mixin pasa `[]` y `read([])` lee
    # todos los campos (odoo/orm/models.py). Mismo camino que los flags de
    # pos_obligatory_invoice y pos_dian_client, ya probados en este entorno.
    comanda_padding_top = fields.Integer(
        string='Espacio superior (px)',
        default=0,
        help='Espacio en blanco arriba de la comanda, en píxeles (0 a 100).',
    )
    comanda_padding_bottom = fields.Integer(
        string='Espacio inferior (px)',
        default=0,
        help='Espacio en blanco al final del cuerpo de la comanda, en píxeles (0 a 100).',
    )
    comanda_show_employee = fields.Boolean(
        string='Mostrar empleado',
        default=True,
        help='Imprime la línea "Atendido por: ..." con el empleado o cajero del pedido.',
    )
    comanda_show_reference = fields.Boolean(
        string='Mostrar número de pedido',
        default=True,
        help='Imprime la línea "Pedido # N" con el número de seguimiento. '
             'La referencia grande (con piso y mesa en restaurante) se '
             'imprime siempre.',
    )
    comanda_spanish_labels = fields.Boolean(
        string='Etiquetas en español',
        default=True,
        help='Imprime las etiquetas fijas de la comanda en español: Pedido, '
             'Atendido por:, NOTA INTERNA, NOTA DEL CLIENTE, (DUPLICADO !). '
             'Desmarcado, se usa el texto de Odoo en el idioma del usuario.',
    )

    @api.constrains('comanda_padding_top', 'comanda_padding_bottom')
    def _check_comanda_padding(self):
        for config in self:
            if not 0 <= config.comanda_padding_top <= 100:
                raise ValidationError(_('El espacio superior de la comanda debe estar entre 0 y 100 px.'))
            if not 0 <= config.comanda_padding_bottom <= 100:
                raise ValidationError(_('El espacio inferior de la comanda debe estar entre 0 y 100 px.'))
