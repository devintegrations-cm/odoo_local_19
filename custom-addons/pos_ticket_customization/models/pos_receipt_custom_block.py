from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.barcode import check_barcode_encoding

# Tipos de bloque que necesitan `content` obligatoriamente para poder renderizarse.
CONTENT_REQUIRED_TYPES = ('text', 'legal_text', 'url_qr', 'qr_text', 'barcode', 'review_qr', 'payment_qr')

# Tipos que no dibujan ninguna imagen y por tanto no usan ancho ni alto.
SIZELESS_TYPES = ('separator', 'text', 'legal_text')

# Lado máximo admitido para un código o una imagen del ticket, en píxeles.
#
# `ir.actions.report.barcode()` rechaza `ancho * alto > 1_200_000` o cualquier lado
# mayor de 10_000 con un `ValueError`, que el endpoint `/report/barcode` traduce a
# una respuesta HTTP 200 con cuerpo HTML: el `<img>` del ticket sale roto y sin
# ningún error visible en el log. Con 1000 se respetan ambos límites del core
# (1000 * 1000 = 1_000_000) y sobra margen: el ticket se rasteriza a 512 px de
# ancho, así que nada por encima de eso aporta resolución real.
MAX_CODE_SIDE = 1000

# Campos que se envían al frontend del POS. Se declara aquí (y no en pos_session)
# para que el modelo sea la única fuente de verdad de su propio contrato con el POS.
POS_LOADED_FIELDS = [
    'sequence', 'block_type', 'position', 'alignment', 'label', 'content',
    'barcode_type', 'barcode_width', 'barcode_height', 'barcode_humanreadable',
    'image', 'date_start', 'date_stop', 'min_amount', 'frequency', 'frequency_offset',
    'wa_number', 'wa_message',
    'wifi_ssid', 'wifi_password', 'wifi_security', 'wifi_hidden',
    'vcard_name', 'vcard_org', 'vcard_phone', 'vcard_email', 'vcard_website', 'vcard_address',
]


