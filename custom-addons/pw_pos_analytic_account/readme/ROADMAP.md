- **The analytic fields are only visible with the "Analytic Accounting" group enabled.** This
  is standard Odoo behaviour, but without that group the setting does not appear at all and
  the module looks like it does nothing.
- **On session closing the analytic distribution is written on every line of the related
  moves**, receivable and cash lines included. That produces analytic items that offset each
  other (for example +67.48 and -67.48 on the receivable account). It is inherited behaviour
  from the previous version and it was kept on purpose; if you only want analytic on revenue
  lines, the analytic items of the balance-sheet accounts have to be filtered out in the
  analytic reports.
- The account is taken from the point of sale at the moment the session and the orders are
  created. Changing the analytic account of a point of sale does not rewrite the entries
  already posted.
- Combo section lines of an invoice (display lines, no amount) do not receive any analytic
  distribution.
- `static/description/icon.png` is 446x446 px, while the core modules use 100x100 px. It
  should be resized or replaced.
