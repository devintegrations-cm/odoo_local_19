from odoo import http, fields
from odoo.http import request
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse as parse_date
from markupsafe import Markup
import logging
import pprint
import psycopg2


def _shopify_lock_key(company_id, shopify_id):
    """Build a stable signed 64-bit key for ``pg_advisory_xact_lock``.

    Hashing the (company_id, shopify_id) tuple into a bigint lets us
    serialize concurrent webhooks for the same order without taking a
    global lock on the sale_order table.
    """
    payload = f"shopify:{company_id}:{shopify_id}".encode('utf-8')
    return int.from_bytes(
        hashlib.sha256(payload).digest()[:8], 'big', signed=True,
    )

_logger = logging.getLogger(__name__)


class ShopifyOrderController(http.Controller):

    # ------------------------------------------------------------------ #
    #  Authentication                                                      #
    # ------------------------------------------------------------------ #

    def _verify_hmac(self, raw_body, company):
        """Verify the Shopify HMAC-SHA256 signature using the company's secret.

        Returns an error Response if verification fails, None if it passes.
        """
        secret = company.shopify_webhook_secret
        if not secret:
            # SHOPIFY-SEC-0002: en 17 una compañía sin secreto aceptaba la
            # solicitud sin autenticar (la ruta es pública y crea ventas con
            # sudo). Ahora se rechaza: sin secreto no hay forma de saber que el
            # pedido viene de Shopify. En producción la única compañía con el
            # webhook activo tiene secreto, así que no cambia nada allí.
            _logger.error(
                "Shopify webhook: la compañía %s (id=%s) tiene el webhook "
                "activo pero no tiene shopify_webhook_secret configurado; la "
                "solicitud se RECHAZA (401). Configure el secreto de firma "
                "de Shopify en Ajustes.",
                company.name, company.id,
            )
            return self._error_response("Webhook secret not configured", 401)

        received = request.httprequest.headers.get('X-Shopify-Hmac-SHA256', '')
        if not received:
            _logger.warning("Shopify webhook: missing HMAC header — rejected.")
            return self._error_response("Missing HMAC signature", 401)

        computed = base64.b64encode(
            hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
        ).decode('utf-8')

        if not hmac.compare_digest(computed, received):
            _logger.warning("Shopify webhook: HMAC mismatch — rejected.")
            return self._error_response("Invalid HMAC signature", 401)

        return None

    # ------------------------------------------------------------------ #
    #  Configuration                                                       #
    # ------------------------------------------------------------------ #

    def _load_config(self, company):
        """Build the per-request config dict from the target company."""
        return {
            'analytic_id':            company.shopify_account_analytic_id.id,
            'price_list_id':          company.shopify_default_price_list_id.id,
            'price_tax_mode':         company.shopify_price_tax_mode or 'included',
            'journal_id':             company.shopify_account_journal_id.id,
            'warehouse_id':           company.shopify_warehouse_id.id,
            'warehouse_partner_ids':  company.shopify_warehouse_responsible_ids.mapped('partner_id').ids,
            'accounting_partner_ids': company.shopify_accounting_responsible_ids.mapped('partner_id').ids,
            'default_tag_id':         company.shopify_default_tag_id.id,
            'user_id':                company.shopify_default_user_id.id,
            'team_id':                company.shopify_default_team_id.id,
            'shipping_product_id':    company.shopify_shipping_product_id.id,
            'auto_delivery':          company.shopify_auto_delivery,
            'auto_invoice':           company.shopify_auto_invoice,
            'auto_payment':           company.shopify_auto_payment,
            'invoice_trigger':        company.shopify_invoice_trigger or 'on_confirm',
            'invoice_delay_hours':    company.shopify_invoice_delay_hours or 24,
        }

    # ------------------------------------------------------------------ #
    #  Tag resolution                                                      #
    # ------------------------------------------------------------------ #

    def _resolve_tag_ids(self, data, cfg, company):
        """Return the crm.tag IDs to apply to the sale order.

        Iterates the company's source-tag mappings (ordered by sequence)
        and returns the first whose pattern is a case-insensitive
        substring of the order's source_name. Falls back to the
        company's default tag if no pattern matches.
        """
        source_name = (data.get('source_name') or '').lower()
        for mapping in company.shopify_source_tag_mapping_ids:
            pattern = (mapping.source_pattern or '').lower()
            if pattern and pattern in source_name:
                return mapping.tag_id.ids
        return [cfg['default_tag_id']] if cfg['default_tag_id'] else []

    # ------------------------------------------------------------------ #
    #  Partner                                                             #
    # ------------------------------------------------------------------ #

    def _find_or_create_partner(self, data):
        """Return a res.partner matching the Shopify customer, creating it if needed."""
        partner_model = request.env['res.partner'].sudo()
        customer = data.get('customer', {})
        
        vat = data.get('billing_address',{}).get('company','')
    
        phone = (
            data.get('phone')
            or data.get('shipping_address', {}).get('phone')
            or data.get('billing_address', {}).get('phone')
            or customer.get('phone')
            or customer.get('default_address', {}).get('phone')
        ) or False

        partner_data = {
            'vat': str(vat) if vat and vat.isnumeric() else False,
            'email': data.get('email'),
            'phone': phone,
        }

        partner = False
        for field, value in partner_data.items():
            if not value:
                continue
            partner = partner_model.search([(field, '=', value)], limit=1)
            if partner:
                break

        if partner and phone and not partner.phone:
            partner.write({'phone': phone})

        if not partner:
            billing  = data.get('billing_address', {})
            country  = request.env['res.country'].sudo().search(
                [('code', '=', billing.get('country_code'))], limit=1
            )
            partner_creation_data = {
                'name':       f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                'email':      partner_data['email'],
                'phone':      partner_data['phone'],
                'vat':        partner_data['vat'],
                'street':     billing.get('address1'),
                'street2':    billing.get('address2'),
                'city':       billing.get('city'),
                'zip':        billing.get('zip'),
                'country_id': country.id,
            }
            if data.get('shipping_address',{}).get('country_code','') == 'CO':
                partner_creation_data['email_edi'] = partner_data['email']
            
            partner = partner_model.create(partner_creation_data)

        return partner

    # ------------------------------------------------------------------ #
    #  Products                                                            #
    # ------------------------------------------------------------------ #

    def _find_or_create_product(self, line, company=None):
        """Return the product matching the line item, creating a consumable if not found.

        Resolution order:
          1. Explicit ``shopify.product.mapping`` (by Shopify variant id,
             then by SKU) — lets the user pin a Shopify variant to a precise
             Odoo product.
          2. Existing product whose ``default_code`` matches the SKU.
          3. A new placeholder consumable.

        type='consu' avoids the stock replenishment rules required by
        type='product' (storable), which causes action_confirm() to fail
        when routes are not configured on auto-created products.
        """
        # 1) Explicit Shopify → Odoo mapping.
        Mapping = request.env['shopify.product.mapping'].sudo()
        base = [('company_id', '=', company.id)] if company else []
        variant_id = str(line.get('variant_id') or '')
        sku = line.get('sku')
        mapping = Mapping.browse()
        if variant_id:
            mapping = Mapping.search(base + [
                ('shopify_variant_id', '=', variant_id),
                ('product_id', '!=', False),
            ], limit=1)
        if not mapping and sku:
            mapping = Mapping.search(base + [
                ('shopify_sku', '=', sku),
                ('product_id', '!=', False),
            ], limit=1)
        if mapping.product_id:
            return mapping.product_id

        # 2) Fallback: match by SKU.
        product = request.env['product.product'].sudo().search([
            ('default_code', 'ilike', line.get('sku')),
        ], limit=1)

        if not product:
            _logger.warning("Shopify: creating placeholder product — SKU: %s", line.get('sku'))
            product = request.env['product.product'].sudo().create({
                'name':         line.get('name'),
                'default_code': line.get('sku') or line.get('name'),
                'type':         'consu',
                'list_price':   float(line.get('price', 0.0)),
            })

        return product

    def _company_taxes(self, product, company):
        """Return the subset of product.taxes_id that belongs to ``company``.

        Products may carry taxes for several companies (multi-company
        setups). Applying all of them to a sale.order in a single company
        triggers the 'Incompatible companies' guard. Global taxes
        (company_id = False) are also kept.
        """
        return product.taxes_id.filtered(
            lambda t: not t.company_id or t.company_id == company
        )

    def _net_price(self, taxes, gross_price, price_tax_mode):
        """Bridge Shopify's price convention to the one Odoo expects.

        Two independent facts decide what to do:

        * ``price_tax_mode`` (company config) — whether the Shopify price
          already contains the tax ('included') or is net ('excluded').
        * The Odoo tax's ``price_include`` flag — whether Odoo interprets
          ``price_unit`` as tax-inclusive (True) or net (False).

        When both sides agree, the price passes through unchanged. When they
        disagree we convert, so the order total always matches Shopify:

          Shopify \\ Odoo │ price_include=True │ price_include=False
          ────────────────┼────────────────────┼─────────────────────
          included        │ pass through       │ divide tax out (net)
          excluded        │ add tax in          │ pass through

        Only percent taxes are considered; fixed taxes can't be converted by
        a simple rate and are left for Odoo to apply.
        """
        rate = sum(
            t.amount for t in taxes if t.amount_type == 'percent'
        )
        if not rate:
            return gross_price

        shopify_included = price_tax_mode != 'excluded'
        odoo_expects_inclusive = any(
            t.price_include for t in taxes if t.amount_type == 'percent'
        )
        factor = 1.0 + rate / 100.0

        if shopify_included and not odoo_expects_inclusive:
            return gross_price / factor      # strip tax → net price_unit
        if not shopify_included and odoo_expects_inclusive:
            return gross_price * factor      # add tax → inclusive price_unit
        return gross_price                   # both agree → no conversion

    # ------------------------------------------------------------------ #
    #  Sale order                                                          #
    # ------------------------------------------------------------------ #

    def _shipping_order_line(self, data, cfg, company):
        """Build the shipping order-line command from Shopify ``shipping_lines``.

        Returns a list with a single ``(0, 0, vals)`` tuple, or an empty
        list when no shipping product is configured or the order carries no
        shipping cost. Shopify shipping prices follow the same tax-inclusion
        convention as line items, so we run them through ``_net_price`` too.
        """
        if not cfg['shipping_product_id']:
            return []
        product = request.env['product.product'].sudo().browse(
            cfg['shipping_product_id']
        ).exists()
        if not product:
            return []

        gross = 0.0
        for shipping in data.get('shipping_lines', []):
            gross += float(shipping.get('price') or 0)
            for disc in shipping.get('discount_allocations', []):
                gross -= float(disc.get('amount') or 0)
        if gross <= 0:
            return []

        taxes = self._company_taxes(product, company)
        return [(0, 0, {
            'product_id':      product.id,
            'product_uom_qty': 1,
            'price_unit':      self._net_price(taxes, gross, cfg['price_tax_mode']),
            'tax_ids':         [(6, 0, taxes.ids)],
            'name':            product.display_name,
            'analytic_distribution': {str(cfg['analytic_id']): 100.0} if cfg['analytic_id'] else False,
        })]

    def _build_order_vals(self, partner, order_date, warehouse, cfg, data, company):
        """Map a Shopify payload to the ``sale.order`` create values.

        Pure mapping with no side effects beyond ``_find_or_create_product``
        (which may create placeholder products). Shared by the real webhook
        flow and the configuration dry-run simulation so both exercise the
        exact same price/tax/mapping logic.
        """
        order_lines = []
        for line in data.get('line_items', []):
            product = self._find_or_create_product(line, company)
            gross   = float(line.get('price') or 0) - float(line.get('total_discount') or 0)
            taxes   = self._company_taxes(product, company)
            order_lines.append((0, 0, {
                'product_id':      product.id,
                'product_uom_qty': line.get('quantity'),
                'price_unit':      self._net_price(taxes, gross, cfg['price_tax_mode']),
                'tax_ids':         [(6, 0, taxes.ids)],
                'name':            line.get('variant_title') or line.get('title'),
                'analytic_distribution': {str(cfg['analytic_id']): 100.0} if cfg['analytic_id'] else False,
            }))

        order_lines += self._shipping_order_line(data, cfg, company)

        if data.get('note'):
            order_lines.append((0, 0, {
                'display_type': 'line_note',
                'name':         data['note'],
            }))

        tag_ids = self._resolve_tag_ids(data, cfg, company)

        pricelist = request.env['product.pricelist'].sudo().browse(cfg['price_list_id']).exists()

        order_vals = {
            'partner_id':       partner.id,
            'client_order_ref': data.get('name'),
            'shopify_order_id': str(data.get('id') or '') or False,
            'date_order':       order_date,
            'warehouse_id':     warehouse.id,
            'company_id':       company.id,
            'order_line':       order_lines,
            'pricelist_id':     pricelist.id if pricelist else False,
            'tag_ids':          tag_ids,
        }
        # Only override the salesperson / sales team when configured;
        # otherwise leave them out so Odoo applies its own defaults.
        if cfg['user_id']:
            order_vals['user_id'] = cfg['user_id']
        if cfg['team_id']:
            order_vals['team_id'] = cfg['team_id']

        return order_vals

    def _create_confirmed_order(self, partner, order_date, warehouse, cfg, data, company):
        """Build order lines, create the sale order and confirm it."""
        order_vals = self._build_order_vals(
            partner, order_date, warehouse, cfg, data, company
        )
        order = request.env['sale.order'].sudo().with_company(company).create(order_vals)
        order.action_confirm()
        return order

    # ------------------------------------------------------------------ #
    #  Invoice trigger dispatch                                            #
    # ------------------------------------------------------------------ #

    def _dispatch_invoice_trigger(self, order, cfg, data):
        """Drive the invoice flow according to the configured trigger.

        - on_confirm  → invoice immediately (legacy behavior).
        - on_delivery → do nothing here; ``stock.picking._action_done``
                        will call ``_shopify_process_invoice`` when the
                        delivery is validated.
        - delayed     → schedule the cron by setting
                        ``shopify_invoice_scheduled_at``.
        """
        order.write({
            'is_shopify_order':         True,
            'shopify_payment_gateways': ','.join(data.get('payment_gateway_names') or []),
        })

        trigger = cfg['invoice_trigger']
        if trigger == 'on_confirm':
            order._shopify_process_invoice()
        elif trigger == 'delayed':
            delay = max(0, cfg['invoice_delay_hours'])
            order.shopify_invoice_scheduled_at = (
                fields.Datetime.now() + timedelta(hours=delay)
            )
        # 'on_delivery' → handled later by stock.picking._action_done.

    # ------------------------------------------------------------------ #
    #  Delivery                                                            #
    # ------------------------------------------------------------------ #

    def _format_shipping_address(self, shipping):
        """Render a Shopify ``shipping_address`` dict as escaped HTML lines.

        Values come from an external system and may contain anything;
        ``Markup.join`` auto-escapes each line while keeping the
        ``<br/>`` separator intact. Returns ``Markup('')`` if the
        payload has no shipping block (digital products, edge cases).
        """
        if not shipping:
            return Markup('<em>(sin dirección de envío en el payload)</em>')

        def _clean(key):
            return (shipping.get(key) or '').strip()

        lines = []
        for key in ('name', 'address1', 'address2'):
            v = _clean(key)
            if v:
                lines.append(v)
        locality = ', '.join(filter(None, [_clean(k) for k in ('city', 'province', 'zip')]))
        if locality:
            lines.append(locality)
        country = _clean('country')
        if country:
            lines.append(country)
        company = _clean('company')
        if company:
            lines.append(f"Empresa / NIT: {company}")
        phone = _clean('phone')
        if phone:
            lines.append(f"Tel: {phone}")

        return Markup('<br/>').join(lines) if lines else Markup('<em>(dirección vacía)</em>')

    def _build_delivery_label_attachment(self, pick):
        """Render the 1/8-letter shipping label PDF and store it as an
        ir.attachment linked to the picking.

        Returns an ``ir.attachment`` recordset (empty if rendering fails,
        e.g. wkhtmltopdf unavailable) so the warehouse notification still
        goes out even when the PDF cannot be produced.
        """
        try:
            pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'shopify_order_webhook.action_report_shopify_delivery_label',
                pick.ids,
            )
        except Exception as e:
            _logger.warning(
                "Shopify: no se pudo generar el PDF de etiqueta para %s: %s",
                pick.name, e,
            )
            return request.env['ir.attachment'].sudo()

        return request.env['ir.attachment'].sudo().create({
            'name':      f"Etiqueta {pick.name}.pdf",
            'type':      'binary',
            'datas':     base64.b64encode(pdf_content),
            'res_model': 'stock.picking',
            'res_id':    pick.id,
            'mimetype':  'application/pdf',
        })

    def _notify_warehouse(self, pick, order, partner, data, partner_ids):
        """Post a chatter entry on the picking and notify warehouse responsibles.

        Uses ``message_post`` (not ``message_notify``) so the entry is
        **visible in the picking's chatter** to anyone with access to
        the document, while still triggering the inbox + email
        notification to ``partner_ids``. This gives admins an audit
        trail without having to inspect ``mail.message`` directly or
        log in as a recipient.
        """
        shipping_html = self._format_shipping_address(data.get('shipping_address'))
        body = Markup(
            "<p><strong>🚚 Nueva orden de entrega generada</strong></p>"
            "<ul>"
            "<li><b>Referencia externa:</b> {external_ref}</li>"
            "<li><b>Venta:</b> {sale_name}</li>"
            "<li><b>Cliente:</b> {customer}</li>"
            "<li><b>Transferencia:</b> {pick_name}</li>"
            "</ul>"
            "<p><b>Dirección de entrega:</b><br/>{shipping}</p>"
            "<p>Saludos.</p>"
        ).format(
            external_ref=data.get('name', ''),
            sale_name=order.name,
            customer=partner.name,
            pick_name=pick.name,
            shipping=shipping_html,
        )
        subject = f"Nueva orden de entrega – {pick.name} ({partner.name})"

        # Generate the 1/8-letter shipping label PDF and attach it to the
        # notification so the warehouse receives it together with the email.
        attachment_ids = self._build_delivery_label_attachment(pick).ids

        if partner_ids:
            pick.message_post(
                body=body,
                subject=subject,
                partner_ids=partner_ids,
                attachment_ids=attachment_ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        else:
            # No responsibles configured — still log in chatter for
            # traceability so an admin can see the webhook fired.
            _logger.warning(
                "Shopify webhook: picking %s created but company %s has "
                "no shopify_warehouse_responsible_ids configured — no "
                "email sent.", pick.name, order.company_id.name,
            )
            pick.message_post(
                body=body,
                subject=subject,
                attachment_ids=attachment_ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _error_response(self, message, status=500):
        return request.make_response(
            json.dumps({'status': 'error', 'message': message}) + '\n',
            status=status,
            headers={'Content-Type': 'application/json'},
        )

    # ------------------------------------------------------------------ #
    #  Endpoint — orchestrates all steps                                   #
    # ------------------------------------------------------------------ #

    @http.route('/shopify/order/<int:company_id>',
                type='http', auth='public', csrf=False, methods=['POST'])
    def receive_order(self, company_id, **_):
        # Se conserva la referencia a la orden (como texto, para no volver a
        # leer la base si el cursor quedó abortado) para que el ``except``
        # general pueda decir en el log si ya quedó creada y confirmada antes
        # del fallo: la respuesta de error no revierte la transacción, así que
        # lo hecho hasta ese punto queda guardado y el reintento de Shopify se
        # contesta como ``skipped``.
        order_ref = None
        try:
            company = request.env['res.company'].sudo().browse(company_id).exists()
            if not company:
                return self._error_response(f"Unknown company id {company_id}", 404)
            if not company.shopify_enable_webhook:
                return self._error_response(
                    f"Shopify webhook is disabled for company '{company.name}'", 403
                )

            raw_body = request.httprequest.data

            error = self._verify_hmac(raw_body, company)
            if error:
                return error

            data = json.loads(raw_body)

            if company.shopify_debug:
                _logger.warning("Shopify webhook data (company=%s):\n%s",
                                company.name, pprint.pformat(data))
            if not data:
                return self._error_response("Missing JSON data", 400)

            # Idempotency: skip if this Shopify order id was already
            # turned into a sale.order for this company (duplicate
            # webhook subscriptions, Shopify retries, double-clicks).
            #
            # Key on `data['id']` (numeric, immutable) instead of
            # `data['name']` (display string like "CO#2859", editable
            # in Shopify admin and easy to collide with manually-created
            # sale orders).
            #
            # Defense in depth:
            #   1. pg_advisory_xact_lock serializes concurrent webhooks
            #      for the same order across workers/connections.
            #   2. The search-and-skip below short-circuits cheaply when
            #      the order already exists.
            #   3. The unique(shopify_order_id, company_id) constraint
            #      on sale_order is the final guarantee — even if the
            #      two checks above are bypassed, the DB rejects the
            #      duplicate INSERT.
            shopify_id = str(data.get('id') or '')
            if shopify_id:
                request.env.cr.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (_shopify_lock_key(company.id, shopify_id),),
                )
                existing = request.env['sale.order'].sudo().search([
                    ('shopify_order_id', '=', shopify_id),
                    ('company_id', '=', company.id),
                ], limit=1)
                if existing:
                    _logger.info(
                        "Shopify webhook: order %s (id=%s) already exists as %s — skipped.",
                        data.get('name'), shopify_id, existing.name,
                    )
                    return request.make_response(
                        json.dumps({
                            'status':   'skipped',
                            'reason':   'already_processed',
                            'order_id': existing.id,
                            'order_name': existing.name,
                        }) + '\n',
                        headers={'Content-Type': 'application/json'},
                    )

            cfg       = self._load_config(company)
            warehouse = request.env['stock.warehouse'].sudo().browse(cfg['warehouse_id']).exists()
            if not warehouse or warehouse.company_id != company:
                warehouse = request.env['stock.warehouse'].sudo().search(
                    [('company_id', '=', company.id)], limit=1
                )
            partner   = self._find_or_create_partner(data)

            try:
                order_date = parse_date(data.get('created_at'))
                order_date = order_date.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                order_date = datetime.now(timezone.utc).replace(tzinfo=None)

            # Wrap the create+confirm in a SAVEPOINT so we can recover
            # cleanly when the UNIQUE(shopify_order_id, company_id)
            # constraint fires under contention.
            #
            # Why this is needed even WITH the advisory lock:
            # Odoo runs requests under PostgreSQL ``REPEATABLE READ``,
            # which freezes each transaction's snapshot at BEGIN time.
            # A worker that started its transaction BEFORE the winner
            # committed will not see the winner's row when it re-runs
            # the search after acquiring the lock — its snapshot is
            # stale. It then attempts the INSERT and trips the UNIQUE.
            # The SAVEPOINT lets us catch that locally; the subsequent
            # ``cr.rollback()`` drops the stale snapshot so we can
            # re-query the winner's row and answer 200 ``skipped``.
            try:
                with request.env.cr.savepoint():
                    order = self._create_confirmed_order(
                        partner, order_date, warehouse, cfg, data, company
                    )
            except psycopg2.errors.UniqueViolation as e:
                if 'shopify_order_company_uniq' not in str(e):
                    raise
                request.env.cr.rollback()
                _logger.info(
                    "Shopify webhook: race lost on order id=%s (company=%s) — "
                    "duplicate caught by UNIQUE constraint.",
                    shopify_id, company.id,
                )
                existing = request.env['sale.order'].sudo().search([
                    ('shopify_order_id', '=', shopify_id),
                    ('company_id', '=', company.id),
                ], limit=1)
                return request.make_response(
                    json.dumps({
                        'status':     'skipped',
                        'reason':     'race_lost',
                        'order_id':   existing.id if existing else None,
                        'order_name': existing.name if existing else None,
                    }) + '\n',
                    headers={'Content-Type': 'application/json'},
                )

            order_ref = (
                f"{order.name} (id={order.id}, Shopify id={shopify_id}, "
                f"compañía id={company.id})"
            )

            if cfg['auto_invoice']:
                self._dispatch_invoice_trigger(order, cfg, data)

            if cfg['auto_delivery']:
                for pick in order.picking_ids:
                    self._notify_warehouse(pick, order, partner, data, cfg['warehouse_partner_ids'])

            return request.make_response(
                json.dumps({'status': 'success', 'order_id': order.id}) + '\n',
                headers={'Content-Type': 'application/json'},
            )

        except Exception as e:
            if order_ref:
                _logger.error(
                    "Error processing Shopify order: la orden de venta %s YA "
                    "QUEDÓ CREADA Y CONFIRMADA, pero un paso posterior falló "
                    "(factura, pago o notificación de entrega). Revise "
                    "manualmente la factura, el pago y la entrega. Error: %s",
                    order_ref, str(e), exc_info=True,
                )
            else:
                _logger.error("Error processing Shopify order: %s", str(e), exc_info=True)
            return self._error_response(str(e))
