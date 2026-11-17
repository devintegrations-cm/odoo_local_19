import json
import logging
from datetime import timedelta

from odoo import models, fields, _
from odoo.exceptions import UserError

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

_logger = logging.getLogger(__name__)


# GraphQL query for the most recent orders. Mirrors the fields the webhook
# controller consumes from the REST payload so the mapper can feed the same
# order-building logic. Customer name is derived from the order addresses to
# avoid requiring the 'read_customers' scope.
_SHOPIFY_LAST_ORDERS_QUERY = """
query($limit: Int!) {
  orders(first: $limit, reverse: true, sortKey: CREATED_AT) {
    edges {
      node {
        id
        name
        createdAt
        note
        email
        phone
        sourceName
        paymentGatewayNames
        totalPriceSet { shopMoney { amount currencyCode } }
        billingAddress {
          firstName lastName company countryCodeV2
          address1 address2 city zip
        }
        shippingAddress {
          firstName lastName name company countryCodeV2
          address1 address2 city province zip phone country
        }
        lineItems(first: 100) {
          edges {
            node {
              sku name title variantTitle quantity
              variant { id }
              product { id }
              originalUnitPriceSet { shopMoney { amount } }
              totalDiscountSet { shopMoney { amount } }
            }
          }
        }
        shippingLines(first: 20) {
          edges {
            node {
              originalPriceSet { shopMoney { amount } }
              discountAllocations { allocatedAmountSet { shopMoney { amount } } }
            }
          }
        }
      }
    }
  }
}
"""


