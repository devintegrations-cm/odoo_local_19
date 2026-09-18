This module gives every point of sale an **Analytic Account** and lets it flow to the
accounting records the Point of Sale produces. Once the account is set on the shop, the
module writes the matching analytic distribution (100 % to that account) on the sale lines
of the session closing entry, on the stock expense and stock valuation lines of that entry,
and on the customer invoice when a POS order is invoiced. When the session is closed and
posted, every line of the moves related to the session carries the distribution.

The analytic account is also shown on the POS order, on its lines and on the POS session, so
the link between a register and its analytic account can be checked without opening the
journal entries. The module is entirely back office: nothing changes in the POS front end.
It works on Odoo 19.0, Community and Enterprise, and depends on `point_of_sale` and
`analytic`.
