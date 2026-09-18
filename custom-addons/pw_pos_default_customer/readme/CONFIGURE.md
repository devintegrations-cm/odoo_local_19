- Go to *Point of Sale › Configuration › Settings*.
- Pick the shop in the **Point of Sale** selector at the top.
- Fill **Default Customer** in the *PoS Interface* block.
- Press **Save**.

The setting is stored on the point of sale (`pos.config`), not globally, so it has to be set
on each shop that needs it. Shops without a Default Customer keep behaving exactly like
standard Odoo.

After changing the setting, reopen the Point of Sale from the backend (*Open Register* /
*Continue Selling*). Reloading the POS tab is not enough for the new value to reach the
session.
