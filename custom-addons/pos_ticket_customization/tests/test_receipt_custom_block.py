import base64
import io

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..models.pos_receipt_custom_block import (
    CONTENT_REQUIRED_TYPES,
    MAX_CODE_SIDE,
    POS_LOADED_FIELDS,
    SIZELESS_TYPES,
)


@tagged('post_install', '-at_install')
class TestPosReceiptCustomBlock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.block_model = cls.env['pos.receipt.custom.block']
        cls.config = cls.env['pos.config'].create({'name': 'Tienda de pruebas'})
        cls.other_config = cls.env['pos.config'].create({'name': 'Otra tienda'})

    def _block(self, **values):
        values.setdefault('config_id', self.config.id)
        return self.block_model.create(values)


class TestConstraints(TestPosReceiptCustomBlock):
    """Las validaciones existen para que una mala configuración se detecte al
    guardar y no en el ticket del cliente, donde ya no hay quien la vea."""

    def test_content_required_by_type(self):
        for block_type in CONTENT_REQUIRED_TYPES:
            with self.subTest(block_type=block_type), self.assertRaises(ValidationError):
                self._block(block_type=block_type, content='   ')

    def test_type_specific_requirements(self):
        cases = [
            ({'block_type': 'image'}, 'imagen sin binario'),
            ({'block_type': 'whatsapp_qr', 'wa_number': ' '}, 'WhatsApp sin número'),
            ({'block_type': 'wifi_qr', 'wifi_ssid': ''}, 'WiFi sin SSID'),
            ({'block_type': 'vcard_qr', 'vcard_name': None}, 'vCard sin nombre'),
        ]
        for values, label in cases:
            with self.subTest(caso=label), self.assertRaises(ValidationError):
                self._block(**values)

    def test_separator_needs_nothing(self):
        block = self._block(block_type='separator')
        self.assertTrue(block.exists())

    def test_ean_encoding_is_validated(self):
        with self.assertRaises(ValidationError):
            self._block(block_type='barcode', barcode_type='EAN13', content='123')
        # Dígito de control correcto: debe pasar.
        self._block(block_type='barcode', barcode_type='EAN13', content='5901234123457')

    def test_ean_validation_skipped_for_placeholders(self):
        """El valor real solo se conoce al imprimir, así que no se puede validar."""
        block = self._block(
            block_type='barcode', barcode_type='EAN13', content='{tracking_number}'
        )
        self.assertTrue(block.exists())

    def test_date_window_must_be_ordered(self):
        with self.assertRaises(ValidationError):
            self._block(
                block_type='text', content='x',
                date_start='2026-12-31', date_stop='2026-01-01',
            )

    def test_frequency_bounds(self):
        with self.assertRaises(ValidationError):
            self._block(block_type='text', content='x', frequency=0)
        with self.assertRaises(ValidationError):
            self._block(block_type='text', content='x', frequency=3, frequency_offset=3)
        with self.assertRaises(ValidationError):
            self._block(block_type='text', content='x', frequency=3, frequency_offset=-1)
        block = self._block(block_type='text', content='x', frequency=3, frequency_offset=2)
        self.assertTrue(block.exists())


class TestCodeSize(TestPosReceiptCustomBlock):
    """El tope de tamaño no es estético: por encima de los límites de
    `ir.actions.report.barcode()` el endpoint responde 200 con un cuerpo HTML y
    el ticket sale con la imagen rota, sin ningún error en el log."""

    def test_size_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._block(block_type='url_qr', content='https://x.co', barcode_width=0)
        with self.assertRaises(ValidationError):
            self._block(block_type='url_qr', content='https://x.co', barcode_height=-1)

    def test_size_upper_bound(self):
        self._block(
            block_type='url_qr', content='https://x.co',
            barcode_width=MAX_CODE_SIDE, barcode_height=MAX_CODE_SIDE,
        )
        for width, height in [(MAX_CODE_SIDE + 1, 150), (150, MAX_CODE_SIDE + 1)]:
            with self.subTest(width=width, height=height), self.assertRaises(ValidationError):
                self._block(
                    block_type='url_qr', content='https://x.co',
                    barcode_width=width, barcode_height=height,
                )

    def test_size_ignored_for_blocks_without_image(self):
        for block_type in SIZELESS_TYPES:
            with self.subTest(block_type=block_type):
                block = self._block(
                    block_type=block_type, content='x',
                    barcode_width=99999, barcode_height=99999,
                )
                self.assertTrue(block.exists())

    def test_max_side_stays_within_core_limits(self):
        """Guarda contra un cambio del core: si `barcode()` endureciera sus
        límites, `MAX_CODE_SIDE` dejaría de proteger y esto lo avisaría."""
        image = self.env['ir.actions.report'].barcode(
            'QR', 'https://libertario.co', width=MAX_CODE_SIDE, height=MAX_CODE_SIDE
        )
        self.assertTrue(image, 'el core debe poder generar un código del tamaño máximo permitido')

    def test_every_barcode_type_is_a_real_reportlab_widget(self):
        """"Code39" e "ITF" no son nombres válidos de ReportLab: sus equivalentes
        son "Standard39" e "I2of5". Un nombre inválido provoca un `KeyError` que
        `barcode()` no captura, así que el endpoint devuelve un 500."""
        valores = {
            'Code128': 'ORDEN-00042',
            'Standard39': 'ABC123',
            'Extended39': 'abc123',
            'Standard93': 'ABC123',
            'EAN13': '5901234123457',
            'EAN8': '96385074',
            'UPCA': '036000291452',
            'I2of5': '12345670',
            'Codabar': 'A12345B',
        }
        tipos = dict(self.block_model._fields['barcode_type'].selection)
        self.assertEqual(
            set(tipos), set(valores),
            'hay simbologías en el selector sin valor de prueba (o al revés)',
        )
        for barcode_type, value in valores.items():
            with self.subTest(barcode_type=barcode_type):
                image = self.env['ir.actions.report'].barcode(
                    barcode_type, value, width=300, height=60
                )
                self.assertTrue(image)


