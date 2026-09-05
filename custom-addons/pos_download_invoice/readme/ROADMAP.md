- The **Invoice** button on the POS order list (ticket screen) still downloads
  the PDF even when the checkbox is off. That path was never covered by this
  module, it behaved the same way in Odoo 17, so it is not a regression of the
  migration, but it is worth knowing before you rely on the setting.
- `static/description/icon.png` weighs about 900 KB and is 1024x1024 pixels,
  while Odoo core icons are 100x100. It should be replaced by a properly sized
  icon.
