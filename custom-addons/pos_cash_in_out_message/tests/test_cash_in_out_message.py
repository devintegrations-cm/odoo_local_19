from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCashInOutMessage(TransactionCase):
    """Configuration wiring of the Cash In/Out message.

    The message itself is rendered by the POS interface (JavaScript); these
    tests cover the part that can silently break on an upgrade: that the
    settings screen writes through to the point of sale record.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].create({
            "name": "Cash Message Test",
            "type": "cash",
            "code": "CMSG",
            "company_id": cls.company.id,
        })
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash Message Test",
            "journal_id": cls.journal.id,
            "is_cash_count": True,
            "split_transactions": False,
        })
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Message",
            "module_pos_restaurant": False,
            "journal_id": cls.journal.id,
            "payment_method_ids": [(6, 0, [cls.payment_method.id])],
        })

    def _settings(self):
        return self.env["res.config.settings"].create({
            "pos_config_id": self.pos_config.id,
        })

    def test_message_is_disabled_by_default(self):
        """A new point of sale does not ask for confirmation."""
        self.assertFalse(self.pos_config.cash_in_out_message_enabled)
        self.assertFalse(self.pos_config.cash_in_out_message)

    def test_settings_write_message_through_to_pos_config(self):
        """The related field stores the text on pos.config, not on the settings."""
        settings = self._settings()
        settings.pos_cash_in_out_message = "Verifique el monto antes de confirmar."
        settings.pos_cash_in_out_message_enabled = True
        settings.execute()

        self.assertEqual(
            self.pos_config.cash_in_out_message,
            "Verifique el monto antes de confirmar.",
        )
        self.assertTrue(self.pos_config.cash_in_out_message_enabled)

    def test_settings_read_the_current_pos_config_value(self):
        """Opening the settings screen shows what is stored on the point of sale."""
        self.pos_config.write({
            "cash_in_out_message_enabled": True,
            "cash_in_out_message": "Texto existente.",
        })

        settings = self._settings()

        self.assertTrue(settings.pos_cash_in_out_message_enabled)
        self.assertEqual(settings.pos_cash_in_out_message, "Texto existente.")

    def test_settings_fields_are_prefixed_to_avoid_collisions(self):
        """Names without the pos_ prefix would collide on the shared settings model."""
        fields = self.env["res.config.settings"]._fields
        self.assertIn("pos_cash_in_out_message", fields)
        self.assertIn("pos_cash_in_out_message_enabled", fields)
        self.assertNotIn("cash_in_out_message", fields)

    def test_disabling_keeps_the_message_text(self):
        """Turning the feature off must not erase the configured text."""
        self.pos_config.write({
            "cash_in_out_message_enabled": True,
            "cash_in_out_message": "Guarde el comprobante.",
        })

        settings = self._settings()
        settings.pos_cash_in_out_message_enabled = False
        settings.execute()

        self.assertFalse(self.pos_config.cash_in_out_message_enabled)
        self.assertEqual(self.pos_config.cash_in_out_message, "Guarde el comprobante.")
