====================
POS Default Customer
====================

..
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! Generado por .claude/scripts/gen_readme.py          !!
   !! Los cambios se sobrescriben: editar readme/*.md     !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1| |badge2|

This module lets you set a default customer per Point of Sale. Every new order is created
with that customer already assigned, so the cashier does not have to open the customer list
for the usual walk-in sale, and the receipt and the resulting POS order are attributed to
that partner.

The default is only a starting point: the cashier can replace the customer at any time, as
usual, and that choice stays on the order. The module also makes sure the configured customer
is always loaded into the POS session. It works on Odoo 19.0, Community and Enterprise.

**Table of contents**

.. contents::
   :local:

Configuration
=============

- Go to *Point of Sale › Configuration › Settings*.
- Pick the shop in the **Point of Sale** selector at the top.
- Fill **Default Customer** in the *PoS Interface* block.
- Press **Save**.

The setting is stored on the point of sale (``pos.config``), not globally, so it has to be set
on each shop that needs it. Shops without a Default Customer keep behaving exactly like
standard Odoo.

After changing the setting, reopen the Point of Sale from the backend (*Open Register* /
*Continue Selling*). Reloading the POS tab is not enough for the new value to reach the
session.

Usage
=====

The customer is picked in the Point of Sale settings, in the *PoS Interface* block.

.. figure:: ../static/description/01_configuration.png
   :alt: Default Customer field in the Point of Sale settings

   Default Customer field in the Point of Sale settings

**A new order already has the customer.** Open the Point of Sale and start an order: the
customer button at the bottom of the ticket already shows the configured customer. Nobody
opened the customer list.

.. figure:: ../static/description/02_new_order.png
   :alt: New POS order with the default customer already assigned

   New POS order with the default customer already assigned

**The cashier can still change it.** Tapping the customer button opens the usual customer
list; once another customer is selected, that choice stays on the order — adding more lines
does not bring the default customer back.

.. figure:: ../static/description/03_manual_override.png
   :alt: The cashier replaces the default customer by hand

   The cashier replaces the default customer by hand

Known issues / Roadmap
======================

- **The default customer must be among the contacts the POS loads.** A POS session only loads
  about 100 partners (the most used ones), so a customer outside that list cannot be resolved
  in the session. This module forces the configured customer into that list; without it the
  order would simply start with no customer and no visible symptom at all.
- **Refund orders inherit the default customer too.** A refund created from the Orders screen
  starts with the configured customer, so the refund may end up attributed to the generic
  customer instead of the original buyer. Check the customer before validating a refund. This
  is the inherited behaviour of the feature, not something the migration changed.
- Saving the Settings page may log a server warning about ``pos_customer_id`` not being properly
  saved. The value *is* saved (through the related field); the warning comes from the generic
  ``pos_*`` prefix handling in Odoo's POS settings and is harmless.
- ``static/description/icon.png`` is 512x512 px, while the core modules use 100x100 px. It
  should be resized or replaced.
- The help text shown under the **Default Customer** setting is written in Spanish
  ("Cliente asignado automaticamente a cada pedido nuevo", in ``views/pos_config_view.xml``)
  inside an otherwise English module. It should be written in English and translated through
  the ``i18n`` files.

Credits
=======

Authors
-------

- Preway IT Solutions

Contributors
------------

- Preway IT Solutions \<<prewayit@gmail.com>\>
