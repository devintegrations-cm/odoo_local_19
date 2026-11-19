from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    skip_partner_due = fields.Boolean(
        string="No calcular la deuda de los clientes",
        default=True,
        help="El POS no calcula lo que debe cada cliente (órdenes y facturas pendientes) al cargar los "
             "clientes, al abrir la caja, al buscar ni después de una venta con cuenta de cliente. "
             "Desmarcado: comportamiento estándar de Liquidar deudas (pos_settle_due).",
    )
