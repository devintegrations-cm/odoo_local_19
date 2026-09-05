====================
POS Download Invoice
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

Out of the box, Odoo downloads the PDF invoice every time a Point of Sale order
marked as **Invoice** is validated. On a shop counter that PDF is usually noise:
the customer gets the printed receipt and the invoice is e-mailed or fetched
later from the backend.

This module adds a single checkbox, **Enable Download Invoice**, to the Point of
Sale settings. When it is off, the order is *still invoiced* exactly as before,
only the PDF download is skipped. When it is on, Odoo keeps its standard
behaviour and downloads the PDF. The option is stored on each point of sale, so
one shop can download and another one not.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to *Point of Sale > Configuration > Settings* (or *Settings > Point of
Sale*), pick the point of sale at the top of the page, scroll to the
**Accounting** block and tick **Enable Download Invoice**. Press **Save**.

Notes about this setting:

- The checkbox is **unset by default**: after installing, no PDF is downloaded
  on validation until you enable it.
- The setting belongs to **each point of sale**, not to the company. Repeat it
  for every shop that needs it.
- After saving, reloading the POS screen is **not enough**: you have to enter
  the POS again from the backend (*Continue Selling* / *Open Register*) so the
  new configuration is loaded.

Usage
=====

Nothing changes for the cashier. Take an order, press **Payment**, choose a
customer, leave the **Invoice** button active and validate. The invoice is
created either way; the PDF download is what the setting controls. The same
applies to the quick payment flow.

The checkbox lives in the **Accounting** block of the Point of Sale settings:

.. figure:: ../static/description/01_configuration.png
   :alt: Enable Download Invoice checkbox in the Point of Sale settings, Accounting block

   Enable Download Invoice checkbox in the Point of Sale settings, Accounting block

And this is the payment screen with the **Invoice** button active, right before
validating the order:

.. figure:: ../static/description/02_payment_screen.png
   :alt: POS payment screen with the Invoice button active, before validating the order

   POS payment screen with the Invoice button active, before validating the order

The setting only controls the **download**. The invoice itself is always created
for orders marked as Invoice, and stays available in Accounting and in the
customer portal.

Known issues / Roadmap
======================

- The **Invoice** button on the POS order list (ticket screen) still downloads
  the PDF even when the checkbox is off. That path was never covered by this
  module, it behaved the same way in Odoo 17, so it is not a regression of the
  migration, but it is worth knowing before you rely on the setting.
- ``static/description/icon.png`` weighs about 900 KB and is 1024x1024 pixels,
  while Odoo core icons are 100x100. It should be replaced by a properly sized
  icon.

Credits
=======

Authors
-------

- Desarrollo Libertario

Contributors
------------

- Desarrollo Libertario \<<regionalit@libertariocoffee.com>\>