# GraphQL query for the product catalog, paginated by product cursor. Each
# variant becomes one mapping row (a Shopify variant ≈ an Odoo product.product).
_SHOPIFY_PRODUCTS_QUERY = """
query($cursor: String) {
  products(first: 50, after: $cursor, sortKey: TITLE) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        status
        variants(first: 100) {
          edges {
            node { id title sku price }
          }
        }
      }
    }
  }
}
"""


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    shopify_enable_webhook = fields.Boolean(
        string="Enable Shopify Webhook",
        help="Enable the Shopify webhook integration for this company.",
    )

    shopify_webhook_secret = fields.Char(
        string='Webhook Secret',
        groups='base.group_system',
        help=(
            "Secret key shown in Shopify Admin → Settings → Notifications → "
            "Webhooks. Every incoming request is verified against the "
            "X-Shopify-Hmac-SHA256 header; while it is empty the webhook "
            "rejects all requests (401)."
        ),
    )

    shopify_debug = fields.Boolean(
        string="Shopify Debug Logging",
        help=(
            "When enabled, the full Shopify webhook payload is logged at "
            "WARNING level. Keep this off in production — payloads contain "
            "customer PII (name, address, phone, email)."
        ),
    )

    # ------------------------------------------------------------------
    # Admin API (outbound query — used by the simulation button)
    # ------------------------------------------------------------------

    shopify_shop_url = fields.Char(
        string='Shopify Store Domain',
        help=(
            "Dominio .myshopify.com de la tienda, p. ej. "
            "'mitienda.myshopify.com'. Lo encuentras en Shopify Admin → "
            "Settings → Domains (usa el dominio interno *.myshopify.com, no "
            "el dominio público)."
        ),
    )

    shopify_enable_api = fields.Boolean(
        string='Enable Shopify API',
        help=(
            "Activa la configuración de credenciales de la Admin API para "
            "consultar órdenes y productos desde Odoo (simulación, importación "
            "manual y mapeo de productos)."
        ),
    )

    shopify_client_id = fields.Char(
        string='Client ID',
        help=(
            "Client ID (API key) de la app del Dev Dashboard de Shopify. "
            "Junto con el Client Secret se usa para generar automáticamente "
            "un token de acceso mediante el grant 'client_credentials' "
            "(válido 24 h). Dev Dashboard → tu app → API credentials."
        ),
    )

    shopify_client_secret = fields.Char(
        string='Client Secret',
        groups='base.group_system',
        help=(
            "Client Secret de la app del Dev Dashboard. Se usa con el Client "
            "ID para obtener el token de acceso (grant 'client_credentials'). "
            "Manténlo en secreto: permite generar tokens con los scopes de "
            "la app."
        ),
    )

    shopify_admin_api_token = fields.Char(
        string='Admin API Access Token (manual)',
        groups='base.group_system',
        help=(
            "Token de acceso de la Admin API ('shpat_...') ingresado a mano. "
            "Opcional: úsalo solo si tienes una app custom heredada con un "
            "token fijo. Si están configurados Client ID y Client Secret, "
            "estos tienen prioridad y este campo se ignora."
        ),
    )

    # Internal cache for the client_credentials token (not user-entered).
    shopify_access_token = fields.Char(
        string='Cached Access Token',
        groups='base.group_system',
        help="Token generado automáticamente vía client_credentials (caché).",
    )

    shopify_token_expiry = fields.Datetime(
        string='Token Expiry',
        help="Vencimiento del token cacheado generado vía client_credentials.",
    )

    shopify_api_version = fields.Char(
        string='Admin API Version',
        default='2024-10',
        help=(
            "Versión de la Admin API a usar en las llamadas GraphQL, con "
            "formato AAAA-MM (p. ej. '2024-10'). Usa una versión estable "
            "vigente; ver https://shopify.dev/docs/api/usage/versioning."
        ),
    )

    # ------------------------------------------------------------------
    # Sales
    # ------------------------------------------------------------------

    shopify_default_price_list_id = fields.Many2one(
        'product.pricelist',
        string='Default Price List',
    )

    shopify_price_tax_mode = fields.Selection(
        selection=[
            ('included', 'Impuestos incluidos'),
            ('excluded', 'Impuestos no incluidos'),
        ],
        string='Precios de Shopify',
        default='included',
        required=True,
        help=(
            "Define cómo vienen los precios de las líneas en el payload de "
            "Shopify:\n"
            "- Impuestos incluidos: el precio ya contiene el impuesto (p. ej. "
            "IVA). Es lo habitual en tiendas Shopify.\n"
            "- Impuestos no incluidos: el precio es neto, sin impuesto.\n\n"
            "Según esta opción y la configuración del impuesto en Odoo "
            "(precio incluido o no), el conector ajusta el price_unit para que "
            "el total de la orden coincida con el de Shopify."
        ),
    )

    shopify_account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
    )

    shopify_default_tag_id = fields.Many2one(
        'crm.tag',
        string='Default Tag',
    )

    shopify_default_user_id = fields.Many2one(
        'res.users',
        string='Default Salesperson',
        help=(
            "Vendedor (user_id) asignado por defecto a las órdenes de venta "
            "creadas desde el webhook de Shopify. Si se deja vacío, Odoo usa "
            "su comportamiento por defecto."
        ),
    )

    shopify_default_team_id = fields.Many2one(
        'crm.team',
        string='Default Sales Team',
        help=(
            "Equipo de ventas (team_id) asignado por defecto a las órdenes de "
            "venta creadas desde el webhook de Shopify. Si se deja vacío, Odoo "
            "usa su comportamiento por defecto."
        ),
    )

    shopify_shipping_product_id = fields.Many2one(
        'product.product',
        string='Default Shipping Product',
        help=(
            "Producto usado para registrar el costo de envío de la orden de "
            "Shopify como una línea adicional en la orden de venta. El importe "
            "se toma de 'shipping_lines' del payload. Si se deja vacío, el "
            "costo de envío no se agrega a la orden."
        ),
    )

    shopify_source_tag_mapping_ids = fields.One2many(
        'shopify.source.tag.mapping',
        'company_id',
        string='Source → Tag Mapping',
    )

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    shopify_auto_delivery = fields.Boolean(
        string='Auto Delivery Tracking',
    )

    shopify_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
    )

    shopify_warehouse_responsible_ids = fields.Many2many(
        'res.users',
        relation='shopify_company_warehouse_responsible_rel',
        column1='company_id',
        column2='user_id',
        string='Warehouse Responsibles',
    )

    # Configuración de impresión de etiquetas de entrega
    shopify_label_page_width = fields.Integer(
        string='Ancho hoja etiqueta (mm)',
        default=140,
    )
    shopify_label_page_height = fields.Integer(
        string='Alto hoja etiqueta (mm)',
        default=216,
    )
    shopify_label_rows = fields.Integer(
        string='Filas de etiquetas por hoja',
        default=3,
    )
    shopify_label_cols = fields.Integer(
        string='Columnas de etiquetas por hoja',
        default=1,
    )

    # ------------------------------------------------------------------
    # Accounting
    # ------------------------------------------------------------------

    shopify_auto_invoice = fields.Boolean(
        string='Auto Invoice',
    )

    shopify_invoice_trigger = fields.Selection(
        selection=[
            ('on_confirm',  'Al confirmar la orden de venta'),
            ('on_delivery', 'Al validar la entrega de inventario'),
            ('delayed',     'Después de un tiempo de creada la orden'),
        ],
        string='Invoice Trigger',
        default='on_confirm',
    )

    shopify_invoice_delay_hours = fields.Integer(
        string='Invoice Delay (hours)',
        default=24,
    )

    shopify_account_journal_id = fields.Many2one(
        'account.journal',
        string='Invoice Journal',
    )

    shopify_accounting_responsible_ids = fields.Many2many(
        'res.users',
        relation='shopify_company_accounting_responsible_rel',
        column1='company_id',
        column2='user_id',
        string='Accounting Responsibles',
    )

    shopify_auto_payment = fields.Boolean(
        string='Auto Payment',
    )

    shopify_payment_mapping_ids = fields.One2many(
        'shopify.payment.journal.mapping',
        'company_id',
        string='Payment Mapping',
    )

    # ------------------------------------------------------------------
    # Admin API client (outbound queries — simulation & manual import)
    # ------------------------------------------------------------------

    def _shopify_normalize_shop(self):
        """Return the bare ``*.myshopify.com`` domain for this company."""
        self.ensure_one()
        shop = (self.shopify_shop_url or '').strip()
        return shop.replace('https://', '').replace('http://', '').strip('/')

    def _shopify_get_access_token(self):
        """Return a valid Admin API access token for this company.

        Resolution order:
          1. Client ID + Client Secret → generate a token via the
             ``client_credentials`` grant, cached on the company until it
             expires (Shopify tokens last ~24 h).
          2. Manual ``shopify_admin_api_token`` (legacy custom apps).

        Raises ``UserError`` with an actionable message when neither is
        usable.
        """
        self.ensure_one()
        shop = self._shopify_normalize_shop()
        if not shop:
            raise UserError(_(
                "Configura el dominio de la tienda (*.myshopify.com) antes "
                "de consultar Shopify."
            ))

        # Los campos secretos son solo de ``base.group_system``; la
        # sincronización de pedidos/productos la lanzan también vendedores,
        # así que las credenciales se leen con sudo (nunca se devuelven al
        # cliente ni se registran en el log).
        company_sudo = self.sudo()
        client_id = (company_sudo.shopify_client_id or '').strip()
        client_secret = (company_sudo.shopify_client_secret or '').strip()

        # 1) client_credentials grant (Dev Dashboard apps).
        if client_id and client_secret:
            now = fields.Datetime.now()
            cached = company_sudo.shopify_access_token
            expiry = company_sudo.shopify_token_expiry
            # Reuse the cached token while it still has a safe margin left.
            if cached and expiry and expiry > now + timedelta(minutes=5):
                return cached

            if requests is None:
                raise UserError(_(
                    "La librería Python 'requests' no está disponible en el "
                    "servidor; es necesaria para consultar la API de Shopify."
                ))

            token_url = f"https://{shop}/admin/oauth/access_token"
            try:
                resp = requests.post(
                    token_url,
                    data={
                        'grant_type':    'client_credentials',
                        'client_id':     client_id,
                        'client_secret': client_secret,
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=30,
                )
            except requests.RequestException as e:
                raise UserError(_("No se pudo conectar con Shopify: %s") % e)

            if resp.status_code in (401, 403):
                raise UserError(_(
                    "Shopify rechazó el Client ID / Client Secret (%s). "
                    "Verifica que sean correctos y que la app del Dev "
                    "Dashboard esté instalada en esta tienda."
                ) % resp.status_code)
            if resp.status_code != 200:
                raise UserError(_(
                    "Shopify no devolvió el token (código %s):\n%s"
                ) % (resp.status_code, resp.text[:500]))

            try:
                body = resp.json()
            except ValueError:
                raise UserError(_(
                    "Respuesta no válida al solicitar el token:\n%s"
                ) % resp.text[:500])

            token = body.get('access_token')
            if not token:
                raise UserError(_(
                    "Shopify no incluyó 'access_token' en la respuesta:\n%s"
                ) % json.dumps(body, ensure_ascii=False)[:500])

            expires_in = int(body.get('expires_in') or 0)
            self.sudo().write({
                'shopify_access_token': token,
                'shopify_token_expiry': now + timedelta(
                    seconds=expires_in) if expires_in else False,
            })
            return token

        # 2) Manual token fallback (legacy custom apps).
        if company_sudo.shopify_admin_api_token:
            return company_sudo.shopify_admin_api_token

        raise UserError(_(
            "Configura el Client ID y Client Secret de la app del Dev "
            "Dashboard (o, alternativamente, un Admin API Access Token "
            "manual) en Ajustes → Ventas → Shopify Connector antes de "
            "consultar Shopify."
        ))

    def _shopify_fetch_last_orders(self, limit=10):
        """Query the Shopify Admin GraphQL API for the most recent orders.

        Returns a list of payload dicts already shaped like the webhook REST
        body (see ``_shopify_gql_order_to_payload``). Raises ``UserError``
        with an actionable message on any misconfiguration or API failure.
        """
        self.ensure_one()
        if requests is None:
            raise UserError(_(
                "La librería Python 'requests' no está disponible en el "
                "servidor; es necesaria para consultar la API de Shopify."
            ))

        shop = self._shopify_normalize_shop()
        version = (self.shopify_api_version or '2024-10').strip()
        token = self._shopify_get_access_token()

        url = f"https://{shop}/admin/api/{version}/graphql.json"
        try:
            resp = requests.post(
                url,
                json={'query': _SHOPIFY_LAST_ORDERS_QUERY,
                      'variables': {'limit': limit}},
                headers={
                    'X-Shopify-Access-Token': token,
                    'Content-Type': 'application/json',
                },
                timeout=30,
            )
        except requests.RequestException as e:
            raise UserError(_("No se pudo conectar con Shopify: %s") % e)

        if resp.status_code == 401:
            raise UserError(_(
                "Shopify rechazó las credenciales (401). Verifica el token / "
                "Client ID y que la app tenga el scope 'read_orders'."
            ))
        if resp.status_code != 200:
            raise UserError(_(
                "Shopify respondió con código %s:\n%s"
            ) % (resp.status_code, resp.text[:500]))

        try:
            payload = resp.json()
        except ValueError:
            raise UserError(_(
                "Respuesta no válida de Shopify (no es JSON):\n%s"
            ) % resp.text[:500])

        errors = payload.get('errors')
        orders_root = (payload.get('data') or {}).get('orders')

        # Field-level denials (e.g. a missing optional scope) still return
        # the rest of the data. Only abort when there is no usable data;
        # otherwise log the warnings and continue with what we got.
        if errors and not orders_root:
            raise UserError(_(
                "Error GraphQL de Shopify:\n%s"
            ) % json.dumps(errors, ensure_ascii=False)[:800])
        if errors:
            _logger.warning("Shopify GraphQL devolvió advertencias: %s",
                            json.dumps(errors, ensure_ascii=False)[:800])

        edges = (orders_root or {}).get('edges') or []
        return [self._shopify_gql_order_to_payload(e['node']) for e in edges]

    @staticmethod
    def _shopify_gid_to_id(gid):
        """Extract the numeric id from a Shopify GID (``gid://.../Order/123``)."""
        gid = gid or ''
        return gid.rsplit('/', 1)[-1] if gid else ''

    @staticmethod
    def _shopify_gql_order_to_payload(node):
        """Translate one GraphQL order node into the REST-shaped webhook dict."""

        def money(money_set):
            return float(((money_set or {}).get('shopMoney') or {}).get('amount') or 0)

        def gid_id(gid):
            return gid.rsplit('/', 1)[-1] if gid else ''

        bill = node.get('billingAddress') or {}
        ship = node.get('shippingAddress') or {}
        # Derive the customer name from the order's own addresses so the
        # query does not require the 'read_customers' scope.
        cust = {
            'firstName': bill.get('firstName') or ship.get('firstName'),
            'lastName':  bill.get('lastName') or ship.get('lastName'),
        }

        line_items = []
        for edge in ((node.get('lineItems') or {}).get('edges') or []):
            n = edge.get('node') or {}
            line_items.append({
                'sku':            n.get('sku'),
                'name':           n.get('name'),
                'title':          n.get('title'),
                'variant_title':  n.get('variantTitle'),
                'quantity':       n.get('quantity'),
                'variant_id':     gid_id((n.get('variant') or {}).get('id')),
                'product_id':     gid_id((n.get('product') or {}).get('id')),
                'price':          money(n.get('originalUnitPriceSet')),
                'total_discount': money(n.get('totalDiscountSet')),
            })

        shipping_lines = []
        for edge in ((node.get('shippingLines') or {}).get('edges') or []):
            n = edge.get('node') or {}
            shipping_lines.append({
                'price': money(n.get('originalPriceSet')),
                'discount_allocations': [
                    {'amount': money(d.get('allocatedAmountSet'))}
                    for d in (n.get('discountAllocations') or [])
                ],
            })

        gid = node.get('id') or ''
        numeric_id = gid.rsplit('/', 1)[-1] if gid else ''
        total_set = (node.get('totalPriceSet') or {}).get('shopMoney') or {}

        return {
            'id':                    numeric_id,
            'name':                  node.get('name'),
            'created_at':            node.get('createdAt'),
            'note':                  node.get('note'),
            'email':                 node.get('email'),
            'phone':                 node.get('phone'),
            'source_name':           node.get('sourceName'),
            'payment_gateway_names': node.get('paymentGatewayNames') or [],
            'total_price':           float(total_set.get('amount') or 0),
            'currency_code':         total_set.get('currencyCode') or '',
            'customer': {
                'first_name': cust.get('firstName'),
                'last_name':  cust.get('lastName'),
            },
            'billing_address': {
                'company':      bill.get('company'),
                'country_code': bill.get('countryCodeV2'),
                'address1':     bill.get('address1'),
                'address2':     bill.get('address2'),
                'city':         bill.get('city'),
                'zip':          bill.get('zip'),
            },
            'shipping_address': {
                'name':         ship.get('name'),
                'company':      ship.get('company'),
                'country_code': ship.get('countryCodeV2'),
                'address1':     ship.get('address1'),
                'address2':     ship.get('address2'),
                'city':         ship.get('city'),
                'province':     ship.get('province'),
                'zip':          ship.get('zip'),
                'phone':        ship.get('phone'),
                'country':      ship.get('country'),
            },
            'line_items':    line_items,
            'shipping_lines': shipping_lines,
        }

    def _shopify_fetch_products(self, max_products=1000):
        """Return the Shopify catalog flattened to one dict per variant.

        Paginates over products by cursor until exhausted or ``max_products``
        is reached (safety cap). Each entry carries the parent product info
        plus the variant id/sku/price so it can be mapped to a product.product.
        """
        self.ensure_one()
        if requests is None:
            raise UserError(_(
                "La librería Python 'requests' no está disponible en el "
                "servidor; es necesaria para consultar la API de Shopify."
            ))

        shop = self._shopify_normalize_shop()
        version = (self.shopify_api_version or '2024-10').strip()
        token = self._shopify_get_access_token()
        url = f"https://{shop}/admin/api/{version}/graphql.json"
        headers = {
            'X-Shopify-Access-Token': token,
            'Content-Type': 'application/json',
        }

        variants = []
        cursor = None
        fetched = 0
        while fetched < max_products:
            try:
                resp = requests.post(
                    url,
                    json={'query': _SHOPIFY_PRODUCTS_QUERY,
                          'variables': {'cursor': cursor}},
                    headers=headers,
                    timeout=30,
                )
            except requests.RequestException as e:
                raise UserError(_("No se pudo conectar con Shopify: %s") % e)

            if resp.status_code == 401:
                raise UserError(_(
                    "Shopify rechazó las credenciales (401). Verifica el token "
                    "/ Client ID y que la app tenga el scope 'read_products'."
                ))
            if resp.status_code != 200:
                raise UserError(_(
                    "Shopify respondió con código %s:\n%s"
                ) % (resp.status_code, resp.text[:500]))

            try:
                payload = resp.json()
            except ValueError:
                raise UserError(_(
                    "Respuesta no válida de Shopify (no es JSON):\n%s"
                ) % resp.text[:500])

            errors = payload.get('errors')
            products_root = (payload.get('data') or {}).get('products')
            if errors and not products_root:
                raise UserError(_(
                    "Error GraphQL de Shopify:\n%s"
                ) % json.dumps(errors, ensure_ascii=False)[:800])
            if errors:
                _logger.warning("Shopify products: advertencias: %s",
                                json.dumps(errors, ensure_ascii=False)[:800])

            for edge in (products_root or {}).get('edges', []):
                node = edge.get('node') or {}
                fetched += 1
                product_gid = self._shopify_gid_to_id(node.get('id'))
                title = node.get('title')
                for v_edge in ((node.get('variants') or {}).get('edges') or []):
                    v = v_edge.get('node') or {}
                    variants.append({
                        'product_id':    product_gid,
                        'variant_id':    self._shopify_gid_to_id(v.get('id')),
                        'title':         title,
                        'variant_title': v.get('title'),
                        'sku':           v.get('sku'),
                        'price':         float(v.get('price') or 0),
                        'status':        node.get('status'),
                    })

            page_info = (products_root or {}).get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')

        return variants
