from unittest.mock import patch
from uuid import uuid4

import psycopg2

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClosingValidation(TransactionCase):
    """Cash In/Out limits, closing validation and the role policy.

    Note on concurrency: ``TransactionCase`` keeps all data in one uncommitted
    transaction and ``registry.cursor()`` returns a savepoint-backed TestCursor,
    so a real second terminal can never observe the rows a test creates.  The
    row-lock tests therefore assert the SQL contract and inject the lock failure
    instead of pretending two transactions are racing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.cash_journal = cls.env["account.journal"].create({
            "name": "Cash Test",
            "type": "cash",
            "code": "CCSH",
            "company_id": cls.company.id,
        })

        cls.cash_payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash",
            "journal_id": cls.cash_journal.id,
            "is_cash_count": True,
            "split_transactions": False,
        })

        # Odoo 19 derives pos.config.cash_control from a payment method with
        # is_cash_count, so it can no longer be set at creation.
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS",
            "module_pos_restaurant": False,
            "journal_id": cls.cash_journal.id,
            "payment_method_ids": [(6, 0, [cls.cash_payment_method.id])],
            "set_maximum_difference": True,
            "amount_authorized_diff": 10.0,
            "maximum_cash_in_out_moves": 2,
            "enable_rescue_session_validation": True,
        })

        base_user = cls.env.ref("base.group_user").id
        pos_user = cls.env.ref("point_of_sale.group_pos_user").id
        pos_manager = cls.env.ref("point_of_sale.group_pos_manager").id
        # pos.config.open_ui and try_cash_in_out require this group: Odoo grants
        # cash move permission to POS managers or to users with invoicing rights.
        invoicing = cls.env.ref("account.group_account_invoice").id

        cls.cashier = cls.env["res.users"].create({
            "name": "Cashier Test",
            "login": "cashier_test",
            "group_ids": [(6, 0, [base_user, pos_user, invoicing])],
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Manager Test",
            "login": "manager_test",
            "group_ids": [(6, 0, [base_user, pos_user, pos_manager, invoicing])],
        })
        cls.non_pos_user = cls.env["res.users"].create({
            "name": "Office Worker Test",
            "login": "office_worker_test",
            "group_ids": [(6, 0, [base_user])],
        })

    def setUp(self):
        super().setUp()
        # Per-test cache: TransactionCase rolls the transaction back after each
        # test, so records created by a sibling test no longer exist.
        self.products = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _product(self, price):
        """One product per price, reused across assertions."""
        if price not in self.products:
            self.products[price] = self.env["product.product"].create({
                "name": f"Test Product {price}",
                "list_price": price,
                "taxes_id": [(6, 0, [])],
            })
        return self.products[price]

    def _create_session(self, opening=0.0, rescue=False, user=None):
        """Create and open a POS session, with the given opening balance."""
        vals = {"config_id": self.pos_config.id}
        if rescue:
            vals["rescue"] = True
        session = self.env["pos.session"].create(vals)
        session.action_pos_session_open()
        if opening:
            session.cash_register_balance_start = opening
        return session.with_user(user) if user else session

    def _create_cash_move(self, session, amount, reason="Test", move_uuid=None):
        """Register a Cash In/Out movement the way the POS frontend does."""
        _type = "in" if amount > 0 else "out"
        user = session.env.user
        session.try_cash_in_out(
            _type,
            abs(amount),
            reason,
            user.partner_id.id,
            {
                "translatedType": _type,
                "formattedAmount": str(abs(amount)),
                "cash_move_uuid": move_uuid or str(uuid4()),
            },
        )

    def _create_order(self, session, product, price, state="draft"):
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "partner_id": self.env["res.partner"].create({"name": "Partner"}).id,
            "lines": [(0, 0, {
                "product_id": product.id,
                "qty": 1,
                "price_unit": price,
                "price_subtotal": price,
                "price_subtotal_incl": price,
            })],
            "amount_tax": 0.0,
            "amount_total": price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "state": state,
        })
        return order

    def _cash_sale(self, session, price):
        """A cash-paid order that counts towards the register balance.

        Odoo only counts payments of captured orders (state paid/invoiced/done);
        a draft order's payment is deliberately invisible to the theoretical
        balance, so the helper makes that explicit instead of hiding it.
        """
        order = self._create_order(session, self._product(price), price)
        self.env["pos.payment"].create({
            "pos_order_id": order.id,
            "payment_method_id": self.cash_payment_method.id,
            "amount": price,
            "payment_date": fields.Datetime.now(),
        })
        order.state = "paid"
        return order

    def _statement_line(self, session, amount, tagged_move=True, move_uuid=None):
        """Create a statement line directly, bypassing the Cash In/Out guard."""
        return self.env["account.bank.statement.line"].create({
            "payment_ref": "Injected move",
            "journal_id": self.cash_journal.id,
            "amount": amount,
            "pos_session_id": session.id,
            "pos_cash_move": tagged_move,
            "pos_cash_move_uuid": move_uuid,
        })

    def _snapshot(self, session):
        return session._get_closing_cash_validation_data()

    # ==================================================================
    # Snapshot: single source of truth, reconciled with Odoo
    # ==================================================================

    def test_case_a_normal_session(self):
        """Caso A: opening 1000 + sales 200 - cash out 50 = 1150."""
        session = self._create_session(opening=1000.0)
        self._cash_sale(session, 200.0)
        self._create_cash_move(session, -50.0)

        data = self._snapshot(session)

        self.assertAlmostEqual(data["opening_cash"], 1000.0, places=2)
        self.assertAlmostEqual(data["cash_sales"], 200.0, places=2)
        self.assertAlmostEqual(data["cash_in"], 0.0, places=2)
        self.assertAlmostEqual(data["cash_out"], 50.0, places=2)
        self.assertAlmostEqual(data["expected_cash"], 1150.0, places=2)
        self.assertFalse(data["is_rescue"])

    def test_expected_cash_is_odoos_theoretical_balance(self):
        """expected_cash must be exactly Odoo's cash_register_balance_end.

        This is the invariant that keeps the module from inventing a second
        definition of "expected cash" that disagrees with the number the
        standard closing popup shows next to ours.
        """
        session = self._create_session(opening=1000.0)
        self._cash_sale(session, 200.0)
        # A cancelled order's payment must not count (Odoo excludes it).
        ghost = self._create_order(session, self._product(70.0), 70.0, state="cancel")
        self.env["pos.payment"].create({
            "pos_order_id": ghost.id,
            "payment_method_id": self.cash_payment_method.id,
            "amount": 70.0,
            "payment_date": fields.Datetime.now(),
        })
        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)

        data = self._snapshot(session)

        self.assertAlmostEqual(
            data["expected_cash"], session.cash_register_balance_end, places=2
        )
        self.assertAlmostEqual(data["expected_cash"], 1250.0, places=2)

    def test_snapshot_breakdown_reconciles_with_expected(self):
        """apertura + ventas + in - out must equal the expected cash."""
        session = self._create_session(opening=500.0)
        self._cash_sale(session, 120.0)
        self._cash_sale(session, 80.0)
        self._create_cash_move(session, 60.0)
        self._create_cash_move(session, -30.0)

        data = self._snapshot(session)
        computed = (
            data["opening_cash"]
            + data["cash_sales"]
            + data["cash_in"]
            - data["cash_out"]
        )

        self.assertAlmostEqual(computed, data["expected_cash"], places=2)

    def test_cash_in_out_counts_all_lines_by_sign(self):
        """Cash In/Out display includes untagged lines, the counter does not.

        A line created outside the popup (accounting entry on the cash journal)
        is real money in the drawer: it must appear in the breakdown, while the
        per-session limit only counts operator movements.
        """
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        self._statement_line(session, 25.0, tagged_move=False)

        data = self._snapshot(session)

        self.assertAlmostEqual(data["cash_in"], 125.0, places=2)
        self.assertEqual(data["cash_move_count"], 1)
        self.assertEqual(data["statement_lines_count"], 2)

    def test_case_b_rescue_session(self):
        """Caso B: rescues reject cash moves and expose their snapshot."""
        parent = self._create_session(opening=1556.90)
        parent.cash_register_balance_end_real = 1556.90
        parent.action_pos_session_closing_control()

        rescue = self._create_session(opening=1556.90, rescue=True)
        for _ in range(3):
            self._cash_sale(rescue, 101.15)

        with self.assertRaises(UserError) as ctx:
            self._create_cash_move(rescue, -1000.0)
        self.assertIn("sincronizado", ctx.exception.args[0].lower())

        data = self._snapshot(rescue)

        self.assertTrue(data["is_rescue"])
        self.assertAlmostEqual(data["cash_sales"], 303.45, places=2)
        self.assertAlmostEqual(data["expected_cash"], 1860.35, places=2)
        self.assertEqual(data["cash_move_count"], 0)
        self.assertEqual(data["reason"], "rescue_session")
        self.assertEqual(data["parent_session_name"], parent.name)

    def test_case_g_rescue_no_statement_lines(self):
        """Caso G: rescue without synced data reports its opening only."""
        rescue = self._create_session(opening=1556.90, rescue=True)

        data = self._snapshot(rescue)

        self.assertAlmostEqual(data["expected_cash"], 1556.90, places=2)
        self.assertAlmostEqual(data["cash_sales"], 0.0, places=2)
        self.assertAlmostEqual(data["cash_in"], 0.0, places=2)
        self.assertAlmostEqual(data["cash_out"], 0.0, places=2)

    def test_snapshot_fields_completeness(self):
        """The snapshot contract consumed by the frontend stays complete."""
        session = self._create_session(opening=1000.0)

        data = self._snapshot(session)

        required_keys = [
            "session_id", "session_name", "state", "is_rescue", "reason",
            "is_manager", "parent_session_name", "opening_cash", "cash_sales",
            "cash_in", "cash_in_count", "cash_out", "cash_out_count",
            "cash_move_count", "cash_move_limit", "expected_cash",
            "counted_cash", "difference", "statement_lines_count",
            "orders_count", "has_orders", "can_close", "blocking_reasons",
            "warnings", "pending_rescue",
        ]
        for key in required_keys:
            self.assertIn(key, data, f"Missing key: {key}")

    def test_case_p_snapshot_has_orders_field(self):
        """Caso P: has_orders reflects the session's orders."""
        session = self._create_session(opening=1000.0)
        self.assertFalse(self._snapshot(session)["has_orders"])

        self._create_order(session, self._product(100.0), 100.0)

        self.assertTrue(self._snapshot(session)["has_orders"])

    def test_closing_control_data_is_left_to_odoo(self):
        """Odoo's own closing payload must not carry our keys.

        Passing unknown keys as props to ClosePosPopup makes OWL 2 reject them,
        which is why the enrichment lives in get_closing_validation_info.
        """
        session = self._create_session(opening=1000.0)

        data = session.with_user(self.cashier).get_closing_control_data()

        for key in ("can_close", "blocking_reasons", "expected_cash", "pending_rescue"):
            self.assertNotIn(key, data)
        self.assertIn("default_cash_details", data)
        self.assertIn("non_cash_payment_methods", data)

    # ==================================================================
    # Cash In / Out limit
    # ==================================================================

    def test_case_e_cash_in_out_limit(self):
        """Caso E: the third movement is refused with a 2/2 limit."""
        session = self._create_session(opening=1000.0)

        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)

        with self.assertRaises(UserError) as ctx:
            self._create_cash_move(session, 25.0)
        self.assertIn("límite de movimientos", ctx.exception.args[0].lower())

    def test_normal_session_allows_cash_moves(self):
        """Non-rescue sessions can move cash in both directions."""
        session = self._create_session(opening=1000.0)

        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)

        data = self._snapshot(session)
        self.assertEqual(data["cash_move_count"], 2)
        self.assertAlmostEqual(data["cash_in"], 100.0, places=2)
        self.assertAlmostEqual(data["cash_out"], 50.0, places=2)

    def test_cash_move_is_tagged_with_uuid(self):
        """The movement is flagged and identified where Odoo builds its values."""
        session = self._create_session(opening=1000.0)
        move_uuid = str(uuid4())

        self._create_cash_move(session, 100.0, move_uuid=move_uuid)

        line = self._statement_lines(session)
        self.assertEqual(len(line), 1)
        self.assertTrue(line.pos_cash_move)
        self.assertEqual(line.pos_cash_move_uuid, move_uuid)

    def test_retrying_the_same_uuid_does_not_duplicate(self):
        """A replayed request (lost response or offline queue) is a no-op.

        Odoo 19 re-sends a queued cash move with the same arguments, and the
        cashier may also press Confirm again after a timeout.  Without the uuid
        both paths would silently exceed the per-session limit.
        """
        session = self._create_session(opening=1000.0)
        move_uuid = str(uuid4())

        self._create_cash_move(session, 100.0, move_uuid=move_uuid)
        self._create_cash_move(session, 100.0, move_uuid=move_uuid)

        self.assertEqual(len(self._statement_lines(session)), 1)
        self.assertEqual(self._snapshot(session)["cash_move_count"], 1)

    def test_duplicate_cash_move_uuid_is_refused_by_the_database(self):
        """The unique constraint is the backstop when two replays overlap.

        The application-level dedupe cannot cover two requests that are in flight
        at the same instant; the database can.  This also guards the constraint
        against being declared with the removed ``_sql_constraints`` attribute,
        which Odoo 19 ignores with only a warning.
        """
        session = self._create_session(opening=1000.0)
        move_uuid = str(uuid4())
        self._create_cash_move(session, 100.0, move_uuid=move_uuid)

        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with self.env.cr.savepoint():
                self._statement_line(session, 20.0, move_uuid=move_uuid)

        self.assertEqual(len(self._statement_lines(session)), 1)

    def test_same_uuid_twice_still_respects_the_limit(self):
        """Dedupe happens before the limit check, not after."""
        session = self._create_session(opening=1000.0)
        first = str(uuid4())
        second = str(uuid4())

        self._create_cash_move(session, 100.0, move_uuid=first)
        self._create_cash_move(session, 50.0, move_uuid=second)
        # Replays are accepted (they are the same movements) but add nothing.
        self._create_cash_move(session, 100.0, move_uuid=first)

        with self.assertRaises(UserError):
            self._create_cash_move(session, 25.0)

    def _statement_lines(self, session):
        return self.env["account.bank.statement.line"].sudo().search([
            ("pos_session_id", "=", session.id),
        ])

    # ==================================================================
    # Row lock
    # ==================================================================

    def test_cash_move_lock_is_bounded(self):
        """The session is locked with a bounded wait, never indefinitely.

        An unbounded FOR UPDATE lets a slow closing transaction hang the second
        terminal's worker until the request times out, which is how a movement
        ends up registered twice.
        """
        session = self._create_session(opening=1000.0)
        executed = []
        real_execute = self.env.cr.execute

        def spy(query, *args, **kwargs):
            executed.append(query)
            return real_execute(query, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=spy):
            self._create_cash_move(session, 100.0)

        timeouts = [q for q in executed if "SET LOCAL lock_timeout" in q]
        locks = [q for q in executed if "FOR UPDATE" in q]
        self.assertEqual(len(timeouts), 1, "lock_timeout must be set once")
        self.assertEqual(len(locks), 1, "the session row must be locked once")
        self.assertLess(
            executed.index(timeouts[0]), executed.index(locks[0]),
            "lock_timeout must be set before the lock is requested",
        )

    def test_lock_timeout_raises_an_actionable_error(self):
        """When the lock cannot be taken, the cashier gets the current count.

        The message must state how many movements exist: the dangerous failure
        is not the error itself but the operator retrying blindly and creating
        a duplicate.  The synthetic failure also proves the savepoint around the
        lock leaves the transaction usable for the follow-up read.
        """
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)

        real_execute = self.env.cr.execute

        def failing_execute(query, *args, **kwargs):
            if "FOR UPDATE" in query:
                raise psycopg2.errors.LockNotAvailable(
                    "could not obtain lock on row in relation \"pos_session\""
                )
            return real_execute(query, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=failing_execute):
            with self.assertRaises(UserError) as ctx:
                self._create_cash_move(session, 50.0)

        message = ctx.exception.args[0]
        self.assertIn("1 de 2", message)
        self.assertIn("Verifique ese conteo", message)

    def test_no_movement_is_recorded_when_the_lock_fails(self):
        """A refused lock means no money moved."""
        session = self._create_session(opening=1000.0)
        real_execute = self.env.cr.execute

        def failing_execute(query, *args, **kwargs):
            if "FOR UPDATE" in query:
                raise psycopg2.errors.LockNotAvailable("blocked")
            return real_execute(query, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=failing_execute):
            with self.assertRaises(UserError):
                self._create_cash_move(session, 50.0)

        self.assertEqual(self._snapshot(session)["cash_move_count"], 0)

    # ==================================================================
    # Cash difference at closing (applies to every role)
    # ==================================================================

    def test_case_d_difference_within_limit(self):
        """Caso D: a 5.0 difference is inside a 10.0 maximum."""
        session = self._create_session(opening=1000.0)

        self.assertIsNone(session._check_authorized_cash_difference(995.0))

    def test_case_d_difference_over_limit(self):
        """A difference above the maximum is refused with both amounts."""
        session = self._create_session(opening=1000.0)

        error = session._check_authorized_cash_difference(900.0)

        self.assertTrue(error)
        self.assertFalse(error["successful"])
        self.assertIn("Diferencia", error["message"])
        self.assertIn("Máximo autorizado", error["message"])

    def test_cash_difference_block_applies_to_managers_too(self):
        """The money rule is never softened, not even for a manager."""
        session = self._create_session(opening=1000.0)

        result = session.with_user(self.manager).post_closing_cash_details(900.0)

        self.assertFalse(result["successful"])
        self.assertIn("diferencia", result["message"].lower())

    def test_custom_cash_difference_message_is_used(self):
        """The configured message replaces the default body."""
        self.pos_config.cash_difference_exceeded_message = "Llame al gerente de turno."
        session = self._create_session(opening=1000.0)

        error = session._check_authorized_cash_difference(900.0)

        self.assertIn("Llame al gerente de turno.", error["message"])

    def test_no_difference_validation_when_disabled(self):
        """With set_maximum_difference off, any counted amount is accepted."""
        self.pos_config.set_maximum_difference = False
        session = self._create_session(opening=1000.0)

        result = session.post_closing_cash_details(5000.0)

        self.assertTrue(result["successful"])

    # ==================================================================
    # Closing dialog contract: which buttons each error may show
    # ==================================================================

    def test_cash_difference_error_offers_the_orders_action(self):
        """A difference is often caused by unregistered orders: offer to review them."""
        session = self._create_session(opening=1000.0)

        error = session._check_authorized_cash_difference(900.0)

        self.assertTrue(error["cash_validation"])
        self.assertEqual(error["kind"], "authorized_difference")
        self.assertTrue(error["show_orders_action"])

    def test_consistency_errors_only_ask_for_acknowledgement(self):
        """Reviewing orders is useless for internal inconsistencies.

        Without this marker the dialog inherits Odoo's secondary button, which
        cancels every non-finalized order of the terminal.
        """
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)
        self._statement_line(session, 25.0)
        session.invalidate_recordset()

        error = session.with_user(self.cashier)._cannot_close_session()

        self.assertTrue(error["cash_validation"])
        self.assertEqual(error["kind"], "cash_move_integrity")
        self.assertFalse(error["show_orders_action"])

        order = self._create_order(session, self._product(100.0), 100.0)
        order.state = "paid"
        data_error = session._check_session_data_integrity()
        self.assertTrue(data_error["cash_validation"])
        self.assertFalse(data_error["show_orders_action"])

    def test_rescue_refusal_only_asks_for_acknowledgement(self):
        """Rescue sessions are closed from the backend, not by reviewing orders."""
        rescue = self._create_session(opening=1000.0, rescue=True)

        result = rescue.post_closing_cash_details(1000.0)

        self.assertTrue(result["cash_validation"])
        self.assertEqual(result["kind"], "rescue_session")
        self.assertFalse(result["show_orders_action"])

    def test_core_draft_order_error_is_not_marked_as_ours(self):
        """Odoo's own draft-orders answer keeps its Cancel Orders button.

        That button is the correct escape hatch there, so it must not be
        swallowed by our handler.
        """
        session = self._create_session(opening=1000.0)
        # Draft order and counted cash matching the expected balance: our rules
        # stay silent and only Odoo's draft check fires.
        self._create_order(session, self._product(100.0), 100.0)

        result = session.post_closing_cash_details(1000.0)

        self.assertFalse(result["successful"])
        self.assertNotIn("cash_validation", result)
        self.assertIn("open_order_ids", result)

    # ==================================================================
    # Closing flow
    # ==================================================================

    def test_post_closing_cash_details_allows_within_limit(self):
        """A clean closing writes the counted balance and succeeds."""
        session = self._create_session(opening=1000.0)

        result = session.post_closing_cash_details(1005.0)

        self.assertTrue(result["successful"])
        self.assertAlmostEqual(session.cash_register_balance_end_real, 1005.0, places=2)

    def test_post_closing_cash_details_refuses_rescue_session(self):
        """Rescues are closed from the backend, whatever the role."""
        rescue = self._create_session(opening=1000.0, rescue=True)

        for user in (self.cashier, self.manager):
            result = rescue.with_user(user).post_closing_cash_details(1000.0)
            self.assertFalse(result["successful"])
            self.assertIn("rescate", result["message"].lower())

    def test_cashier_is_blocked_by_consistency_checks(self):
        """A plain cashier cannot close with an inconsistent movement count."""
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)
        # Third tagged line: 3 movements against a limit of 2.
        self._statement_line(session, 25.0)

        session.invalidate_recordset()
        result = session.with_user(self.cashier).post_closing_cash_details(1075.0)

        self.assertFalse(result["successful"])
        self.assertIn("inconsistencia", result["message"].lower())

    def test_manager_bypasses_consistency_checks_with_audit_note(self):
        """A manager can close over an internal inconsistency, and it is recorded.

        A false positive in a heuristic check must never trap a store with its
        register open at the end of the day.
        """
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)
        self._statement_line(session, 25.0)

        session.invalidate_recordset()
        result = session.with_user(self.manager).post_closing_cash_details(1075.0)

        self.assertTrue(result["successful"])
        notes = session.message_ids.filtered(
            lambda m: "Validación de caja superada" in (m.body or "")
        )
        self.assertTrue(notes, "the bypass must leave an audit trail")

    def test_snapshot_can_close_depends_on_role(self):
        """can_close and blocking_reasons match what the server will enforce."""
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        self._create_cash_move(session, -50.0)
        self._statement_line(session, 25.0)
        session.invalidate_recordset()

        cashier_view = self._snapshot(session.with_user(self.cashier))
        manager_view = self._snapshot(session.with_user(self.manager))

        self.assertFalse(cashier_view["can_close"])
        self.assertTrue(cashier_view["blocking_reasons"])
        self.assertTrue(manager_view["can_close"])
        self.assertEqual(manager_view["blocking_reasons"], [])
        # The warning is still reported, so the UI can show it without blocking.
        self.assertTrue(manager_view["warnings"])

    def test_structural_block_is_not_role_dependent(self):
        """Closed and rescue sessions block every role identically."""
        rescue = self._create_session(opening=1000.0, rescue=True)

        for user in (self.cashier, self.manager):
            snapshot = self._snapshot(rescue.with_user(user))
            self.assertFalse(snapshot["can_close"])
            self.assertTrue(snapshot["blocking_reasons"])

    def test_get_blocking_reasons_empty_for_clean_session(self):
        """A normal session with nothing unusual reports no reasons."""
        session = self._create_session(opening=1000.0)

        self.assertEqual(session.with_user(self.cashier)._get_blocking_reasons(), [])

    def test_case_i_data_integrity_paid_no_payments(self):
        """Caso I: a paid order without payments is reported.

        The direct write of state='paid' is kept from the Odoo 17 suite; it must
        be re-verified if a future version rejects that transition.
        """
        session = self._create_session(opening=1000.0)
        order = self._create_order(session, self._product(100.0), 100.0)
        order.state = "paid"

        result = session._check_session_data_integrity()

        self.assertTrue(result)
        self.assertEqual(result["kind"], "data_integrity")
        self.assertIn("órdenes pagadas", result["message"])

    def test_clean_session_has_no_data_integrity_issue(self):
        """Properly paid orders produce no integrity complaint.

        There is no test for the orphan-payment branch on purpose: Odoo 19 makes
        pos.payment.pos_order_id mandatory, so the row cannot exist anymore and
        the branch only guards sessions upgraded from an older version.
        """
        session = self._create_session(opening=1000.0)
        self._cash_sale(session, 100.0)

        self.assertIsNone(session._check_session_data_integrity())

    # ==================================================================
    # Endpoints: access and cashier readability
    # ==================================================================

    def test_endpoints_require_pos_user(self):
        """Cash data is not readable by arbitrary internal users."""
        session = self._create_session(opening=1000.0)
        outsider = session.with_user(self.non_pos_user)

        for method in ("get_closing_validation_info", "get_cash_in_out_control_data"):
            with self.assertRaises(AccessError):
                getattr(outsider, method)()

    def test_cashier_can_read_the_snapshot(self):
        """Statement lines are read with sudo, so the popup works for cashiers.

        Without sudo the whole Cash In/Out popup would raise an AccessError for
        the only role that uses it.
        """
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)

        cashier_session = session.with_user(self.cashier)
        data = cashier_session.get_closing_validation_info()

        self.assertEqual(data["cash_move_count"], 1)
        self.assertEqual(cashier_session.get_cash_in_out_control_data()["count"], 1)

    def test_control_data_reports_limit(self):
        """The popup reads count and limit in one call."""
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)

        control = session.get_cash_in_out_control_data()

        self.assertEqual(control, {"count": 1, "limit": 2})

    # ==================================================================
    # Deleting movements
    # ==================================================================

    def test_cashier_cannot_delete_a_cash_move(self):
        """Deleting releases a slot of the limit, so it is manager-only."""
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        line = self._statement_lines(session)

        with self.assertRaises(UserError) as ctx:
            session.with_user(self.cashier).delete_cash_in_out(line.id, self.cashier.partner_id.id)
        self.assertIn("responsable", ctx.exception.args[0].lower())
        self.assertTrue(line.exists())

    def test_manager_can_delete_a_cash_move(self):
        """A manager may remove a movement, and the count follows."""
        session = self._create_session(opening=1000.0)
        self._create_cash_move(session, 100.0)
        line = self._statement_lines(session)

        session.with_user(self.manager).delete_cash_in_out(
            line.id, self.manager.partner_id.id
        )

        session.invalidate_recordset()
        self.assertEqual(self._snapshot(session)["cash_move_count"], 0)

    # ==================================================================
    # Rescue sessions
    # ==================================================================

    def test_case_c_rescue_blocks_both_directions(self):
        """Caso C: rescues reject Cash In and Cash Out alike."""
        rescue = self._create_session(opening=1556.90, rescue=True)

        with self.assertRaises(UserError):
            self._create_cash_move(rescue, 500.0)
        with self.assertRaises(UserError):
            self._create_cash_move(rescue, -200.0)

        data = self._snapshot(rescue)
        self.assertAlmostEqual(data["cash_in"], 0.0, places=2)
        self.assertAlmostEqual(data["cash_out"], 0.0, places=2)
        self.assertEqual(data["cash_move_count"], 0)

    def test_snapshot_rescue_parent_link(self):
        """A rescue is linked to the last normal session of its POS."""
        parent = self._create_session(opening=1000.0)
        parent.action_pos_session_closing_control()

        rescue = self._create_session(rescue=True)

        self.assertEqual(rescue.rescue_parent_session_id, parent)
        self.assertIn(rescue, parent.rescue_session_ids)

    def test_case_j_is_empty_rescue_empty(self):
        """Caso J: a rescue without data is empty."""
        rescue = self._create_session(opening=1000.0, rescue=True)

        self.assertTrue(rescue._is_empty_rescue())

    def test_case_k_is_empty_rescue_with_order(self):
        """Caso K: a rescue with an order is not empty."""
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(100.0), 100.0)

        self.assertFalse(rescue._is_empty_rescue())

    def test_case_l_is_empty_rescue_with_cancelled_orders(self):
        """Caso L: cancelled orders still mean the rescue holds data."""
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(100.0), 100.0, state="cancel")

        self.assertFalse(rescue._is_empty_rescue())

    def test_case_m_empty_rescue_does_not_block(self):
        """Caso M: an empty rescue must not block closing."""
        parent = self._create_session(opening=1000.0)
        self._create_session(opening=1000.0, rescue=True)

        self.assertIsNone(parent._check_rescue_sessions_pending())

    def test_case_n_non_empty_rescue_does_block(self):
        """Caso N: a rescue holding orders blocks the parent's closing."""
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)

        result = parent._check_rescue_sessions_pending()

        self.assertTrue(result)
        self.assertEqual(result["kind"], "pending_rescue")
        self.assertIn("rescate", result["message"].lower())

    def test_case_o_default_rescue_validation_is_false(self):
        """Caso O: rescue validation is opt-in per POS."""
        journal = self.env["account.journal"].create({
            "name": "Cash Default Test",
            "type": "cash",
            "code": "CDEF",
            "company_id": self.company.id,
        })
        payment_method = self.env["pos.payment.method"].create({
            "name": "Cash Default Test",
            "journal_id": journal.id,
            "is_cash_count": True,
            "split_transactions": False,
        })
        new_config = self.env["pos.config"].create({
            "name": "Test POS Default",
            "module_pos_restaurant": False,
            "journal_id": journal.id,
            "payment_method_ids": [(6, 0, [payment_method.id])],
        })

        self.assertFalse(new_config.enable_rescue_session_validation)

    def test_rescue_validation_disabled_skips_the_check(self):
        """With the flag off, pending rescues are not a blocker."""
        self.pos_config.enable_rescue_session_validation = False
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)

        self.assertIsNone(parent._check_rescue_sessions_pending())

    def test_filter_non_empty_rescues_returns_correct_subset(self):
        """The batched filter keeps only rescues with data."""
        empty_rescue = self._create_session(opening=1000.0, rescue=True)
        rescue_with_order = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue_with_order, self._product(50.0), 50.0)
        rescue_with_payment = self._create_session(opening=1000.0, rescue=True)
        order = self._create_order(rescue_with_payment, self._product(50.0), 50.0)
        self.env["pos.payment"].create({
            "pos_order_id": order.id,
            "payment_method_id": self.cash_payment_method.id,
            "amount": 50.0,
            "payment_date": fields.Datetime.now(),
        })
        rescue_with_line = self._create_session(opening=1000.0, rescue=True)
        self._statement_line(rescue_with_line, 20.0)

        all_rescues = (
            empty_rescue | rescue_with_order | rescue_with_payment | rescue_with_line
        )
        non_empty = all_rescues._filter_non_empty_rescues()

        self.assertNotIn(empty_rescue, non_empty)
        self.assertIn(rescue_with_order, non_empty)
        self.assertIn(rescue_with_payment, non_empty)
        self.assertIn(rescue_with_line, non_empty)
        self.assertEqual(len(non_empty), 3)

    def test_filter_non_empty_rescues_empty_recordset(self):
        """The filter tolerates an empty recordset."""
        self.assertEqual(len(self.env["pos.session"]._filter_non_empty_rescues()), 0)

    def test_filter_non_empty_rescues_ignores_normal_sessions(self):
        """Non-rescue sessions never survive the rescue filter."""
        normal = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)

        kept = (normal | rescue)._filter_non_empty_rescues()

        self.assertEqual(kept, rescue)

    # ==================================================================
    # Opening cycle: pending rescues
    # ==================================================================

    def test_opening_blocked_with_pending_rescue(self):
        """A pending rescue stops a new session from opening."""
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)
        parent.cash_register_balance_end_real = 1050.0
        parent.action_pos_session_closing_control()

        with self.assertRaises(UserError) as ctx:
            self.pos_config.open_ui()
        message = ctx.exception.args[0].lower()
        self.assertIn("rescate", message)
        self.assertIn("tablero", message)

    def test_opening_allowed_when_no_rescue(self):
        """Nothing is pending for a clean config."""
        self._create_session(opening=1000.0)

        pending = self.env["pos.session"]._get_pending_rescue_sessions_for_config(
            self.pos_config.id
        )
        self.assertEqual(len(pending), 0)

    def test_opening_allowed_when_rescue_validation_disabled(self):
        """The flag really gates open_ui."""
        self.pos_config.enable_rescue_session_validation = False
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)

        try:
            self.pos_config.open_ui()
        except UserError as error:
            self.assertNotIn("rescate", error.args[0].lower())

    def test_opening_allowed_when_rescue_closed(self):
        """A closed rescue no longer counts as pending."""
        self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        rescue.cash_register_balance_end_real = 1000.0
        rescue.action_pos_session_closing_control()

        pending = self.env["pos.session"]._get_pending_rescue_sessions_for_config(
            self.pos_config.id
        )
        self.assertEqual(len(pending), 0)

    def test_check_pending_rescue_sessions_returns_blocked(self):
        """Opening validation is strict: any open rescue blocks."""
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)

        result = parent._check_pending_rescue_sessions()

        self.assertTrue(result["blocked"])
        self.assertEqual(result["reason"], "pending_rescue")
        self.assertEqual(result["sessions"][0]["id"], rescue.id)

    def test_check_pending_rescue_sessions_returns_not_blocked(self):
        """No rescue means no block."""
        session = self._create_session(opening=1000.0)

        result = session._check_pending_rescue_sessions()

        self.assertFalse(result["blocked"])
        self.assertEqual(result["sessions"], [])

    def test_get_pending_rescue_sessions_includes_empty(self):
        """Opening considers empty rescues too (stricter than closing)."""
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)

        self.assertIn(rescue, parent._get_pending_rescue_sessions())

    def test_has_pending_rescue_sessions(self):
        """The boolean helper agrees with the recordset."""
        parent = self._create_session(opening=1000.0)
        self.assertFalse(parent._has_pending_rescue_sessions())

        rescue = self._create_session(opening=1000.0, rescue=True)
        self.assertTrue(parent._has_pending_rescue_sessions())
        self.assertIn(rescue, parent._get_pending_rescue_sessions())

    def test_pending_rescue_validation_data_structure(self):
        """The rescue summary exposes id, name and state."""
        parent = self._create_session(opening=1000.0)
        rescue = self._create_session(opening=1000.0, rescue=True)

        data = parent._get_pending_rescue_validation_data()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], rescue.id)
        self.assertEqual(data[0]["name"], rescue.name)
        self.assertEqual(data[0]["state"], rescue.state)

    # ==================================================================
    # Configuration
    # ==================================================================

    def test_maximum_cash_moves_must_be_positive(self):
        """A zero or negative limit is rejected with a translated message."""
        with self.assertRaises(UserError) as ctx:
            self.pos_config.maximum_cash_in_out_moves = 0
            self.env.flush_all()
        self.assertIn("mayor que cero", ctx.exception.args[0])

    def test_pending_rescue_flag_in_snapshot(self):
        """pending_rescue only reports rescues that actually hold data."""
        parent = self._create_session(opening=1000.0)
        self._create_session(opening=1000.0, rescue=True)

        self.assertFalse(self._snapshot(parent)["pending_rescue"])

        rescue = self._create_session(opening=1000.0, rescue=True)
        self._create_order(rescue, self._product(50.0), 50.0)
        parent.invalidate_recordset()

        self.assertTrue(self._snapshot(parent)["pending_rescue"])
