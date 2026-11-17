# -*- coding: utf-8 -*-
{
    'name': "Shopify Order Webhook",

    'summary': "Convert Shopify order webhooks into Odoo sales, invoices and payments (per-company).",

    'description': """
Shopify Order Webhook
=====================

HTTP endpoint that listens for Shopify `orders/create` (and similar)
webhooks and turns them into a confirmed sale order, an optional posted
invoice and an optional reconciled inbound payment in Odoo 19.

Features
--------
* Per-company configuration (each company has its own webhook URL,
  secret, warehouse, journal, mappings and responsible users).
* Mandatory HMAC-SHA256 signature verification (timing-safe);
  requests are rejected while the company has no secret.
* Idempotency by Shopify numeric order ``id`` + ``company_id``,
  enforced by a UNIQUE SQL constraint and a per-order advisory lock.
* Three invoice triggers: on order confirmation, on delivery
  validation, or after N hours via a scheduled action.
* Configurable mapping of Shopify ``source_name`` to ``crm.tag``.
* Configurable mapping of Shopify payment gateways to Odoo journals.
* Multi-company aware tax filtering on product lines.
* Email notifications to warehouse and accounting responsibles via
  ``message_notify`` (no permanent chatter footprint).

Configuration
-------------
``Settings → Sales → Shopify Connector`` after installation.

Webhook URL format
------------------
``{web.base.url}/shopify/order/<company_id>`` — point each Shopify
store to the URL of its target Odoo company.
    """,

    'author':     "Desarrollo Libertario",
    'maintainer': "Desarrollo Libertario",
    'company':    "Libertario Coffee Roasters",
    'website':    "https://www.libertariocoffee.com",
    'support':    "regionalit@libertariocoffee.com",
    'license':    'LGPL-3',

    # Check https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list of categories.
    'category': 'Sales/Sales',
    'version':  '19.0.1.9.3',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'sale',
        'sale_management',
        'sale_stock',
        'account',
        'stock',
        'mail',
        'crm',
        'l10n_co_edi_jorels',
    ],

    # external Python packages required (already bundled with Odoo,
    # listed for clarity).
    'external_dependencies': {
        'python': ['python-dateutil', 'requests'],
    },

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'report/report_shopify_delivery_label.xml',
        'views/shopify_order_simulation_views.xml',
        'views/shopify_order_import_views.xml',
        'views/shopify_product_mapping_views.xml',
        'views/res_config_settings_views.xml',
    ],

    # static/description/index.html is used automatically by Odoo for
    # the app description; static/description/icon.png is the listing
    # icon (place a PNG there when ready).
    'images': [
        'static/description/icon.png',
    ],

    'application':  False,
    'installable':  True,
    'auto_install': False,
}
