from odoo import fields, models
from odoo.tools import SQL


class PosConfig(models.Model):
    _inherit = "pos.config"

    frequent_partners_by_store = fields.Boolean(
        string="Clientes frecuentes de esta caja",
        default=True,
        help="Al abrir la caja, el POS carga primero los clientes con más órdenes en esta caja en los "
             "últimos días indicados, en lugar de contar todas las órdenes de todas las tiendas.",
    )
    frequent_partners_days = fields.Integer(
        string="Días de historial",
        default=90,
        help="Días de órdenes con que se ordenan los clientes frecuentes de esta caja. "
             "0 = ranking estándar de Odoo.",
    )

    _frequent_partners_days_not_negative = models.Constraint(
        "CHECK (frequent_partners_days >= 0)",
        "Los días de historial de los clientes frecuentes no pueden ser negativos.",
    )

    def get_limited_partners_loading(self, offset=0):
        """Customers loaded by the POS, ranked by their orders in THIS point of sale over the last N days.

        The standard query (point_of_sale/models/pos_config.py) counts every POS order of the database
        on each call: on production data (850,000+ orders) that is several seconds every time the POS
        opens and every time the cashier scrolls the customer list, and the ranking mixes all stores.
        Same output as the standard method (list of 1-tuples, same limit and offset, every partner of
        the company after the ranked ones, by name), only the ranking changes.

        It replaces the query instead of calling super(): the default customer of
        pw_pos_default_customer, which also overrides this method, is added back here, on the first
        page only.  pw_pos_default_customer adds it to every page: the POS then receives limit + 1
        customers, moves its offset by limit + 1 (partner_list.js, getNewPartners) and one ranked
        customer per page is never loaded.  The first page is the one the POS loads when it opens
        (res.partner._load_pos_data_domain), so the default customer is always there.
        """
        if len(self) != 1 or not self.frequent_partners_by_store or self.frequent_partners_days <= 0:
            return super().get_limited_partners_loading(offset)
        # raw SQL: write pending ORM changes first (orders created in this same transaction)
        self.env["pos.order"].flush_model(["config_id", "partner_id", "date_order"])
        self.env["res.partner"].flush_model(["company_id", "name"])
        partner_ids = self.env.execute_query(SQL(
            """
            WITH pm AS (
                SELECT partner_id, count(*) AS order_count
                  FROM pos_order
                 WHERE config_id = %s
                   AND partner_id IS NOT NULL
                   AND date_order >= (now() AT TIME ZONE 'UTC') - make_interval(days => %s)
              GROUP BY partner_id
            )
            SELECT partner.id
              FROM res_partner AS partner
         LEFT JOIN pm ON partner.id = pm.partner_id
             WHERE partner.company_id = %s OR partner.company_id IS NULL
          ORDER BY COALESCE(pm.order_count, 0) DESC, partner.name
             LIMIT %s OFFSET %s
            """,
            self.id, self.frequent_partners_days, self.company_id.id, self._get_limited_partner_count(), offset,
        ))
        default_customer = self.pos_customer_id
        if not offset and default_customer and (default_customer.id,) not in partner_ids:
            partner_ids.append((default_customer.id,))
        return partner_ids
