from odoo import fields, models


class PosPaymentCustomerRestriction(models.Model):
    """
    Línea de restricción: un método de pago + lista de partners autorizados,
    vinculada a una configuración de POS específica.

    Los campos create_delivery / to_invoice / to_ei_invoice se aplican
    automáticamente al cliente cuando selecciona este método en el POS.
    """
    _name = 'pos.payment.customer.restriction'
    _description = 'Restricción de método de pago por cliente (POS)'
    _order = 'config_id, sequence, id'

    config_id = fields.Many2one(
        comodel_name='pos.config',
        string='Configuración POS',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    payment_method_id = fields.Many2one(
        comodel_name='pos.payment.method',
        string='Método de pago',
        required=True,
        ondelete='restrict',
    )
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='pos_payment_restrict_partner_rel',
        column1='restriction_id',
        column2='partner_id',
        string='Clientes autorizados',
        help='Si la lista está vacía, el método queda bloqueado para todos. '
             'Agrega los clientes que sí pueden usarlo.',
    )
    create_delivery = fields.Boolean(
        string='Crear entrega de inventario',
        default=False,
        help='Al validar la orden, genera automáticamente una entrega de inventario '
             '(stock.picking) para los clientes de esta restricción.',
    )
    to_invoice = fields.Boolean(
        string='Crear factura',
        default=False,
        help='Decide si la orden de un cliente de esta restricción se factura '
             'en el POS. Prevalece sobre la factura obligatoria: si está '
             'desmarcado, la orden queda sin factura para agruparla después.',
    )
    to_ei_invoice = fields.Boolean(
        string='Crear factura electrónica',
        default=False,
        help='Emite factura electrónica (DIAN) al seleccionar un cliente '
             'de esta restricción. Requiere módulo l10n_co_edi_jorels_pos.',
    )
    restriction_field_ids = fields.One2many(
        comodel_name='pos.payment.restriction.field',
        inverse_name='restriction_id',
        string='Campos del popup',
        help='Campos que el cajero debe completar al seleccionar este método de pago.',
    )
