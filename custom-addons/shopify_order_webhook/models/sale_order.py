from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_shopify_order = fields.Boolean(
        default=False,
        index=True,
        copy=False,
        help="True if this sale order was created from a Shopify webhook.",
    )

    shopify_payment_gateways = fields.Char(
        copy=False,
        help=(
            "Comma-separated list of payment_gateway_names captured from "
            "the original Shopify payload. Used to look up the journal "
            "via shopify.payment.journal.mapping when registering the "
            "automatic payment."
        ),
    )

    shopify_invoice_scheduled_at = fields.Datetime(
        copy=False,
        index=True,
        help=(
            "When the delayed-invoice cron should generate the invoice "
            "for this order. Only set when invoice trigger is 'delayed'."
        ),
    )

    shopify_order_id = fields.Char(
        copy=False,
        index=True,
        help=(
            "Numeric Shopify order ID (payload `id`). Stable and "
            "immutable — used as the idempotency key so the same "
            "webhook delivered twice cannot create two sale orders."
        ),
    )

    # Odoo 19 ignora ``_sql_constraints``. El nombre del atributo produce la
    # restricción ``sale_order_shopify_order_company_uniq``, la misma que creó
    # 17, y la definición se deja idéntica para que en la base actualizada no
    # se elimine y se vuelva a crear. El controlador depende de ese nombre
    # (``'shopify_order_company_uniq' in str(e)``) para la idempotencia.
    _shopify_order_company_uniq = models.Constraint(
        'unique(shopify_order_id, company_id)',
        'Esta orden de Shopify ya fue importada para esta compañía.',
    )

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _shopify_get_config(self):
        """Return the Shopify configuration for this order's company.

        All settings now live on ``res.company`` (per-company), so we
        read straight from ``self.company_id`` instead of the old
        ``ir.config_parameter`` keys.
        """
        self.ensure_one()
        company = self.company_id
        return {
            'analytic_id':            company.shopify_account_analytic_id.id,
            'journal_id':             company.shopify_account_journal_id.id,
            'invoice_trigger':        company.shopify_invoice_trigger or 'on_confirm',
            'invoice_delay_hours':    company.shopify_invoice_delay_hours or 24,
            'auto_invoice':           company.shopify_auto_invoice,
            'auto_payment':           company.shopify_auto_payment,
            'accounting_partner_ids': company.shopify_accounting_responsible_ids.mapped('partner_id').ids,
        }

    # ------------------------------------------------------------------
    # Invoice flow (moved from the webhook controller so it can also be
    # invoked from the stock.picking hook and the delayed-invoice cron)
    # ------------------------------------------------------------------

    def _shopify_process_invoice(self):
        """Create + post + notify (+ optional pay) for this Shopify order.

        Safe to call multiple times: ``_create_invoices`` only generates
        moves for lines whose ``qty_to_invoice > 0``, and we early-out
        when the order is fully invoiced.
        """
        self.ensure_one()
        if not self.is_shopify_order:
            return self.env['account.move']
        if self.state not in ('sale', 'done'):
            return self.env['account.move']
        if self.invoice_status == 'invoiced':
            return self.env['account.move']

        cfg = self._shopify_get_config()
        invoices = self.env['account.move']
        try:
            new_invoices = self._create_invoices()
        except Exception as e:
            _logger.warning(
                "Shopify: nothing to invoice yet for %s (%s)", self.name, e
            )
            return invoices

        for inv in new_invoices:
            self._shopify_post_invoice(inv, cfg)
            self._shopify_notify_accounting(inv, cfg['accounting_partner_ids'])
            if cfg['auto_payment']:
                self._shopify_safe_register_payment(inv)
            invoices |= inv

        # Clear the scheduled timestamp once handled.
        if self.shopify_invoice_scheduled_at:
            self.shopify_invoice_scheduled_at = False

        return invoices

    def _shopify_post_invoice(self, inv, cfg):
        # DECISIÓN DEL USUARIO (intencional): las facturas de Shopify NO se
        # envían a la DIAN. Marcar ``ei_is_valid=True`` antes de publicar hace
        # que Jorels las trate como ya validadas: en Jorels 19
        # ``AccountMove._can_process_edi`` exige ``not ei_is_valid``, así que
        # ``_post`` no las envía (``is_pending_to_send_to_dian`` es False) y
        # el envío masivo tampoco las toma. No quitar sin decisión del usuario.
        inv.write({
            'invoice_date': self.date_order,
            'journal_id':   cfg['journal_id'] or inv.journal_id.id,
            'ei_is_valid':  True,
        })
        if cfg['analytic_id']:
            for line in inv.invoice_line_ids:
                line.write({
                    'analytic_distribution': {str(cfg['analytic_id']): 100.0},
                })
        inv.action_post()

    def _shopify_notify_accounting(self, inv, partner_ids):
        """Post a chatter entry on the invoice and notify accounting responsibles.

        Uses ``message_post`` (not ``message_notify``) so the entry is
        **visible in the invoice's chatter** to anyone with access, in
        addition to triggering the inbox + email notification to
        ``partner_ids``. Mirrors the warehouse-notification flow.
        """
        body = Markup(
            "<p><strong>🛒 Nueva factura generada</strong></p>"
            "<ul>"
            "<li><b>Referencia externa:</b> {external_ref}</li>"
            "<li><b>Cliente:</b> {customer}</li>"
            "<li><b>Factura:</b> {inv_name}</li>"
            "<li><b>Total:</b> {total} {currency}</li>"
            "<li><b>Fecha:</b> {date}</li>"
            "</ul>"
            "<p>Saludos.</p>"
        ).format(
            external_ref=self.client_order_ref or '',
            customer=self.partner_id.name,
            inv_name=inv.name,
            total=inv.amount_total,
            currency=inv.currency_id.name,
            date=inv.invoice_date,
        )
        subject = f"Nueva factura – {inv.name} ({self.partner_id.name})"

        if partner_ids:
            inv.message_post(
                body=body,
                subject=subject,
                partner_ids=partner_ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        else:
            _logger.warning(
                "Shopify webhook: invoice %s posted but company %s has "
                "no shopify_accounting_responsible_ids configured — no "
                "email sent.", inv.name, self.company_id.name,
            )
            inv.message_post(
                body=body,
                subject=subject,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    def _shopify_safe_register_payment(self, inv):
        """Registrar el pago automático sin arrastrar la factura si falla.

        En 17 una excepción del pago subía hasta el ``except`` general del
        controlador: se respondía 500, pero la orden y la factura ya
        publicada quedaban guardadas (y el reintento de Shopify se omitía
        por idempotencia), sin más rastro que el log. Aquí el pago corre en
        un SAVEPOINT: si falla, se revierte solo el pago (sin pagos a
        medias), se registra un error claro en el log y se deja una nota en
        el chatter de la factura para que contabilidad lo registre a mano.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return self._shopify_register_and_reconcile_payment(inv)
        except Exception as e:
            _logger.error(
                "Shopify: la factura %s de la orden %s quedó PUBLICADA SIN "
                "PAGO: falló el registro automático del pago (%s). Registre "
                "el pago manualmente.",
                inv.name, self.name, e, exc_info=True,
            )
            inv.message_post(
                body=Markup(
                    "<p><strong>Pago automático de Shopify no registrado</strong></p>"
                    "<p>La factura se publicó, pero el pago automático falló y "
                    "debe registrarse manualmente.</p><p>Error: {error}</p>"
                ).format(error=str(e)),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            return self.env['account.payment']

    def _shopify_register_and_reconcile_payment(self, inv):
        warehouse = self.warehouse_id
        partner   = self.partner_id

        gateways = [
            g.strip()
            for g in (self.shopify_payment_gateways or '').split(',')
            if g.strip()
        ]
        journal = None
        if gateways:
            mapping = self.env['shopify.payment.journal.mapping'].sudo().search(
                [
                    ('shopify_gateway', 'in', gateways),
                    ('company_id', '=', self.company_id.id),
                ], limit=1,
            )
            if mapping:
                journal = mapping.journal_id
        if not journal:
            journal = self.env['account.journal'].sudo().search([
                ('type', 'in', ['bank', 'cash']),
                ('company_id', '=', warehouse.company_id.id),
            ], limit=1)

        payment = self.env['account.payment'].sudo().with_company(
            warehouse.company_id
        ).create({
            'payment_type':           'inbound',
            'partner_type':           'customer',
            'partner_id':             partner.id,
            'amount':                 inv.amount_total,
            'date':                   self.date_order,
            'journal_id':             journal.id,
            'payment_method_line_id': journal.inbound_payment_method_line_ids[:1].id,
            # 19: ``account.payment.ref`` pasó a ``memo`` (va al ``ref`` del asiento).
            'memo':                   inv.name,
            'company_id':             warehouse.company_id.id,
        })

        # 19: el pago solo genera asiento si tiene ``outstanding_account_id``
        # (``_generate_journal_entry``). Ese campo sale de
        # ``payment_method_line_id.payment_account_id`` y, con
        # account_accountant instalado, el núcleo NO aplica ningún respaldo:
        # el pago quedaría "en proceso" sin asiento y sin conciliar con la
        # factura. En 17 el respaldo era la cuenta de recibos pendientes de la
        # compañía; ``_get_outstanding_account`` es el equivalente en 19 (el
        # mismo que usa el núcleo cuando no hay contabilidad completa). Solo se
        # aplica si la línea del método de pago no tiene cuenta propia.
        if not payment.outstanding_account_id:
            payment.outstanding_account_id = payment._get_outstanding_account(
                payment.payment_type
            )
        payment.action_post()

        if not payment.move_id:
            # No debería ocurrir con la cuenta asegurada arriba; si ocurre, el
            # pago no se puede conciliar y se prefiere fallar (se revierte el
            # pago y queda la nota en la factura) a dejarlo a medias.
            raise UserError(_(
                "El pago de Shopify para la factura %s no generó asiento "
                "contable; no se puede conciliar."
            ) % inv.name)

        receivable = ('asset_receivable', 'liability_payable')
        pay_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in receivable and not l.reconciled
        )
        inv_lines = inv.line_ids.filtered(
            lambda l: l.account_id.account_type in receivable and not l.reconciled
        )
        if pay_lines and inv_lines:
            (pay_lines + inv_lines).reconcile()
        else:
            _logger.warning(
                "Shopify: el pago %s no se concilió con la factura %s (sin "
                "líneas por cobrar abiertas en uno de los dos).",
                payment.name, inv.name,
            )
        return payment

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def _shopify_cron_delayed_invoices(self):
        """Invoice Shopify orders whose scheduled time has elapsed."""
        now = fields.Datetime.now()
        orders = self.search([
            ('is_shopify_order', '=', True),
            ('shopify_invoice_scheduled_at', '!=', False),
            ('shopify_invoice_scheduled_at', '<=', now),
            ('state', 'in', ('sale', 'done')),
            ('invoice_status', '!=', 'invoiced'),
        ])
        for order in orders:
            try:
                order._shopify_process_invoice()
            except Exception as e:
                _logger.error(
                    "Shopify delayed invoice failed for %s: %s",
                    order.name, e, exc_info=True,
                )
