from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


CREDIBANCO_TERMINAL = "credibanco"
CREDIBANCO_SEQUENCE_PREFIX = "pos_api_credibanco.trx"
POS_USER_GROUP = "point_of_sale.group_pos_user"


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [
            (CREDIBANCO_TERMINAL, _("Credibanco"))
        ]

    pos_payment_terminal_name = fields.Char(
        string="Payment terminal name",
        help="Name the terminal expects as the prefix of every message, e.g. dataf001.",
    )
    pos_ip_host = fields.Char(
        string="Ip host POS",
        help="Host of the WebSocket bridge of the terminal, as seen by the "
             "cashier's browser. The browser connects to it directly.",
    )
    pos_websocket_port = fields.Char(
        string="Payment terminal port",
        default="8080",
    )
    # The cash register number (message position 42) is *not* configured here.
    # Credibanco's certification of this integration is built on the value the
    # Odoo 17 module sent: the POS session id concatenated with the cashier id
    # (`sessionId + cashierId`), computed by the interface at charge time.  A
    # manual field was a migration deviation from that serialisation, so it was
    # removed; the number the terminal really received is still stored per payment
    # in pos.payment.credibanco_cash_register so anulación and recovery echo it.
    credibanco_timeout = fields.Integer(
        string="Terminal Timeout (s)",
        default=100,
        help="Seconds to wait for the terminal's answer. It must outlive the "
             "terminal bridge's own long timeout (tef.ini: LONG_TIMEOUT = 90 s), "
             "so the first one to give up is the device and the cashier sees its "
             "error instead of a browser-side one. Without a bound at all, a "
             "silent terminal would freeze the register.",
    )

    # Transaction numbers are drawn from a sequence per Credibanco payment
    # method, which is the natural scope of uniqueness for the terminal's
    # (cash register, transaction number) lookup. Note this does *not* claim that
    # a method is one physical terminal (pos.payment.method is linked to the
    # configs with a many2many, so the same method can be used by several).
    TRANSACTION_NUMBERS_BATCH = 25
    TRANSACTION_NUMBER_PADDING = 6

    # Message positions of the terminal protocol, classified by the tax GROUP
    # instead of by tax id: the ids of a chart of accounts are meaningless in
    # another company or after a re-installation, and the hardcoded 9/10/61 of
    # the Odoo 17 module silently became a withholding tax in a different chart.
    # Colombia: IVA -> 41, and the restaurant "IAC" is the group named INC
    # (Impuesto Nacional al Consumo) -> 82.  Withholdings (R ICA…, R IVA…) start
    # with "R ", so the prefix test leaves them out, and their negative amounts
    # must never reach the terminal.
    VAT_GROUP_PREFIX = "IVA"
    IAC_GROUP_PREFIX = "INC"

    def get_credibanco_tax_map(self):
        """``{tax_id: 'vat' | 'iac'}`` for the terminal message of this method.

        Exposed to the interface as one call per POS session: the browser knows
        the amounts of every order but must not guess which tax is IVA or INC
        from a translated display name.  Names are read with the language
        disabled so the classification does not depend on the cashier's locale.

        Taxes that belong to neither group (and every withholding) are absent
        from the map, and the interface refuses to build a message with an
        unclassified tax rather than sending zeroes to the acquirer.
        """
        self.ensure_one()
        if not self.env.user.has_group(POS_USER_GROUP):
            raise AccessError(_(
                "You don't have the access rights to get the Credibanco tax map."
            ))

        taxes = self.env["account.tax"].with_context(lang=False).search([
            ("type_tax_use", "=", "sale"),
            ("company_id", "in", [self.company_id.id, False]),
        ])
        tax_map = {}
        for tax in taxes:
            if tax.amount < 0 or tax.has_negative_factor:
                continue
            group_name = (tax.tax_group_id.name or "").strip().upper()
            if group_name.startswith(self.VAT_GROUP_PREFIX):
                tax_map[tax.id] = "vat"
            elif group_name.startswith(self.IAC_GROUP_PREFIX):
                tax_map[tax.id] = "iac"
        return tax_map

    @api.model
    def _load_pos_data_fields(self, config):
        """Expose the terminal settings to the Point of Sale interface.

        Odoo 19 replaced ``pos.session._loader_params_*`` by this hook, declared
        on the model owning the fields. Overriding the old one does not fail: the
        fields are simply never loaded and the interface ends up without host,
        port or terminal name, so no WebSocket is ever opened.
        """
        result = super()._load_pos_data_fields(config)
        for field in (
            "pos_payment_terminal_name",
            "pos_ip_host",
            "pos_websocket_port",
            "credibanco_timeout",
        ):
            if field not in result:
                result.append(field)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_credibanco_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_credibanco_vals(vals)
        return super().write(vals)

    def _normalize_credibanco_vals(self, vals):
        """Selecting the Credibanco terminal implies the terminal integration.

        ``use_payment_terminal`` is only editable when ``payment_method_type`` is
        ``terminal`` (``_compute_hide_use_payment_terminal``), so asking the
        operator to set both would be busywork and a source of half-configured
        methods.
        """
        if vals.get("use_payment_terminal") == CREDIBANCO_TERMINAL:
            vals["payment_method_type"] = "terminal"

    @api.constrains(
        "use_payment_terminal",
        "payment_method_type",
        "journal_id",
    )
    def _check_credibanco_terminal_settings(self):
        for method in self.filtered(
            lambda pm: pm.use_payment_terminal == CREDIBANCO_TERMINAL
        ):
            missing = [
                label
                for field, label in (
                    ("pos_payment_terminal_name", _("el nombre de la terminal")),
                    ("pos_ip_host", _("el host del datáfono")),
                    ("pos_websocket_port", _("el puerto")),
                )
                if not method[field]
            ]
            if missing:
                raise ValidationError(_(
                    "La terminal Credibanco está incompleta: falta %s.",
                    ", ".join(missing),
                ))
            if method.type == "cash":
                raise ValidationError(_(
                    "Un método de datáfono Credibanco no puede ser el método de "
                    "efectivo."
                ))

    def _credibanco_sequence_code(self):
        self.ensure_one()
        return f"{CREDIBANCO_SEQUENCE_PREFIX}.{self.id}"

    def _credibanco_transaction_sequence(self):
        """Sequence of transaction numbers of this payment method, created on use."""
        self.ensure_one()
        sequence = self.env["ir.sequence"].sudo().search(
            [("code", "=", self._credibanco_sequence_code())], limit=1
        )
        if not sequence:
            sequence = self.env["ir.sequence"].sudo().create({
                "name": _("Credibanco: números de transacción (%s)", self.display_name),
                "code": self._credibanco_sequence_code(),
                "number_next": 1,
                "number_increment": 1,
                "padding": self.TRANSACTION_NUMBER_PADDING,
                "company_id": self.company_id.id,
            })
        return sequence

    def reserve_credibanco_transaction_numbers(self, count=TRANSACTION_NUMBERS_BATCH):
        """Give the interface a block of transaction numbers to spend offline.

        Reserved in batches because the browser must keep charging when it loses
        the server: a terminal that is reachable but a server that is not is a
        normal situation on a shop network. When the block runs out offline the
        interface refuses the payment rather than repeating a number.

        The 6-digit padding is presentation only (a stable, readable reference on
        the ticket and on the acquirer report). The protocol limit is 10
        characters and the terminal bridge is the one that pads fields, so this
        method never truncates and never relies on the padding.
        """
        self.ensure_one()
        if not self.env.user.has_group(POS_USER_GROUP):
            raise AccessError(_(
                "You don't have the access rights to reserve Credibanco "
                "transaction numbers."
            ))
        if self.use_payment_terminal != CREDIBANCO_TERMINAL:
            raise UserError(_(
                "Only a Credibanco terminal method can reserve transaction numbers."
            ))
        count = max(1, min(int(count or self.TRANSACTION_NUMBERS_BATCH), 100))
        sequence = self._credibanco_transaction_sequence()
        return [sequence.next_by_id() for _ in range(count)]
