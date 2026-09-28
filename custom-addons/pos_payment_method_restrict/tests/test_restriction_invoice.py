from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestRestrictionInvoice(TestPoSCommon):
    """La restricción de pago decide `to_invoice` en el servidor y las órdenes
    sin factura se pueden agrupar después en una sola factura."""

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.product = self.create_product('Producto hotel', self.categ_basic, 10.0, 5.0)
        self.hotel = self.env['res.partner'].create({'name': 'Hotel restringido'})
        self.config.write({
            'payment_restrict_enabled': True,
            'payment_customer_restriction_ids': [(0, 0, {
                'payment_method_id': self.pay_later_pm.id,
                'partner_ids': [(6, 0, self.hotel.ids)],
                'to_invoice': False,
            })],
        })
        self.restriction = self.config.payment_customer_restriction_ids
        self.open_new_session()

    def _sync(self, customer, is_invoiced, payment_method=None):
        payment_method = payment_method or self.pay_later_pm
        data = self.create_ui_order_data(
            [(self.product, 1)],
            customer=customer,
            is_invoiced=is_invoiced,
            payments=[(payment_method, 10.0)],
        )
        result = self.env['pos.order'].sync_from_ui([data])
        return self.env['pos.order'].browse(result['pos.order'][0]['id'])

    def test_restriccion_sin_factura_prevalece(self):
        """El POS envía "Facturar" (p. ej. factura obligatoria) pero la
        restricción dice que no: la orden queda pagada y sin factura."""
        order = self._sync(self.hotel, is_invoiced=True)
        self.assertFalse(order.to_invoice)
        self.assertFalse(order.account_move)
        self.assertEqual(order.state, 'paid')

    def test_restriccion_con_factura_prevalece(self):
        """La restricción exige factura aunque el POS no la marque."""
        self.restriction.to_invoice = True
        order = self._sync(self.hotel, is_invoiced=False)
        self.assertTrue(order.to_invoice)
        self.assertTrue(order.account_move)

    def test_cliente_sin_restriccion_no_se_toca(self):
        """Un cliente normal conserva lo que envió el POS."""
        order = self._sync(self.customer, is_invoiced=True, payment_method=self.cash_pm1)
        self.assertTrue(order.to_invoice)
        self.assertTrue(order.account_move)

    def test_restricciones_desactivadas_no_se_toca(self):
        """Con las restricciones apagadas en el POS no se fuerza nada."""
        self.config.payment_restrict_enabled = False
        order = self._sync(self.hotel, is_invoiced=True)
        self.assertTrue(order.to_invoice)
        self.assertTrue(order.account_move)

    def test_factura_agrupada(self):
        """Dos órdenes del hotel sin factura salen en una sola factura con el
        diario de facturas del POS, y no se pueden volver a facturar."""
        orders = self._sync(self.hotel, is_invoiced=True) | self._sync(self.hotel, is_invoiced=True)
        orders.action_pos_grouped_invoice()
        move = orders.account_move
        self.assertEqual(len(move), 1)
        self.assertEqual(move.journal_id, self.config.invoice_journal_id)
        self.assertEqual(move.amount_total, sum(orders.mapped('amount_total')))
        self.assertEqual(set(orders.mapped('state')), {'done'})
        with self.assertRaises(UserError):
            orders.action_pos_grouped_invoice()
