import re
from pathlib import Path

from odoo.modules import get_module_path
from odoo.tests.common import TransactionCase, tagged

from ..models.res_partner import DUE_FIELDS


@tagged("post_install", "-at_install")
class TestSettleDueBridge(TransactionCase):
    """The amount due is not loaded in the POS, and the pieces of pos_settle_due this module relies on
    still exist.

    pos_settle_due is Enterprise: if an update renames what this module intercepts, the interception
    stops working without any error (the override simply no longer applies).  The last two tests fail
    in that case, so the module gets reviewed instead of silently doing nothing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({"name": "Caja deuda (test)"})
        cls.Partner = cls.env["res.partner"]

    def test_enabled_by_default(self):
        self.assertTrue(self.config.skip_partner_due)

    def test_due_fields_are_not_loaded_when_skipped(self):
        loaded = self.Partner._load_pos_data_fields(self.config)
        for fname in DUE_FIELDS:
            self.assertNotIn(fname, loaded)
        self.assertIn("name", loaded, "the other customer fields are still loaded")

    def test_standard_loading_when_not_skipped(self):
        self.config.skip_partner_due = False
        loaded = self.Partner._load_pos_data_fields(self.config)
        for fname in DUE_FIELDS:
            self.assertIn(fname, loaded, "pos_settle_due no longer loads %s: review this module" % fname)

    def test_pos_settle_due_still_defines_the_due_fields(self):
        for fname in DUE_FIELDS:
            self.assertIn(fname, self.Partner._fields, "res.partner.%s is gone: review this module" % fname)

    def test_pos_settle_due_frontend_still_has_what_is_intercepted(self):
        src = Path(get_module_path("pos_settle_due")) / "static" / "src"
        code = "\n".join(path.read_text(encoding="utf-8") for path in src.rglob("*.js"))
        expected = {
            # intercepted in static/src/js/pos_store_patch.js
            "setAllTotalDueOfPartners(": r"setAllTotalDueOfPartners\(",
            "get_all_total_due": r"get_all_total_due",
            # the recomputation after a sale on the customer account only runs when the due is loaded
            "total_due !== undefined": r"total_due\s*!==\s*undefined",
        }
        for label, pattern in expected.items():
            self.assertRegex(code, re.compile(pattern), "pos_settle_due changed (%s): review this module" % label)
