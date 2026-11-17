# -*- coding: utf-8 -*-
"""The link with the purchase order (the P##### code on the first line of the Clara comment) and the reconciliation
state in its four cases."""
import json

from ..models.clara_transaction import order_code, scrub_payload
from .common import HOLDER, HOLDER_UUID, MASKED_PAN, ClaraCase, transaction_payload


class TestReconciliation(ClaraCase):
    def _tx(self, uuid, **kwargs):
        payload = transaction_payload(uuid, **kwargs)
        return self.Transaction.create(dict(self.Transaction._vals_from_payload(payload)))

    def test_order_code_on_the_first_line(self):
        self.assertEqual(order_code("P45717"), "P45717")
        self.assertEqual(order_code("  p45717: Paquete Salitre, tienda 140\nsegunda línea"), "P45717")
        self.assertEqual(order_code("Orden P00817 - almuerzo"), "P00817")
        self.assertEqual(order_code("Almuerzo con cliente\nP45717"), "")       # not on the first line
        self.assertEqual(order_code("XP45717 PA1234 P12"), "")                  # part of another word, too short
        self.assertEqual(order_code(""), "")
        self.assertEqual(order_code(None), "")

    def test_reconciliation_state_in_its_four_cases(self):
        order = self._order("P77101")
        reconciled = self._tx("tx-reconciled", comment="P77101\nPaquete Salitre", legalization="Approved")
        approved_no_order = self._tx("tx-approved", comment="Sin código", legalization="Approved")
        pending = self._tx("tx-pending", comment="P77101", legalization="Needs Approval")
        rejected = self._tx("tx-rejected", comment="P77101", legalization="Rejected")
        self.assertEqual((reconciled.purchase_order_id, reconciled.reconciliation_state, reconciled.reconciled_ratio), (order, "reconciled", 100.0))
        self.assertEqual((approved_no_order.purchase_order_id.id, approved_no_order.reconciliation_state, approved_no_order.reconciled_ratio), (False, "approved_no_order", 0.0))
        self.assertEqual((pending.purchase_order_id, pending.reconciliation_state, pending.reconciled_ratio), (order, "pending", 0.0))
        self.assertEqual((rejected.purchase_order_id, rejected.reconciliation_state, rejected.reconciled_ratio), (order, "rejected", 0.0))
        self.assertEqual(set(dict(self.Transaction._fields["reconciliation_state"].selection)), {"reconciled", "approved_no_order", "pending", "rejected"})

    def test_an_order_that_does_not_exist_or_is_cancelled_does_not_reconcile(self):
        missing = self._tx("tx-missing", comment="P77999", legalization="Approved")
        self.assertEqual((missing.purchase_order_id.id, missing.reconciliation_state), (False, "approved_no_order"))
        order = self._order("P77102")
        tx = self._tx("tx-cancel", comment="P77102", legalization="Approved")
        self.assertEqual(tx.reconciliation_state, "reconciled")
        order.button_cancel()   # the test cancels it, not the module
        self.assertEqual(tx.reconciliation_state, "approved_no_order")
        self.env.add_to_compute(self.Transaction._fields["purchase_order_id"], tx)
        self.assertFalse(tx.purchase_order_id)
        # the order is booked after the transaction was synced: the next sync links it
        late = self._tx("tx-late", comment="P77103", legalization="Approved")
        self.assertEqual(late.reconciliation_state, "approved_no_order")
        self._order("P77103")
        self.Transaction._relink_after_sync()
        self.assertEqual((late.purchase_order_id.name, late.reconciliation_state), ("P77103", "reconciled"))

    def test_relink_follows_orders_booked_or_cancelled_after_the_sync(self):
        """A pending transaction with a code gets its order when the bot books it; a link to an order cancelled since
        the last sync is dropped; a transaction without a code has nothing to link."""
        pending = self._tx("tx-pending-late", comment="Orden P77201 almuerzo", legalization="Needs Approval")
        no_code = self._tx("tx-pending-nocode", comment="Almuerzo con cliente", legalization="Needs Approval")
        self.assertEqual((pending.purchase_order_id.id, pending.reconciliation_state, no_code.purchase_order_id.id), (False, "pending", False))
        order = self._order("P77201")
        self.Transaction._relink_after_sync()
        self.assertEqual((pending.purchase_order_id, pending.reconciliation_state, no_code.purchase_order_id.id), (order, "pending", False))
        # the order is cancelled after the sync: the state follows at once, the link waits for the relink
        approved = self._tx("tx-approved-cancel", comment="P77201", legalization="Approved")
        rejected = self._tx("tx-rejected-cancel", comment="P77201", legalization="Rejected")
        self.assertEqual((approved.purchase_order_id, approved.reconciliation_state, rejected.purchase_order_id), (order, "reconciled", order))
        order.button_cancel()   # the test cancels it, not the module
        self.assertEqual((pending.purchase_order_id, approved.purchase_order_id, approved.reconciliation_state), (order, order, "approved_no_order"))
        self.Transaction._relink_after_sync()
        self.assertEqual((pending.purchase_order_id.id, pending.reconciliation_state), (False, "pending"))
        self.assertEqual((approved.purchase_order_id.id, approved.reconciliation_state), (False, "approved_no_order"))
        self.assertEqual((rejected.purchase_order_id.id, rejected.reconciliation_state), (False, "rejected"))
        # booked again under the same code: the pending and the approved transaction find it on the next relink
        again = self._order("P77201")
        self.Transaction._relink_after_sync()
        self.assertEqual((pending.purchase_order_id, approved.purchase_order_id, approved.reconciliation_state), (again, again, "reconciled"))

    def test_only_settled_purchases_have_a_reconciliation_state(self):
        self.assertFalse(self._tx("tx-payment", tx_type="PAYMENT").reconciliation_state)
        self.assertFalse(self._tx("tx-fee", tx_type="FEE", status="SYSTEM_TRANSACTION").reconciliation_state)
        self.assertFalse(self._tx("tx-declined", status="REJECTED").reconciliation_state)
        self.assertEqual(self._tx("tx-notification", status="NOTIFICATION", legalization="Needs Approval").reconciliation_state, "pending")

    def test_payload_facts_and_scrubbing(self):
        tx = self._tx("tx-facts", comment="P45717\nPaquete Salitre, tienda 140", document="1020304050")
        self.assertEqual((tx.tx_type, tx.has_receipt, tx.approval_status, tx.approval_comment, tx.cardholder_uuid), ("PURCHASE", True, "Approved", "Hola, mil gracias :)", HOLDER_UUID))
        self.assertEqual((tx.clara_comment, tx.card_last_four, tx.cardholder_name, tx.merchant_name, tx.amount, tx.currency_id.name), ("P45717\nPaquete Salitre, tienda 140", "5458", HOLDER, "Uber", 56343.0, "COP"))
        self.assertEqual((str(tx.transaction_date), str(tx.last_update_date), tx.status), ("2026-10-08", "2026-10-10", "authorized"))
        stored = json.loads(tx.raw_payload)
        self.assertNotIn("maskedPan", stored["card"])
        self.assertNotIn("documentNumber", stored["user"])
        self.assertNotIn(MASKED_PAN[:6], tx.raw_payload)
        self.assertNotIn("1020304050", tx.raw_payload)
        self.assertEqual(stored["user"]["holderName"], HOLDER)
        clean = scrub_payload({"merchant": {"taxId": "900714035"}, "user": {"taxId": "1020304050", "name": "x"}, "card": {"pan": "5109790000005458", "lastFour": "5458"}})
        self.assertEqual(clean, {"merchant": {"taxId": "900714035"}, "user": {"name": "x"}, "card": {"lastFour": "5458"}})
