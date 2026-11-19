from odoo import api, models

# Amount-due fields that pos_settle_due adds to every customer loaded by the POS.
DUE_FIELDS = ("total_due", "invoices_amount_due", "pos_orders_amount_due")


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config):
        """Customers reach the POS without their amount due when the point of sale skips it.

        Computing it costs tens of seconds per customer with a large history (37.7 s for total_due of a
        default customer with 139,000 invoices, measured in staging), and it was computed for every
        customer loaded.  Without these fields pos_settle_due does not recompute the amount due after a
        sale paid with the customer account either (it only does it when the customer has it loaded).
        The module depends on pos_settle_due, so this runs after the fields are added.
        """
        fields_list = super()._load_pos_data_fields(config)
        if config and config.skip_partner_due:
            return [fname for fname in fields_list if fname not in DUE_FIELDS]
        return fields_list