class TestImageField(TestPosReceiptCustomBlock):

    def _png(self, width, height):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new('RGB', (width, height), 'red').save(buffer, 'PNG')
        return base64.b64encode(buffer.getvalue())

    def test_image_is_resized_on_write(self):
        """El binario viaja entero en la carga de CADA sesión de POS."""
        from PIL import Image
        block = self._block(block_type='image', image=self._png(2000, 1500))
        stored = Image.open(io.BytesIO(base64.b64decode(block.image)))
        self.assertLessEqual(max(stored.size), 512)
        # Y sin deformar el logo.
        self.assertAlmostEqual(stored.size[0] / stored.size[1], 2000 / 1500, places=2)


class TestPosLoader(TestPosReceiptCustomBlock):
    """Contrato con el frontend del POS."""

    def test_model_is_loaded_in_the_pos(self):
        session = self.env['pos.session'].create({
            'config_id': self.config.id, 'user_id': self.env.uid,
        })
        self.assertIn('pos.receipt.custom.block', session._load_pos_data_models(self.config))

    def test_loaded_fields_all_exist(self):
        """Un campo mal escrito en POS_LOADED_FIELDS rompe la apertura de caja."""
        self.assertEqual(
            self.block_model._load_pos_data_fields(self.config), POS_LOADED_FIELDS,
        )
        desconocidos = set(POS_LOADED_FIELDS) - set(self.block_model._fields)
        self.assertFalse(desconocidos, f'campos inexistentes: {desconocidos}')

    def test_loader_only_returns_own_active_blocks(self):
        mine = self._block(block_type='text', content='mío')
        archived = self._block(block_type='text', content='archivado', active=False)
        others = self._block(block_type='text', content='ajeno', config_id=self.other_config.id)

        loaded_ids = [
            row['id'] for row in self.block_model._load_pos_data_search_read({}, self.config)
        ]

        self.assertIn(mine.id, loaded_ids)
        self.assertNotIn(archived.id, loaded_ids, 'un bloque archivado no debe imprimirse')
        self.assertNotIn(others.id, loaded_ids, 'cada tienda carga solo su configuración')

    def test_loader_respects_sequence(self):
        second = self._block(block_type='text', content='b', sequence=20)
        first = self._block(block_type='text', content='a', sequence=10)
        rows = self.block_model._load_pos_data_search_read({}, self.config)
        self.assertEqual([r['id'] for r in rows], [first.id, second.id])


class TestConfigIntegration(TestPosReceiptCustomBlock):

    def test_company_follows_the_point_of_sale(self):
        block = self._block(block_type='text', content='x')
        self.assertEqual(block.company_id, self.config.company_id)

    def test_display_name_shows_type_and_title(self):
        block = self._block(block_type='text', content='Gracias por su compra')
        self.assertIn('Gracias por su compra', block.display_name)
        labelled = self._block(block_type='wifi_qr', wifi_ssid='X', label='Nuestro WiFi')
        self.assertIn('Nuestro WiFi', labelled.display_name)

    def test_duplicating_a_config_duplicates_its_blocks(self):
        self._block(block_type='text', content='x')
        copy = self.config.copy()
        self.assertEqual(len(copy.custom_receipt_block_ids), 1)
        self.assertNotEqual(
            copy.custom_receipt_block_ids, self.config.custom_receipt_block_ids
        )

    def test_action_is_scoped_to_its_config(self):
        action = self.config.action_open_custom_receipt_blocks()
        self.assertIn(('config_id', '=', self.config.id), action['domain'])
        self.assertEqual(action['context']['default_config_id'], self.config.id)

    def test_settings_counts_only_its_own_blocks(self):
        self._block(block_type='text', content='x')
        self._block(block_type='text', content='y')
        self._block(block_type='text', content='z', config_id=self.other_config.id)
        settings = self.env['res.config.settings'].create({'pos_config_id': self.config.id})
        self.assertEqual(settings.pos_custom_receipt_block_count, 2)
