import logging
from datetime import timezone

from dateutil.parser import parse as parse_date

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class _SimulationRollback(Exception):
    """Internal sentinel used to force a SAVEPOINT rollback after a dry-run."""


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    enable_shopify_webhook = fields.Boolean(
        string="Enable Shopify Webhook",
        related='company_id.shopify_enable_webhook',
        readonly=False,
    )

    shopify_webhook_secret = fields.Char(
        string='Webhook Secret',
        related='company_id.shopify_webhook_secret',
        readonly=False,
    )

    shopify_webhook_url = fields.Char(
        string='URL del Webhook',
        compute='_compute_shopify_webhook_url',
        readonly=True,
        help=(
            "URL pública que debe pegarse en Shopify Admin → Settings → "
            "Notifications → Webhooks. Incluye el ID de la compañía, así "
            "que cada compañía tiene su propio endpoint."
        ),
    )

    shopify_debug = fields.Boolean(
        string="Activar logging de depuración",
        related='company_id.shopify_debug',
        readonly=False,
    )

    # ------------------------------------------------------------------
    # Admin API (outbound query)
    # ------------------------------------------------------------------

    shopify_enable_api = fields.Boolean(
        string='Activar consulta a la API de Shopify',
        related='company_id.shopify_enable_api',
        readonly=False,
    )

    shopify_shop_url = fields.Char(
        string='Dominio de la tienda',
        related='company_id.shopify_shop_url',
        readonly=False,
    )

    shopify_client_id = fields.Char(
        string='Shopify Client ID',
        related='company_id.shopify_client_id',
        readonly=False,
    )

    shopify_client_secret = fields.Char(
        string='Client Secret',
        related='company_id.shopify_client_secret',
        readonly=False,
    )

    shopify_admin_api_token = fields.Char(
        string='Admin API Access Token (manual)',
        related='company_id.shopify_admin_api_token',
        readonly=False,
    )

    shopify_api_version = fields.Char(
        string='Versión de la Admin API',
        related='company_id.shopify_api_version',
        readonly=False,
    )

    @api.depends('company_id')
    def _compute_shopify_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', default=''
        ).rstrip('/')
        for rec in self:
            if rec.company_id and base_url:
                rec.shopify_webhook_url = f"{base_url}/shopify/order/{rec.company_id.id}"
            else:
                rec.shopify_webhook_url = ''

    # ------------------------------------------------------------------
    # Sales
    # ------------------------------------------------------------------

    shopify_default_price_list = fields.Many2one(
        'product.pricelist',
        string='Lista de precios Shopify',
        related='company_id.shopify_default_price_list_id',
        readonly=False,
    )

    shopify_price_tax_mode = fields.Selection(
        related='company_id.shopify_price_tax_mode',
        readonly=False,
    )

    shopify_account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta analítica Shopify',
        related='company_id.shopify_account_analytic_id',
        readonly=False,
    )

    shopify_default_tag_id = fields.Many2one(
        'crm.tag',
        string='Etiqueta por defecto',
        related='company_id.shopify_default_tag_id',
        readonly=False,
    )

    shopify_default_user_id = fields.Many2one(
        'res.users',
        string='Vendedor por defecto',
        related='company_id.shopify_default_user_id',
        readonly=False,
    )

    shopify_default_team_id = fields.Many2one(
        'crm.team',
        string='Equipo de ventas por defecto',
        related='company_id.shopify_default_team_id',
        readonly=False,
    )

    shopify_shipping_product_id = fields.Many2one(
        'product.product',
        string='Producto de envío por defecto',
        related='company_id.shopify_shipping_product_id',
        readonly=False,
    )

    shopify_source_tag_mapping_ids = fields.One2many(
        related='company_id.shopify_source_tag_mapping_ids',
        readonly=False,
    )

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    shopify_auto_delivery = fields.Boolean(
        string="Registro automático de entrega de inventario",
        related='company_id.shopify_auto_delivery',
        readonly=False,
    )

    shopify_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén Shopify',
        related='company_id.shopify_warehouse_id',
        readonly=False,
    )

    shopify_warehouse_responsible_ids = fields.Many2many(
        'res.users',
        related='company_id.shopify_warehouse_responsible_ids',
        readonly=False,
    )

    shopify_label_page_width = fields.Integer(
        related='company_id.shopify_label_page_width',
        readonly=False,
    )
    shopify_label_page_height = fields.Integer(
        related='company_id.shopify_label_page_height',
        readonly=False,
    )
    shopify_label_rows = fields.Integer(
        related='company_id.shopify_label_rows',
        readonly=False,
    )
    shopify_label_cols = fields.Integer(
        related='company_id.shopify_label_cols',
        readonly=False,
    )

    def set_values(self):
        super().set_values()
        paperformat = self.env.ref(
            'shopify_order_webhook.paperformat_shopify_delivery_label',
            raise_if_not_found=False,
        )
        if paperformat:
            company = self.company_id
            paperformat.sudo().write({
                'page_width': company.shopify_label_page_width or 140,
                'page_height': company.shopify_label_page_height or 216,
            })

    # ------------------------------------------------------------------
    # Accounting
    # ------------------------------------------------------------------

    shopify_auto_invoice = fields.Boolean(
        string="Activar creación automática de facturas",
        related='company_id.shopify_auto_invoice',
        readonly=False,
    )

    shopify_invoice_trigger = fields.Selection(
        related='company_id.shopify_invoice_trigger',
        readonly=False,
    )

    shopify_invoice_delay_hours = fields.Integer(
        related='company_id.shopify_invoice_delay_hours',
        readonly=False,
    )

    shopify_account_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de facturas Shopify',
        related='company_id.shopify_account_journal_id',
        readonly=False,
    )

    shopify_accounting_responsible_ids = fields.Many2many(
        'res.users',
        related='company_id.shopify_accounting_responsible_ids',
        readonly=False,
    )

    shopify_auto_payment = fields.Boolean(
        string="Activar registro automático de pago",
        related='company_id.shopify_auto_payment',
        readonly=False,
    )

    shopify_payment_mapping_ids = fields.One2many(
        related='company_id.shopify_payment_mapping_ids',
        readonly=False,
    )

    # ------------------------------------------------------------------
    # Simulation — fetch last orders from Shopify and dry-run the mapping
    # ------------------------------------------------------------------

    def action_shopify_simulate_last_orders(self):
        """Fetch the last 10 Shopify orders and dry-run their mapping.

        Each order is built and created inside a SAVEPOINT that is always
        rolled back, so nothing is persisted: this only validates that the
        payload maps correctly (products, prices, taxes, totals). Results
        are rendered into a transient wizard opened in a dialog.
        """
        self.ensure_one()
        company = self.company_id

        # Local import to avoid a hard module-load dependency between the
        # model layer and the controller layer.
        from ..controllers.controllers import ShopifyOrderController
        controller = ShopifyOrderController()

        orders = company._shopify_fetch_last_orders(limit=10)
        cfg = controller._load_config(company)

        warehouse = self.env['stock.warehouse'].sudo().browse(
            cfg['warehouse_id']
        ).exists()
        if not warehouse or warehouse.company_id != company:
            warehouse = self.env['stock.warehouse'].sudo().search(
                [('company_id', '=', company.id)], limit=1
            )

        results = []
        for data in orders:
            summary = {
                'name':    data.get('name') or '(sin nombre)',
                'partner': '',
                'untaxed': 0.0,
                'tax':     0.0,
                'total':   0.0,
                'lines':   [],
                'error':   None,
            }
            try:
                with self.env.cr.savepoint():
                    partner = controller._find_or_create_partner(data)
                    try:
                        order_date = parse_date(data.get('created_at'))
                        order_date = order_date.astimezone(
                            timezone.utc).replace(tzinfo=None)
                    except Exception:
                        order_date = fields.Datetime.now()
                    vals = controller._build_order_vals(
                        partner, order_date, warehouse, cfg, data, company
                    )
                    order = self.env['sale.order'].sudo().with_company(
                        company
                    ).create(vals)

                    summary['partner'] = partner.name or ''
                    summary['untaxed'] = order.amount_untaxed
                    summary['tax'] = order.amount_tax
                    summary['total'] = order.amount_total
                    summary['lines'] = [{
                        'product':  line.product_id.display_name or line.name,
                        'qty':      line.product_uom_qty,
                        'price':    line.price_unit,
                        'taxes':    ', '.join(line.tax_ids.mapped('name')),
                        'subtotal': line.price_subtotal,
                        'total':    line.price_total,
                    } for line in order.order_line if not line.display_type]

                    # Always undo: this is a simulation.
                    raise _SimulationRollback()
            except _SimulationRollback:
                pass
            except Exception as e:  # noqa: BLE001 — surface per-order failures
                _logger.exception("Shopify simulation failed for order %s",
                                  summary['name'])
                summary['error'] = str(e)
            # The SAVEPOINT rollback leaves the ORM cache holding values for
            # rolled-back records; clear it so the next order starts clean.
            self.env.invalidate_all()
            results.append(summary)

        wizard = self.env['shopify.order.simulation'].create({
            'company_id':  company.id,
            'result_html': self._shopify_render_simulation(company, results),
        })
        return {
            'type':      'ir.actions.act_window',
            'name':      _("Simulación de órdenes Shopify"),
            'res_model': 'shopify.order.simulation',
            'res_id':    wizard.id,
            'view_mode': 'form',
            'target':    'new',
        }

    @staticmethod
    def _shopify_render_simulation(company, results):
        """Render the dry-run results as an HTML report for the wizard."""
        from markupsafe import Markup

        currency = company.currency_id

        def fmt(amount):
            return f"{amount:,.2f} {currency.name or ''}".strip()

        blocks = [Markup(
            "<p class='text-muted'>Simulación de las últimas {n} órdenes de "
            "Shopify. <b>No se creó ningún registro</b> — los datos se "
            "construyeron y descartaron para validar el mapeo.</p>"
        ).format(n=len(results))]

        for r in results:
            header = Markup(
                "<h4 class='mt-3 mb-1'>{name} <small class='text-muted'>— "
                "{partner}</small></h4>"
            ).format(name=r['name'], partner=r['partner'] or '—')
            blocks.append(header)

            if r['error']:
                blocks.append(Markup(
                    "<div class='alert alert-danger py-1 px-2 mb-2'>"
                    "<b>Error:</b> {err}</div>"
                ).format(err=r['error']))
                continue

            rows = [Markup(
                "<tr><td>{product}</td><td class='text-end'>{qty:g}</td>"
                "<td class='text-end'>{price}</td><td>{taxes}</td>"
                "<td class='text-end'>{subtotal}</td>"
                "<td class='text-end'>{total}</td></tr>"
            ).format(
                product=l['product'] or '',
                qty=l['qty'] or 0,
                price=fmt(l['price']),
                taxes=l['taxes'] or '—',
                subtotal=fmt(l['subtotal']),
                total=fmt(l['total']),
            ) for l in r['lines']]

            table = Markup(
                "<table class='table table-sm table-bordered'>"
                "<thead><tr>"
                "<th>Producto</th><th class='text-end'>Cant.</th>"
                "<th class='text-end'>P. unit.</th><th>Impuestos</th>"
                "<th class='text-end'>Subtotal</th>"
                "<th class='text-end'>Total</th>"
                "</tr></thead><tbody>{rows}</tbody>"
                "<tfoot>"
                "<tr><th colspan='4' class='text-end'>Base imponible</th>"
                "<th colspan='2' class='text-end'>{untaxed}</th></tr>"
                "<tr><th colspan='4' class='text-end'>Impuestos</th>"
                "<th colspan='2' class='text-end'>{tax}</th></tr>"
                "<tr><th colspan='4' class='text-end'>Total</th>"
                "<th colspan='2' class='text-end'>{total}</th></tr>"
                "</tfoot></table>"
            ).format(
                rows=Markup('').join(rows),
                untaxed=fmt(r['untaxed']),
                tax=fmt(r['tax']),
                total=fmt(r['total']),
            )
            blocks.append(table)

        if not results:
            blocks.append(Markup(
                "<div class='alert alert-info'>Shopify no devolvió órdenes.</div>"
            ))

        return Markup('').join(blocks)
