import json

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosApiCredibanco(TransactionCase):
    """Terminal configuration, the fields the interface needs, and the answer.

    The wire protocol itself is exercised against a terminal (real or simulated);
    what is covered here is everything around it: the method must be
    configurable and refuse to be half-configured, the settings must reach the
    interface, and a payment carrying a terminal answer must end up readable and
    auditable in the database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.cash_journal = cls.env["account.journal"].create({
            "name": "Cash Credibanco Test",
            "type": "cash",
            "code": "CCRD",
            "company_id": cls.company.id,
        })
        cls.bank_journal = cls.env["account.journal"].create({
            "name": "Bank Credibanco Test",
            "type": "bank",
            "code": "BNCB",
            "company_id": cls.company.id,
        })
        cls.payment_method = cls.env["pos.payment.method"].create(
            cls._method_vals()
        )
        cls.config = cls.env["pos.config"].create({
            "name": "Test POS Credibanco",
            "module_pos_restaurant": False,
            "journal_id": cls.cash_journal.id,
            "payment_method_ids": [(6, 0, [cls.payment_method.id])],
        })

    @classmethod
    def _method_vals(cls, **overrides):
        vals = {
            "name": "Credibanco Test",
            "journal_id": cls.bank_journal.id,
            "use_payment_terminal": "credibanco",
            "pos_payment_terminal_name": "dataf001",
            "pos_ip_host": "192.168.1.50",
            "pos_websocket_port": "8080",
        }
        vals.update(overrides)
        return vals

    def _payment(self, **vals):
        """A payment on a real order: pos.payment requires an order in Odoo 19."""
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        amount = vals.pop("amount", 1000.0)
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "user_id": self.env.uid,
            "amount_tax": 0.0,
            "amount_total": amount,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "payment_ids": [(0, 0, dict(
                {"amount": amount, "payment_method_id": self.payment_method.id},
                **vals,
            ))],
        })
        return order.payment_ids

    def _answer(self, **overrides):
        """A terminal answer as the interface stores it: position -> value."""
        values = {
            "0": "00",
            "1": "A12345",
            "2": "TX999",
            "40": "25000",
            "41": "3991",
            "42": "dataf001",
            "53": "1001",
            "81": "2000",
            "82": "2500",
            "83": "Osmar",
        }
        values.update(overrides)
        return values

    # ------------------------------------------------------------------
    # Method configuration
    # ------------------------------------------------------------------

    def test_credibanco_is_offered_as_a_terminal(self):
        selection = self.env["pos.payment.method"]._get_payment_terminal_selection()

        self.assertIn("credibanco", [key for key, _label in selection])

    def test_terminal_choice_forces_the_terminal_integration(self):
        """use_payment_terminal is only editable with payment_method_type=terminal."""
        self.assertEqual(self.payment_method.payment_method_type, "terminal")

        method = self.env["pos.payment.method"].create(
            self._method_vals(
                name="Credibanco Cambiado",
                use_payment_terminal=False,
            )
        )
        method.write({"use_payment_terminal": "credibanco"})

        self.assertEqual(method.payment_method_type, "terminal")

    def test_incomplete_terminal_config_is_refused(self):
        for field in (
            "pos_payment_terminal_name",
            "pos_ip_host",
            "pos_websocket_port",
        ):
            with self.assertRaises(ValidationError):
                self.env["pos.payment.method"].create(
                    self._method_vals(**{field: False})
                )

    def test_cash_method_cannot_be_a_terminal(self):
        with self.assertRaises(ValidationError):
            self.env["pos.payment.method"].create(
                self._method_vals(type="cash", journal_id=self.cash_journal.id)
            )

    def test_timeout_has_a_bounded_default(self):
        """Without a bound, a silent terminal would freeze the register."""
        self.assertGreater(self.payment_method.credibanco_timeout, 0)
        self.assertLessEqual(self.payment_method.credibanco_timeout, 300)

    # ------------------------------------------------------------------
    # What the interface loads
    # ------------------------------------------------------------------

    TERMINAL_FIELDS = (
        "pos_payment_terminal_name",
        "pos_ip_host",
        "pos_websocket_port",
        "credibanco_timeout",
    )

    def test_terminal_fields_are_loaded_for_the_pos(self):
        fields = self.payment_method._load_pos_data_fields(self.config)

        for field in self.TERMINAL_FIELDS:
            self.assertIn(field, fields)

    def test_loading_twice_does_not_duplicate_fields(self):
        first = self.payment_method._load_pos_data_fields(self.config)
        second = self.payment_method._load_pos_data_fields(self.config)

        for field in self.TERMINAL_FIELDS:
            self.assertEqual(first.count(field), 1)
            self.assertEqual(second.count(field), 1)

    def test_core_fields_survive_the_extension(self):
        fields = self.payment_method._load_pos_data_fields(self.config)

        for field in ("name", "is_cash_count", "use_payment_terminal", "type"):
            self.assertIn(field, fields)

    # ------------------------------------------------------------------
    # The terminal answer becomes data
    # ------------------------------------------------------------------

    def test_answer_is_materialized_as_readable_rows(self):
        payment = self._payment(credibanco_response=json.dumps(self._answer()), amount=27000.0)

        values = {
            row.credibancoField: row.credibancoValue
            for row in payment.credibanco_extra_info
        }

        self.assertTrue(values, "the answer must become readable rows")
        self.assertEqual(values.get("Código de autorización"), "A12345")
        self.assertEqual(values.get("Identificador Transacción"), "TX999")
        self.assertEqual(payment.credibanco_approval_number, "A12345")
        self.assertEqual(payment.transaction_id, "TX999")

    def test_rows_are_ordered_by_protocol_position(self):
        payment = self._payment(credibanco_response=json.dumps(self._answer()))

        sequences = payment.credibanco_extra_info.mapped("sequence")

        self.assertEqual(sequences, sorted(sequences))

    def test_unknown_positions_are_skipped_without_losing_the_payment(self):
        answer = self._answer(**{"699": "valor no documentado"})

        payment = self._payment(credibanco_response=json.dumps(answer))

        self.assertTrue(payment.exists())
        self.assertNotIn(
            "valor no documentado",
            payment.credibanco_extra_info.mapped("credibancoValue"),
        )

    def test_malformed_answer_does_not_break_the_sync(self):
        """A payment must never be lost because its terminal answer is junk."""
        payment = self._payment(credibanco_response="{no es json")

        self.assertTrue(payment.exists())
        self.assertFalse(payment.credibanco_extra_info)
        self.assertFalse(payment.credibanco_approval_number)

    def test_payment_without_answer_creates_no_rows(self):
        payment = self._payment()

        self.assertFalse(payment.credibanco_extra_info)

    def test_pending_sale_is_stored_for_the_recovery_flow(self):
        """The interface keeps the unreconciled sale on the line, for after a reload."""
        payment = self._payment(credibanco_pending_sale=json.dumps(self._answer()))

        self.assertEqual(json.loads(payment.credibanco_pending_sale)["40"], "25000")

    # ------------------------------------------------------------------
    # Cash register number (position 42)
    # ------------------------------------------------------------------

    def test_cash_register_is_not_a_configurable_field_of_the_method(self):
        """Odoo 17 composed the 42 from the session and the cashier ids.

        Credibanco certified that serialisation, so the migration must not let
        the operator write a different value: the field was removed on purpose,
        and the payment-side copy stays only as the *what was sent* audit.
        """
        self.assertNotIn(
            "credibanco_cash_register", self.env["pos.payment.method"]._fields
        )

    def test_cash_register_is_still_stored_on_the_payment(self):
        """The exact 42 that went on the wire is what anulación/recovery echo."""
        self.assertIn(
            "credibanco_cash_register", self.env["pos.payment"]._fields
        )

    # ------------------------------------------------------------------
    # Transaction numbers (position 53)
    # ------------------------------------------------------------------

    def test_reserved_numbers_are_unique_and_never_reused(self):
        first = self.payment_method.reserve_credibanco_transaction_numbers(5)
        second = self.payment_method.reserve_credibanco_transaction_numbers(5)

        self.assertEqual(len(first), 5)
        self.assertEqual(len(set(first + second)), 10, "no number may repeat")
        self.assertEqual(first[0][-6:], first[0][-6:].zfill(6), "stable width")

    def test_numbers_are_unique_within_a_method_and_may_repeat_across_methods(self):
        """Each payment method reserves its own numbering.

        The terminal looks a sale up by (42, 53), and 42 is composed as
        sessionId+cashierId so two sessions never share it; the numbers are
        scoped per method (which is what ties them to a browser's reserved
        block).  Reusing a number across different methods is harmless.
        """
        other = self.env["pos.payment.method"].create(
            self._method_vals(name="Credibanco Otra Caja")
        )

        first_calls = (
            self.payment_method.reserve_credibanco_transaction_numbers(3)
            + self.payment_method.reserve_credibanco_transaction_numbers(3)
        )

        self.assertEqual(len(set(first_calls)), 6, "a register must never repeat")
        self.assertTrue(
            set(other.reserve_credibanco_transaction_numbers(2)) & set(first_calls),
            "a different register may restart its own numbering",
        )

    def test_reserve_refuses_a_method_without_a_credibanco_terminal(self):
        plain = self.env["pos.payment.method"].create({
            "name": "Sin terminal",
            "journal_id": self.bank_journal.id,
        })

        with self.assertRaises(UserError):
            plain.reserve_credibanco_transaction_numbers(3)

    def test_reserve_requires_a_pos_user(self):
        office_user = self.env["res.users"].create({
            "name": "Office Worker Reserva",
            "login": "office_reserva",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })

        with self.assertRaises(AccessError):
            self.payment_method.with_user(office_user).reserve_credibanco_transaction_numbers(3)

    def test_timeout_outlives_the_bridge_own_limit(self):
        """tef.ini LONG_TIMEOUT is 90 s: the POS must not give up first."""
        self.assertGreater(self.payment_method.credibanco_timeout, 90)

    # ------------------------------------------------------------------
    # What the payment keeps about the message it sent
    # ------------------------------------------------------------------

    WIRE_REFERENCE_FIELDS = (
        "credibanco_cash_register",
        "credibanco_number_transaction",
        "credibanco_operator",
    )

    def test_wire_references_are_text_and_survive_verbatim(self):
        """Stored as text so leading zeros and length are preserved exactly."""
        payment = self._payment(
            amount=27000.0,
            credibanco_cash_register="012905",
            credibanco_number_transaction="0001241",
            credibanco_operator="Jose",
        )

        for field in self.WIRE_REFERENCE_FIELDS:
            meta = self.env["pos.payment"]._fields[field]
            self.assertEqual(meta.type, "char", field)
            self.assertEqual(
                payment[field],
                {"credibanco_cash_register": "012905",
                 "credibanco_number_transaction": "0001241",
                 "credibanco_operator": "Jose"}[field],
                "%s must not be coerced to a number" % field,
            )

    def test_wire_references_are_not_copied(self):
        """A duplicated payment must not answer for another transaction."""
        payment = self._payment(
            amount=27000.0,
            credibanco_cash_register="12905",
            credibanco_number_transaction="1241",
            credibanco_operator="Jose",
        )

        clone = payment.copy()

        for field in self.WIRE_REFERENCE_FIELDS:
            self.assertFalse(clone[field], field)

    def test_approval_is_not_copied_when_the_payment_is_recreated(self):
        """copy=False everywhere: a duplicated payment must not fake an approval."""
        payment = self._payment(credibanco_response=json.dumps(self._answer()))

        clone = payment.copy()

        self.assertFalse(clone.credibanco_approval_number)
        self.assertFalse(clone.credibanco_extra_info)

    # ------------------------------------------------------------------
    # Anulación: the compensating negative line (Odoo 17 accounting parity)
    # ------------------------------------------------------------------

    def test_anulation_leaves_a_sale_and_a_reversal_that_net_to_zero(self):
        """The interface registers an anulación as a negative payment line.

        This is the invariant the whole reversal design protects: the approved
        sale keeps its +X (nothing is zeroed), and a -X line cancels it, so
        ``amount_paid`` nets to zero while *both* movements stay present for
        accounting and the acquirer settlement.  The core's native reversal would
        leave a single 0-valued record instead, which `_create_payment_moves`
        skips (nothing to post and nothing to reconcile).
        """
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        amount = 25000.0
        sale = self.env["pos.order"].create({
            "session_id": session.id,
            "user_id": self.env.uid,
            "amount_tax": 0.0,
            "amount_total": amount,
            "amount_paid": amount,
            "amount_return": 0.0,
            "payment_ids": [(0, 0, {
                "amount": amount,
                "payment_method_id": self.payment_method.id,
                "credibanco_cash_register": "012905",
                "credibanco_number_transaction": "000042",
                "credibanco_response": json.dumps(self._answer()),
            })],
        })
        approved = sale.payment_ids
        self.assertTrue(approved.credibanco_approval_number, "the sale is approved")

        # What the browser adds after a successful protocol anulación: a plain
        # negative payment line on the same order (add_payment recomputes
        # amount_paid, exactly like the order sync does).
        sale.add_payment({
            "pos_order_id": sale.id,
            "payment_method_id": self.payment_method.id,
            "amount": -amount,
            "credibanco_cash_register": approved.credibanco_cash_register,
            "credibanco_number_transaction": approved.credibanco_number_transaction,
            "credibanco_anulation_of": approved.uuid,
        })
        reversal = sale.payment_ids - approved

        self.assertEqual(sale.amount_paid, 0.0, "the pair must net to zero")
        self.assertEqual(approved.amount, amount, "the sale amount is not touched")
        self.assertEqual(reversal.amount, -amount)
        self.assertEqual(reversal.credibanco_anulation_of, approved.uuid)
        # The reversal is a plain payment line (no electronic status), so it
        # reaches the ledger instead of being skipped.
        self.assertFalse(reversal.payment_status)

    def test_anulation_marker_is_never_copied(self):
        """A copied reversal must not claim to annul the same (or any) sale."""
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        sale = self.env["pos.order"].create({
            "session_id": session.id,
            "user_id": self.env.uid,
            "amount_tax": 0.0,
            "amount_total": 1000.0,
            "amount_paid": 1000.0,
            "amount_return": 0.0,
            "payment_ids": [(0, 0, {
                "amount": 1000.0,
                "payment_method_id": self.payment_method.id,
            })],
        })
        approved = sale.payment_ids
        sale.add_payment({
            "pos_order_id": sale.id,
            "payment_method_id": self.payment_method.id,
            "amount": -1000.0,
            "credibanco_anulation_of": approved.uuid,
        })
        reversal = sale.payment_ids - approved

        self.assertFalse(reversal.copy().credibanco_anulation_of)


@tagged("post_install", "-at_install")
class TestCredibancoTaxMap(TransactionCase):
    """Which tax becomes which position of the terminal message.

    The Odoo 17 module hardcoded tax ids (9, 10 as IVA and 61 as IAC).  Ids mean
    nothing in another chart: in this very database, 61 is a *negative*
    withholding (R ICA 0.414%), so a literal port of 17 would have sent a
    negative amount in the IAC position.  The classification is therefore done on
    the server, from the tax *group* name, and read with the language disabled so
    a translated group name cannot change the result.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].create({
            "name": "Bank Credibanco Tax Map",
            "type": "bank",
            "code": "BNCM",
            "company_id": cls.company.id,
        })
        cls.method = cls.env["pos.payment.method"].create({
            "name": "Credibanco Tax Map",
            "journal_id": cls.journal.id,
            "use_payment_terminal": "credibanco",
            "pos_payment_terminal_name": "dataf001",
            "pos_ip_host": "127.0.0.1",
            "pos_websocket_port": "8080",
        })
        cls.tax_group = cls.env["account.tax.group"]
        cls.iva_group = cls.tax_group.create({"name": "IVA TEST 18%"})
        cls.inc_group = cls.tax_group.create({"name": "INC TEST 7%"})
        cls.rica_group = cls.tax_group.create({"name": "R ICA TEST 0.5%"})
        cls.cree_group = cls.tax_group.create({"name": "CREE TEST"})
        cls.iva_tax = cls._tax("18% IVA TEST", cls.iva_group, 18)
        cls.inc_tax = cls._tax("7% INC TEST", cls.inc_group, 7)
        cls.rica_tax = cls._tax("0.5% RteICA TEST", cls.rica_group, -0.5)
        cls.cree_tax = cls._tax("4% CREE TEST", cls.cree_group, 4)
        cls.negative_iva_tax = cls._tax("-18% IVA TEST", cls.iva_group, -18)

    @classmethod
    def _tax(cls, name, group, amount, type_tax_use="sale", company=None):
        target = company or cls.company
        # A company without a chart has no fiscal country yet; the tax itself
        # still needs one, and the classification must not depend on it.
        country = target.account_fiscal_country_id or cls.company.account_fiscal_country_id
        return cls.env["account.tax"].create({
            "name": name,
            "type_tax_use": type_tax_use,
            "amount_type": "percent",
            "amount": amount,
            "tax_group_id": group.id,
            "company_id": target.id,
            # Odoo 19 keeps the country of a tax explicit (chart of accounts).
            "country_id": country.id,
        })

    def test_iva_and_inc_are_classified(self):
        tax_map = self.method.get_credibanco_tax_map()

        self.assertEqual(tax_map[self.iva_tax.id], "vat")
        self.assertEqual(tax_map[self.inc_tax.id], "iac")

    def test_withholdings_and_unrelated_groups_never_travel(self):
        tax_map = self.method.get_credibanco_tax_map()

        for tax in (self.rica_tax, self.cree_tax, self.negative_iva_tax):
            self.assertNotIn(tax.id, tax_map, tax.name)

    def test_a_withholding_is_not_iva_even_when_its_group_says_iva(self):
        """The negative -18% lives in an IVA group and must stay out."""
        self.assertTrue(self.negative_iva_tax.tax_group_id.name.startswith("IVA"))
        self.assertNotIn(self.negative_iva_tax.id, self.method.get_credibanco_tax_map())

    def test_classification_is_language_independent(self):
        """The POS user's language must not change what the terminal is told.

        The group name is translated with a direct write: assigning it through
        ``with_context(lang=...)`` on a freshly created record replaces the
        stored value instead of adding a translation, which would make this test
        prove nothing.
        """
        self.env.cr.execute(
            "UPDATE account_tax_group SET name = %s::jsonb WHERE id = %s",
            (
                '{"en_US": "IVA TEST 18%", "es_419": "Impuesto nacional 18%"}',
                self.iva_group.id,
            ),
        )
        self.env.invalidate_all()

        # Sanity check of the fixture: the two languages really do differ.
        self.assertEqual(
            self.iva_group.with_context(lang="es_419").name, "Impuesto nacional 18%"
        )

        tax_map = self.method.with_context(lang="es_419").get_credibanco_tax_map()

        self.assertEqual(tax_map[self.iva_tax.id], "vat")

    def test_only_sale_taxes_of_the_company_are_considered(self):
        other_company = self.env["res.company"].create({
            "name": "Otra Compania Credibanco",
        })
        purchase_tax = self._tax(
            "19% COMPRA TEST", self.iva_group, 19, type_tax_use="purchase"
        )
        foreign_tax = self._tax(
            "18% IVA OTRA CIA", self.iva_group, 18, company=other_company
        )

        tax_map = self.method.get_credibanco_tax_map()

        self.assertNotIn(purchase_tax.id, tax_map)
        self.assertNotIn(foreign_tax.id, tax_map)

    def test_the_map_is_guarded_for_pos_users(self):
        office_user = self.env["res.users"].create({
            "name": "Office Worker Credibanco",
            "login": "office_credibanco",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })

        with self.assertRaises(AccessError):
            self.method.with_user(office_user).get_credibanco_tax_map()

    def test_the_map_can_no_longer_be_configured_per_method(self):
        """Detection is automatic: no tax must be picked by an operator."""
        for field in ("credibanco_vat_tax_ids", "credibanco_iac_tax_ids"):
            self.assertNotIn(field, self.env["pos.payment.method"]._fields)
