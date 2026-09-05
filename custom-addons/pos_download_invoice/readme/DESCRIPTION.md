Out of the box, Odoo downloads the PDF invoice every time a Point of Sale order
marked as **Invoice** is validated. On a shop counter that PDF is usually noise:
the customer gets the printed receipt and the invoice is e-mailed or fetched
later from the backend.

This module adds a single checkbox, **Enable Download Invoice**, to the Point of
Sale settings. When it is off, the order is *still invoiced* exactly as before,
only the PDF download is skipped. When it is on, Odoo keeps its standard
behaviour and downloads the PDF. The option is stored on each point of sale, so
one shop can download and another one not.
