import json
import logging
from datetime import timezone

import psycopg2
from dateutil.parser import parse as parse_date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShopifyOrderImport(models.Model):
    _name = 'shopify.order.import'
    _description = 'Pedido de Shopify (consulta e importación)'
    _order = 'order_date desc, id desc'

    name = fields.Char(string='Pedido', readonly=True, index=True)
    shopify_order_id = fields.Char(
        string='ID de Shopify', readonly=True, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company,
    )
    order_date = fields.Datetime(string='Fecha', readonly=True)
    partner_name = fields.Char(string='Cliente', readonly=True)
    email = fields.Char(string='Email', readonly=True)
    phone = fields.Char(string='Teléfono', readonly=True)
    amount_total = fields.Float(string='Total Shopify', readonly=True)
    currency_code = fields.Char(string='Moneda', readonly=True)
    payload_json = fields.Text(string='Payload', readonly=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', readonly=True, copy=False,
    )
    state = fields.Selection(
        selection=[('pending', 'Pendiente'), ('imported', 'Registrado')],
        string='Estado', compute='_compute_state', store=True,
    )

    @api.depends('sale_order_id')
    def _compute_state(self):
        for rec in self:
            rec.state = 'imported' if rec.sale_order_id else 'pending'

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_order_date(created_at):
        """Parse Shopify's ISO timestamp into a naive-UTC datetime."""
        try:
            dt = parse_date(created_at)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return fields.Datetime.now()

    @staticmethod
    def _payload_partner_name(data):
        cust = data.get('customer') or {}
        name = f"{cust.get('first_name') or ''} {cust.get('last_name') or ''}".strip()
        return name or (data.get('email') or '')

    # ------------------------------------------------------------------ #
    #  Sync — pull recent orders from Shopify into the cache             #
    # ------------------------------------------------------------------ #

    def action_sync_from_shopify(self):
        """Fetch the most recent Shopify orders and upsert them as records.

        Triggered from the list header (so ``self`` may be empty). Reads the
        credentials of the active company and links any order that already
        exists as a ``sale.order``.
        """
        company = self.env.company
        orders = company._shopify_fetch_last_orders(limit=50)

        SaleOrder = self.env['sale.order'].sudo()
        created = updated = 0
        for data in orders:
            sid = data.get('id')
            if not sid:
                continue
            existing_so = SaleOrder.search([
                ('shopify_order_id', '=', sid),
                ('company_id', '=', company.id),
            ], limit=1)
            vals = {
                'name':             data.get('name') or sid,
                'shopify_order_id': sid,
                'company_id':       company.id,
                'order_date':       self._parse_order_date(data.get('created_at')),
                'partner_name':     self._payload_partner_name(data),
                'email':            data.get('email'),
                'phone':            data.get('phone'),
                'amount_total':     data.get('total_price') or 0.0,
                'currency_code':    data.get('currency_code') or '',
                'payload_json':     json.dumps(data),
                'sale_order_id':    existing_so.id if existing_so else False,
            }
            rec = self.search([
                ('shopify_order_id', '=', sid),
                ('company_id', '=', company.id),
            ], limit=1)
            if rec:
                rec.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1

        _logger.info("Shopify sync (company=%s): %s nuevos, %s actualizados.",
                     company.name, created, updated)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # ------------------------------------------------------------------ #
    #  Register — create the real sale.order in Odoo                     #
    # ------------------------------------------------------------------ #

    def _register_order(self, controller):
        """Create (and confirm) the sale.order for this Shopify order.

        Mirrors the webhook flow: idempotent on ``shopify_order_id`` and runs
        the same invoice / delivery dispatch driven by the company config.
        """
        self.ensure_one()
        if self.sale_order_id:
            return self.sale_order_id

        company = self.company_id
        data = json.loads(self.payload_json or '{}')
        if not data:
            raise UserError(_(
                "El pedido %s no tiene payload almacenado; vuelve a "
                "sincronizar antes de registrarlo."
            ) % self.name)

        SaleOrder = self.env['sale.order'].sudo()
        existing = SaleOrder.search([
            ('shopify_order_id', '=', self.shopify_order_id),
            ('company_id', '=', company.id),
        ], limit=1)
        if existing:
            self.sale_order_id = existing.id
            return existing

        cfg = controller._load_config(company)
        warehouse = self.env['stock.warehouse'].sudo().browse(
            cfg['warehouse_id']
        ).exists()
        if not warehouse or warehouse.company_id != company:
            warehouse = self.env['stock.warehouse'].sudo().search(
                [('company_id', '=', company.id)], limit=1
            )

        partner = controller._find_or_create_partner(data)
        order_date = self._parse_order_date(data.get('created_at'))

        try:
            with self.env.cr.savepoint():
                order = controller._create_confirmed_order(
                    partner, order_date, warehouse, cfg, data, company
                )
        except psycopg2.errors.UniqueViolation as e:
            # Lost a race against the webhook (or a concurrent click): the
            # SAVEPOINT already rolled back, so just relink the winner.
            if 'shopify_order_company_uniq' not in str(e):
                raise
            existing = SaleOrder.search([
                ('shopify_order_id', '=', self.shopify_order_id),
                ('company_id', '=', company.id),
            ], limit=1)
            self.sale_order_id = existing.id if existing else False
            return existing

        # Post-creation steps, identical to the webhook.
        if cfg['auto_invoice']:
            controller._dispatch_invoice_trigger(order, cfg, data)
        if cfg['auto_delivery']:
            for pick in order.picking_ids:
                controller._notify_warehouse(
                    pick, order, partner, data, cfg['warehouse_partner_ids']
                )

        self.sale_order_id = order.id
        return order

    def action_register(self):
        """Register the selected Shopify orders as real sale orders in Odoo."""
        from ..controllers.controllers import ShopifyOrderController
        controller = ShopifyOrderController()
        for rec in self:
            rec._register_order(controller)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return False
        return {
            'type':      'ir.actions.act_window',
            'name':      self.sale_order_id.name,
            'res_model': 'sale.order',
            'res_id':    self.sale_order_id.id,
            'view_mode': 'form',
            'target':    'current',
        }
