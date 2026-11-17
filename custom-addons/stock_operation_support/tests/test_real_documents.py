# -*- coding: utf-8 -*-
"""Lo que salio de correr el modulo sobre 14 fotos reales de staging (2026-10-07).

Los soportes reales casi nunca son remisiones: son facturas electronicas y
tiquetes de caja, el "recibido" es una anotacion a mano y las unidades del
proveedor rara vez son las de Odoo. Cada test fija uno de esos casos.
"""

from odoo.tests import tagged

from .common import SosCase, parsed_result

NO_SIGNATURES = {
    "sender": {"present": False, "confidence": 0.9, "name": "", "id_number": "",
               "note": "no hay casilla"},
    "receiver": {"present": False, "confidence": 0.9, "name": "", "id_number": "",
                 "note": "no hay casilla"},
}
RECEIPT_MARK_ONLY = {
    "sender": NO_SIGNATURES["sender"],
    "receiver": {"present": True, "confidence": 0.85, "name": "Antonio Valencia",
                 "id_number": "", "note": "P44358 / Antonio Valencia / 28-09 a mano"},
}


@tagged("post_install", "-at_install")
class TestRealDocuments(SosCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_grams = cls.env["product.product"].create({
            "name": "Pechuga de pollo",
            "default_code": "PECDEPOL",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_gram").id,
        })

    def _one(self, picking_lines, doc_lines, **extra):
        picking = self._create_picking(picking_lines)
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(doc_lines, **extra))
        return support

    # --- Firmas segun el tipo de documento ------------------------------

    def test_un_tiquete_de_caja_no_necesita_firmas(self):
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="tiquete_pos", signatures=NO_SIGNATURES)
        self.assertEqual(support.state, "approved", self._codes(support))
        self.assertIn("SIGNATURE_RECEIVER_NOT_REQUIRED", self._codes(support, "ok"))

    def test_una_factura_con_anotacion_de_recibido_queda_aprobada(self):
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="factura", signatures=RECEIPT_MARK_ONLY)
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_una_factura_sin_constancia_de_recibido_es_observacion(self):
        """ABC Cocina y Pelletier: facturas sin nada escrito a mano."""
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="factura", signatures=NO_SIGNATURES)
        self.assertIn("SIGNATURE_RECEIVER_MISSING", self._codes(support, "warning"))
        self.assertEqual(support.state, "warning")

    def test_una_remision_sin_constancia_de_recibido_sigue_siendo_error(self):
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="remision", signatures=NO_SIGNATURES)
        self.assertIn("SIGNATURE_RECEIVER_MISSING", self._codes(support, "error"))
        self.assertNotIn("SIGNATURE_SENDER_MISSING", self._codes(support))

    def test_tirilla_a_nombre_de_otro_es_observacion_no_error(self):
        """Farmatodo: la tirilla salio a nombre de 'Tienda 9 Caja 11'."""
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="tiquete_pos", signatures=NO_SIGNATURES,
                            receiver={"nit": "20250401911", "dv": "", "name": "Tienda 9 Caja 11"})
        self.assertIn("RECEIVER_NIT", self._codes(support, "warning"))
        self.assertEqual(support.state, "warning")

    def test_en_una_factura_el_nit_de_quien_recibe_sigue_siendo_error(self):
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            document_type="factura", signatures=RECEIPT_MARK_ONLY,
                            receiver={"nit": "800111222", "dv": "3", "name": "OTRA SAS"})
        self.assertIn("RECEIVER_NIT", self._codes(support, "error"))

    # --- Lineas de servicio ---------------------------------------------

    def test_el_envio_no_cuenta_como_linea_sin_emparejar(self):
        result = parsed_result([("Cafe verde excelso", "CAFE-001", 100.0),
                                ("Envio", "", 1.0)], document_type="factura",
                               signatures=RECEIPT_MARK_ONLY)
        result["lines"][1]["is_service"] = True
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, result)
        self.assertEqual(support.state, "approved", self._codes(support))
        self.assertIn("SERVICE_LINES", self._codes(support, "ok"))
        self.assertFalse(support.line_ids.filtered("is_service").move_id)

    # --- Unidades como las escriben los proveedores ---------------------

    def test_k_es_kilogramo(self):
        """Tiquete de Pueblo Sano: 'AGUACATE PAPELILI 3.070 K'."""
        support = self._one([(self.product_grams, 3070.0)],
                            [("Pechuga de pollo", "PECDEPOL", 3.07)], lines_unit="K")
        self.assertEqual(support.line_ids.uom_status, "converted")
        self.assertEqual(support.line_ids.quantity_converted, 3070.0)

    def test_unidades_x_80_gr_es_unidades(self):
        """Factura de ABC Cocina: la unidad viene como 'Unidades X 80 Gr'."""
        support = self._one([(self.product_cafe, 72.0)], [("Cafe verde excelso", "CAFE-001", 72.0)],
                            lines_unit="Unidades X 80 Gr")
        self.assertEqual(support.line_ids.uom_status, "same")
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_sin_unidad_contra_gramos_no_se_asume_nada(self):
        """Tiquete de BBI: '2 Baguette' contra una recepcion de 1150 g no son 2 g."""
        support = self._one([(self.product_grams, 1150.0)],
                            [("Pechuga de pollo", "PECDEPOL", 2.0)], lines_unit="")
        self.assertEqual(support.line_ids.uom_status, "unknown")
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))

    def test_insumo_en_el_nombre_interno_no_impide_emparejar(self):
        """Frutelli: 'JUGO DE NARANJA POR LITRO' contra 'JUGO DE NARANJA INSUMO'."""
        juice = self.env["product.product"].create({
            "name": "JUGO DE NARANJA INSUMO", "default_code": "JUGDENARINS", "type": "consu", "is_storable": True,
        })
        support = self._one([(juice, 12.0)], [("JUGO DE NARANJA POR LITRO", "12003", 12.0)])
        self.assertEqual(support.line_ids.product_id, juice)
        self.assertEqual(support.line_ids.match_method, "description")

    def test_los_plurales_no_impiden_emparejar(self):
        """'Palitos de Queso Hojaldre' contra 'PALITO DE QUESO HOJALDRE'."""
        support = self._one([(self.product_cafe, 100.0)], [("Cafes verdes excelsos", "", 100.0)])
        self.assertEqual(support.line_ids.match_method, "description")

    # --- Partes ---------------------------------------------------------

    def test_con_el_nit_correcto_la_razon_social_mal_escrita_no_importa(self):
        """'LIBERTARIO COFFE ROASTER SAS' con el NIT de la compania."""
        support = self._one([(self.product_cafe, 100.0)], [("Cafe verde excelso", "", 100.0)],
                            receiver={"nit": "901234567", "dv": "8", "name": "LIBERTARIO COFE"})
        self.assertNotIn("RECEIVER_NAME", self._codes(support))
