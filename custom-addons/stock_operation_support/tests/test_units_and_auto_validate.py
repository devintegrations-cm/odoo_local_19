# -*- coding: utf-8 -*-
"""Unidades distintas entre el papel y la operacion, y validacion automatica."""

from odoo.tests import tagged

from .common import SosCase, parsed_result


def ai_factor(factor, source="document", evidence="caja x 24", confidence=0.9, move_index=0):
    """IA simulada: asocia cada linea pendiente al movimiento indicado con ese factor."""
    def units(lines, moves):
        return [{
            "index": line["index"], "move_id": moves[move_index]["move_id"],
            "factor": factor, "source": source, "evidence": evidence,
            "confidence": confidence,
        } for line in lines]
    return units


@tagged("post_install", "-at_install")
class TestUnits(SosCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_grams = cls.env["product.product"].create({
            "name": "Cafe tostado molido",
            "default_code": "CAF-TOS",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_gram").id,
        })

    def test_kg_contra_g_lo_convierte_odoo_sin_ia(self):
        picking = self._create_picking([(self.product_grams, 5000.0)])
        support = self._create_support(picking)
        adapter = self._validate_with(support, parsed_result([
            ("Cafe tostado molido", "CAF-TOS", 5.0),
        ], lines_unit="KG"))
        line = support.line_ids
        self.assertEqual(line.uom_status, "converted")
        self.assertEqual(line.quantity_converted, 5000.0)
        self.assertEqual(adapter.unit_calls, [], "Odoo sabe convertir: no hace falta la IA")
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_caja_por_24_la_resuelve_la_ia_con_respaldo_en_el_papel(self):
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        adapter = self._validate_with(support, parsed_result([
            ("Empaque 500 g caja x 24", "EMP-500", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(24.0))
        line = support.line_ids
        self.assertEqual(line.match_method, "code")
        self.assertEqual(line.uom_status, "ai")
        self.assertEqual(line.quantity_converted, 48.0)
        self.assertEqual(support.state, "approved", self._codes(support))
        self.assertEqual(len(adapter.unit_calls), 1)

    def test_a_la_ia_no_se_le_mandan_las_cantidades_de_la_operacion(self):
        """Si las viera, podria inventar el factor que hace cuadrar las cifras."""
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        adapter = self._validate_with(support, parsed_result([
            ("Empaque 500 g caja x 24", "EMP-500", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(24.0))
        for move in adapter.unit_calls[0]["moves"]:
            self.assertFalse({"quantity", "product_uom_qty", "demand"} & set(move))

    def test_un_factor_de_la_ia_sin_respaldo_queda_en_observacion(self):
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Empaque 500 g", "EMP-500", 2.0),
        ], lines_unit="PACA"), units=ai_factor(24.0, evidence="supongo 24"))
        self.assertEqual(support.line_ids.uom_status, "ai_unverified")
        self.assertIn("UOM_CONVERSION_UNVERIFIED", self._codes(support, "warning"))
        self.assertNotEqual(support.state, "approved")

    def test_un_numero_suelto_en_la_descripcion_no_respalda_el_factor(self):
        """'Vaso 9 oz' contado en Unidades: el 9 no es cuantos vasos trae la caja."""
        picking = self._create_picking([(self.product_bag, 18.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Vaso azul 9 oz", "EMP-500", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(9.0, evidence="9 oz"))
        self.assertEqual(support.line_ids.uom_status, "ai_unverified")

    def test_bulto_de_25_kg_contra_gramos_lo_respalda_el_papel(self):
        picking = self._create_picking([(self.product_grams, 50000.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe tostado molido bulto 25 kg", "CAF-TOS", 2.0),
        ], lines_unit="BULTO"), units=ai_factor(25000.0, evidence="bulto 25 kg"))
        self.assertEqual(support.line_ids.uom_status, "ai")
        self.assertEqual(support.line_ids.quantity_converted, 50000.0)

    def test_el_empaque_registrado_del_producto_respalda_el_factor(self):
        # En 19 el empaque es una unidad de medida del producto (uom_ids). Se
        # nombra distinto de lo que dice el papel ("CAJA") para que la unidad
        # no se resuelva por nombre y el factor tenga que venir de la IA.
        self.product_bag.uom_ids = [(4, self._packaging_uom("Empaque x 24 und", 24.0).id)]
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Empaque 500 g", "EMP-500", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(24.0, source="packaging", evidence="Caja"))
        self.assertEqual(support.line_ids.uom_status, "ai")
        self.assertEqual(support.state, "approved", self._codes(support))

    def _packaging_uom(self, name, units):
        return self.env["uom.uom"].create({
            "name": name, "relative_factor": units,
            "relative_uom_id": self.env.ref("uom.product_uom_unit").id,
        })

    def test_un_empaque_de_otra_familia_no_respalda_el_factor(self):
        """Un empaque en Unidades no dice nada de un producto que se cuenta en gramos."""
        self.product_grams.uom_ids = [(4, self._packaging_uom("Empaque x 24 und", 24.0).id)]
        picking = self._create_picking([(self.product_grams, 48.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe tostado molido", "CAF-TOS", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(24.0, source="packaging", evidence="Caja"))
        self.assertEqual(support.line_ids.uom_status, "ai_unverified")

    def test_la_unidad_del_papel_con_nombre_de_empaque_la_convierte_odoo(self):
        """Si el papel dice el nombre exacto de una unidad de Odoo, no hace falta la IA."""
        self._packaging_uom("Caja x 24", 24.0)
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        adapter = self._validate_with(support, parsed_result([
            ("Empaque 500 g", "EMP-500", 2.0),
        ], lines_unit="Caja x 24"))
        line = support.line_ids
        self.assertEqual(line.uom_status, "converted")
        self.assertEqual(line.quantity_converted, 48.0)
        self.assertEqual(adapter.unit_calls, [])

    def test_sin_unidad_en_el_papel_contra_gramos_no_se_asume_nada(self):
        """'2 Baguette' contra una recepcion en gramos no son 2 g (en 19 sin categorias)."""
        picking = self._create_picking([(self.product_grams, 2.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe tostado molido", "CAF-TOS", 2.0),
        ], lines_unit=""))
        self.assertEqual(support.line_ids.uom_status, "unknown")

    def test_sin_ia_una_unidad_desconocida_no_se_compara_ni_se_rechaza(self):
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Empaque 500 g", "EMP-500", 2.0),
        ], lines_unit="CAJA"))
        self.assertEqual(support.line_ids.uom_status, "unknown")
        self.assertIn("UOM_UNKNOWN", self._codes(support, "warning"))
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))
        self.assertNotIn("QTY_MISSING_IN_DOCUMENT", self._codes(support))

    def test_la_ia_empareja_una_linea_que_ni_el_codigo_ni_la_descripcion_resuelven(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Grano verde tipo exportacion", "", 100.0),
        ]), units=ai_factor(1.0, evidence="grano verde = cafe verde"))
        line = support.line_ids
        self.assertEqual(line.match_method, "ai")
        self.assertEqual(line.product_id, self.product_cafe)
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_el_factor_puesto_a_mano_se_conserva_al_volver_a_leer(self):
        from unittest.mock import patch

        from odoo.addons.stock_operation_support.services import vision_adapter
        from .common import FakeVisionAdapter

        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        result = parsed_result([("Empaque 500 g", "EMP-500", 2.0)], lines_unit="PACA")
        self._validate_with(support, result)
        support.line_ids.write({"uom_factor": 24.0, "uom_status": "manual"})
        with patch.object(vision_adapter, "get_vision_adapter",
                          return_value=FakeVisionAdapter(result)):
            support.action_reread()
        self.assertEqual(support.line_ids.uom_status, "manual")
        self.assertEqual(support.line_ids.uom_factor, 24.0)
        self.assertEqual(support.state, "approved", self._codes(support))


@tagged("post_install", "-at_install")
class TestAutoValidate(SosCase):

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("sos.auto_validate", "True")

    def _exact(self):
        return parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ])

    def test_una_recepcion_que_cuadra_exacto_se_valida_sola(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, self._exact())
        self.assertEqual(support.state, "approved")
        self.assertEqual(picking.state, "done")
        self.assertEqual(sorted(picking.move_ids.mapped("quantity")), [50.0, 100.0])
        self.assertTrue(any("validada automaticamente" in (message.body or "")
                            for message in picking.message_ids))

    def test_con_conversion_de_unidades_tambien_se_valida(self):
        picking = self._create_picking([(self.product_bag, 48.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Empaque 500 g caja x 24", "EMP-500", 2.0),
        ], lines_unit="CAJA"), units=ai_factor(24.0))
        self.assertEqual(picking.state, "done")

    def test_una_diferencia_dentro_de_la_tolerancia_no_se_valida_sola(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.qty_tolerance_abs", "1")
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 99.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        self.assertEqual(support.state, "approved")
        self.assertEqual(picking.state, "assigned")

    def test_con_observaciones_no_se_valida_sola(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, self._exact() | {"confidence": 0.3})
        self.assertEqual(support.state, "warning")
        self.assertEqual(picking.state, "assigned")

    def test_apagada_en_ajustes_no_valida(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.auto_validate", "False")
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, self._exact())
        self.assertEqual(support.state, "approved")
        self.assertEqual(picking.state, "assigned")

    def test_con_lote_o_serie_no_se_valida_sola(self):
        self.product_cafe.tracking = "lot"
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, self._exact())
        self.assertEqual(support.state, "approved")
        self.assertEqual(picking.state, "assigned")

    def test_el_chatter_muestra_html_y_no_etiquetas(self):
        """Odoo 17 escapa un str en message_post: hay que mandar Markup."""
        self.env["ir.config_parameter"].sudo().set_param("sos.auto_validate", "False")
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, self._exact())
        body = picking.message_ids[0].body
        self.assertIn("<b>%s</b>" % support.name, body)
        self.assertNotIn("&lt;b&gt;", body)