class PosReceiptCustomBlock(models.Model):
    _name = 'pos.receipt.custom.block'
    _inherit = ['pos.load.mixin']
    _description = 'Bloque de información adicional del ticket del POS'
    _order = 'config_id, sequence, id'

    @api.model
    def _load_pos_data_domain(self, data, config):
        # Solo los bloques activos del punto de venta de esta sesión: cada tienda
        # carga exclusivamente su propia configuración.
        return [('config_id', '=', config.id), ('active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config):
        return POS_LOADED_FIELDS

    config_id = fields.Many2one(
        'pos.config',
        string='Punto de venta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='config_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)

    block_type = fields.Selection(
        selection=[
            ('text', 'Texto libre'),
            ('legal_text', 'Texto legal'),
            ('separator', 'Separador'),
            ('image', 'Imagen'),
            ('url_qr', 'QR de URL'),
            ('qr_text', 'QR de texto'),
            ('barcode', 'Código de barras'),
            ('review_qr', 'QR de reseña en Google'),
            ('whatsapp_qr', 'QR de WhatsApp'),
            ('wifi_qr', 'QR de WiFi'),
            ('vcard_qr', 'QR de contacto (vCard)'),
            ('payment_qr', 'QR de pago / propina'),
        ],
        string='Tipo',
        required=True,
        default='text',
    )
    position = fields.Selection(
        selection=[
            ('header', 'Cabecera'),
            ('before_footer', 'Antes del pie'),
            ('footer', 'Final del ticket'),
        ],
        string='Posición',
        required=True,
        default='before_footer',
    )
    alignment = fields.Selection(
        selection=[
            ('left', 'Izquierda'),
            ('center', 'Centro'),
            ('right', 'Derecha'),
        ],
        string='Alineación',
        required=True,
        default='center',
    )

    label = fields.Char(string='Leyenda', translate=True, help='Texto opcional que acompaña al bloque, p. ej. "Escanea para tu factura".')
    content = fields.Text(
        string='Contenido',
        help='Contenido según el tipo: el texto a imprimir, la URL, o el valor del código de barras.\n'
             'Admite marcadores dinámicos: {order_name}, {total}, {date}, {cashier}, {table}, '
             '{partner_name}, {tracking_number}, {store_name}.',
    )

    # --- Códigos de barras / QR -------------------------------------------------
    # OJO: los valores son nombres de widget de ReportLab, que es lo que espera
    # `ir.actions.report.barcode()`. "Code39" e "ITF" NO son nombres válidos: sus
    # equivalentes reales son "Standard39" e "I2of5". Con un nombre inválido
    # ReportLab lanza `KeyError`, que `barcode()` no captura (solo atrapa
    # ValueError/AttributeError), así que el endpoint responde 500 y el ticket
    # sale con la imagen rota.
    barcode_type = fields.Selection(
        selection=[
            ('Code128', 'Code 128'),
            ('Standard39', 'Code 39'),
            ('Extended39', 'Code 39 extendido'),
            ('Standard93', 'Code 93'),
            ('EAN13', 'EAN-13'),
            ('EAN8', 'EAN-8'),
            ('UPCA', 'UPC-A'),
            ('I2of5', 'ITF (2 de 5 intercalado)'),
            ('Codabar', 'Codabar'),
        ],
        string='Simbología',
        default='Code128',
    )
    barcode_width = fields.Integer(string='Ancho (px)', default=150)
    barcode_height = fields.Integer(
        string='Alto (px)',
        default=150,
        help='Solo se usa para elegir la proporción con la que el servidor genera el '
             'código. Al imprimir manda el ancho: el alto se ajusta solo para no '
             'deformar la imagen.',
    )
    barcode_humanreadable = fields.Boolean(
        string='Mostrar valor',
        help='Imprime el valor legible debajo de las barras. No aplica a los códigos QR.',
    )

    # `Image` en vez de `Binary`: recorta al escribir. El binario viaja entero en la
    # carga de CADA sesión de POS, así que un logo de 2 MB se pagaría en cada apertura
    # de caja; y por encima de 512 px no se gana nada, que es el ancho al que se
    # rasteriza el ticket.
    image = fields.Image(
        string='Imagen',
        max_width=512,
        max_height=512,
        attachment=True,
    )

    # --- Filtros de aplicación --------------------------------------------------
    date_start = fields.Date(string='Vigente desde', help='Vacío = sin límite inferior.')
    date_stop = fields.Date(string='Vigente hasta', help='Vacío = sin límite superior.')
    min_amount = fields.Float(
        string='Importe mínimo',
        digits='Product Price',
        help='Imprimir solo si el total del pedido (con impuestos) es mayor o igual a este valor. 0 = sin mínimo.',
    )
    frequency = fields.Integer(
        string='Cada N pedidos',
        default=1,
        required=True,
        help='1 = en todos los pedidos. 10 = en uno de cada diez.\n'
             'Se cuenta con el número de pedido dentro de la sesión de caja, que se '
             'reinicia al abrir caja: con 10, sale en los pedidos 10, 20, 30... del turno.',
    )
    frequency_offset = fields.Integer(
        string='Desplazamiento',
        default=0,
        help='Desplaza en qué pedido del ciclo aparece. Con "Cada N pedidos" = 10 y '
             'desplazamiento 1, sale en los pedidos 1, 11, 21... en vez de 10, 20, 30...\n'
             'Sirve para repartir varios bloques y que no caigan todos en el mismo ticket.',
    )

    # --- Campos específicos por tipo -------------------------------------------
    wa_number = fields.Char(string='Número de WhatsApp', help='En formato internacional sin "+" ni espacios, p. ej. 573001234567.')
    wa_message = fields.Char(string='Mensaje de WhatsApp', translate=True, help='Mensaje prellenado. Admite marcadores dinámicos.')

    wifi_ssid = fields.Char(string='SSID')
    wifi_password = fields.Char(string='Contraseña WiFi')
    wifi_security = fields.Selection(
        selection=[('WPA', 'WPA/WPA2'), ('WEP', 'WEP'), ('nopass', 'Abierta')],
        string='Seguridad',
        default='WPA',
    )
    wifi_hidden = fields.Boolean(string='Red oculta')

    vcard_name = fields.Char(string='Nombre (vCard)')
    vcard_org = fields.Char(string='Organización (vCard)')
    vcard_phone = fields.Char(string='Teléfono (vCard)')
    vcard_email = fields.Char(string='Correo (vCard)')
    vcard_website = fields.Char(string='Sitio web (vCard)')
    vcard_address = fields.Char(string='Dirección (vCard)')

    # ---------------------------------------------------------------- overrides
    @api.depends('block_type', 'label', 'content')
    def _compute_display_name(self):
        types = dict(self._fields['block_type']._description_selection(self.env))
        for block in self:
            title = block.label or (block.content or '').strip().split('\n')[0]
            type_label = types.get(block.block_type, '')
            block.display_name = '%s: %s' % (type_label, title[:40]) if title else type_label

    @api.onchange('block_type')
    def _onchange_block_type(self):
        """Ajusta el tamaño por defecto: los QR son cuadrados, los lineales apaisados."""
        for block in self:
            if block.block_type == 'barcode':
                block.barcode_width = 300
                block.barcode_height = 60
            else:
                block.barcode_width = 150
                block.barcode_height = 150

    # ------------------------------------------------------------- constraints
    @api.constrains('block_type', 'content', 'image', 'wa_number', 'wifi_ssid', 'vcard_name')
    def _check_required_content(self):
        for block in self:
            if block.block_type in CONTENT_REQUIRED_TYPES and not (block.content or '').strip():
                raise ValidationError(_('El bloque "%s" requiere un contenido.', block.display_name))
            if block.block_type == 'image' and not block.image:
                raise ValidationError(_('El bloque de tipo Imagen requiere una imagen.'))
            if block.block_type == 'whatsapp_qr' and not (block.wa_number or '').strip():
                raise ValidationError(_('El bloque de WhatsApp requiere un número.'))
            if block.block_type == 'wifi_qr' and not (block.wifi_ssid or '').strip():
                raise ValidationError(_('El bloque de WiFi requiere un SSID.'))
            if block.block_type == 'vcard_qr' and not (block.vcard_name or '').strip():
                raise ValidationError(_('El bloque de vCard requiere un nombre de contacto.'))

    @api.constrains('block_type', 'barcode_type', 'content')
    def _check_barcode_encoding(self):
        """EAN/UPC solo aceptan longitudes y dígito de control concretos.

        Si el valor no cumple, `ir.actions.report.barcode()` degrada silenciosamente
        a Code128 y se imprime un código distinto al configurado. Preferimos avisar
        al configurar. Se omite la validación si el valor lleva marcadores dinámicos,
        porque su valor real solo se conoce en el momento de imprimir.
        """
        for block in self:
            if block.block_type != 'barcode' or block.barcode_type not in ('EAN8', 'EAN13'):
                continue
            value = (block.content or '').strip()
            if not value or '{' in value:
                continue
            if not check_barcode_encoding(value, block.barcode_type):
                raise ValidationError(_(
                    'El valor "%(value)s" no es un %(type)s válido (longitud o dígito de control incorrectos).',
                    value=value, type=block.barcode_type,
                ))

    @api.constrains('date_start', 'date_stop')
    def _check_dates(self):
        for block in self:
            if block.date_start and block.date_stop and block.date_start > block.date_stop:
                raise ValidationError(_('La fecha "Vigente desde" no puede ser posterior a "Vigente hasta".'))

    @api.constrains('frequency', 'frequency_offset')
    def _check_frequency(self):
        for block in self:
            if block.frequency < 1:
                raise ValidationError(_('"Cada N pedidos" debe ser 1 o mayor (1 = en todos los pedidos).'))
            # Un desplazamiento fuera del ciclo es equivalente a otro dentro de él,
            # pero acotarlo evita configuraciones confusas del tipo "cada 3, desfase 7".
            if not 0 <= block.frequency_offset < block.frequency:
                raise ValidationError(_(
                    'El desplazamiento debe estar entre 0 y %(max)s cuando se imprime cada %(freq)s pedidos.',
                    max=block.frequency - 1, freq=block.frequency,
                ))

    @api.constrains('block_type', 'barcode_width', 'barcode_height')
    def _check_barcode_size(self):
        for block in self:
            if block.block_type in SIZELESS_TYPES:
                continue
            if block.barcode_width <= 0 or block.barcode_height <= 0:
                raise ValidationError(_('El ancho y el alto del código deben ser mayores que cero.'))
            if block.barcode_width > MAX_CODE_SIDE or block.barcode_height > MAX_CODE_SIDE:
                raise ValidationError(_(
                    'El ancho y el alto no pueden pasar de %(max)s px. Por encima de ese '
                    'tamaño el servidor no genera el código y el ticket sale con la imagen '
                    'rota. Para impresión térmica lo recomendable son 120-200 px.',
                    max=MAX_CODE_SIDE,
                ))
