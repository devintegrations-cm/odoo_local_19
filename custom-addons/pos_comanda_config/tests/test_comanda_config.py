from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComandaConfig(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Tienda comanda'})

    def test_defaults_compactos_en_espanol(self):
        """Los defaults replican la comanda compacta en español de Odoo 17."""
        self.assertEqual(self.config.comanda_padding_top, 0)
        self.assertEqual(self.config.comanda_padding_bottom, 0)
        self.assertTrue(self.config.comanda_show_employee)
        self.assertTrue(self.config.comanda_show_reference)
        self.assertTrue(self.config.comanda_spanish_labels)

    def test_espaciado_configurable(self):
        """El espaciado se puede ajustar dentro del rango admitido."""
        self.config.write({
            'comanda_padding_top': 20,
            'comanda_padding_bottom': 10,
        })
        self.assertEqual(self.config.comanda_padding_top, 20)
        self.assertEqual(self.config.comanda_padding_bottom, 10)

    def test_espaciado_fuera_de_rango(self):
        """El espaciado se acota a 0-100 px: valores extremos o negativos no pasan."""
        with self.assertRaises(ValidationError):
            self.config.comanda_padding_top = 101
        with self.assertRaises(ValidationError):
            self.config.comanda_padding_bottom = -1
