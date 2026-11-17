# -*- coding: utf-8 -*-
"""Tests del flujo completo: leer el soporte, emparejar y correr las reglas."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SosCase, parsed_result


@tagged("post_install", "-at_install")
class TestSupportFlow(SosCase):

    # ------------------------------------------------------------------
    # Caso feliz
    # ------------------------------------------------------------------

    def test_soporte_que_cuadra_queda_aprobado(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        self.assertEqual(support.state, "approved")
        self.assertEqual(support.remission_ref, "REM-001")
        self.assertNotIn("QTY_OVER_OPERATION", self._codes(support))
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))

    def test_las_lineas_se_emparejan_por_codigo(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Lo que sea", "CAFE-001", 100.0),
            ("Cualquier cosa", "EMP-500", 50.0),
        ]))
        self.assertEqual(set(support.line_ids.mapped("match_method")), {"code"})
        self.assertEqual(
            support.line_ids.mapped("product_id"),
            self.product_cafe | self.product_bag,
        )

    def test_la_descripcion_que_contiene_el_nombre_del_producto_se_empareja(self):
        """Caso real de staging: 'Te Chai Dorado bolsa' para 'CHAI DORADO'."""
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Lote cafe verde excelso bolsa x 100", "", 100.0),
            ("Empaque 500 g", "", 50.0),
        ]))
        line = support.line_ids.filtered(lambda l: l.description.startswith("Lote"))
        self.assertEqual(line.product_id, self.product_cafe)
        self.assertEqual(line.match_method, "description")

    def test_las_lineas_se_emparejan_por_descripcion_si_no_hay_codigo(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("CAFE VERDE EXCELSO", "", 100.0),
            ("EMPAQUE 500 G", "", 50.0),
        ]))
        self.assertEqual(set(support.line_ids.mapped("match_method")), {"description"})

    # ------------------------------------------------------------------
    # Cantidades: el corazon del modulo
    # ------------------------------------------------------------------

    def test_mas_cantidad_en_el_soporte_que_en_la_operacion_es_error(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 120.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        self.assertEqual(support.state, "rejected")
        self.assertIn("QTY_OVER_OPERATION", self._codes(support, "error"))

    def test_menos_cantidad_en_el_soporte_que_en_la_operacion_es_error(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 80.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        self.assertEqual(support.state, "rejected")
        self.assertIn("QTY_UNDER_OPERATION", self._codes(support, "error"))

    def test_un_movimiento_que_el_soporte_no_menciona_es_observacion(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertIn("QTY_MISSING_IN_DOCUMENT", self._codes(support, "warning"))

    def test_dos_lineas_del_papel_al_mismo_movimiento_se_suman(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 60.0),
            ("Cafe verde excelso (resto)", "CAFE-001", 40.0),
        ]))
        # La segunda no encuentra movimiento libre, pero la suma es lo que
        # importa: sin emparejar queda la observacion de LINES_MATCHED.
        self.assertIn("LINES_MATCHED", self._codes(support))

    def test_la_tolerancia_absoluta_admite_la_diferencia(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.qty_tolerance_abs", "5")
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 97.0),
        ]))
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))

    def test_la_tolerancia_porcentual_admite_la_diferencia(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.qty_tolerance_pct", "5")
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 96.0),
        ]))
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))

    def test_la_linea_muestra_la_diferencia_y_contra_que_se_comparo(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 90.0),
        ]))
        line = support.line_ids
        self.assertEqual(line.picking_quantity, 100.0)
        self.assertEqual(line.quantity_diff, -10.0)
        self.assertEqual(line.quantity_basis, "esperada")

    # ------------------------------------------------------------------
    # Firmas
    # ------------------------------------------------------------------

    def test_sin_firma_de_quien_recibe_es_error(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            signatures={
                "sender": {"present": True, "confidence": 0.9, "name": "Juan",
                           "id_number": "", "note": ""},
                "receiver": {"present": False, "confidence": 0.9, "name": "",
                             "id_number": "", "note": "casilla vacia"},
            },
        ))
        self.assertEqual(support.state, "rejected")
        self.assertIn("SIGNATURE_RECEIVER_MISSING", self._codes(support, "error"))
        self.assertFalse(support.signature_receiver_ok)

    def test_la_firma_de_quien_entrega_no_se_exige(self):
        """En los soportes reales ningun proveedor la pone; manda el recibido."""
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            signatures={
                "sender": {"present": False, "confidence": 0.9, "name": "",
                           "id_number": "", "note": ""},
                "receiver": {"present": True, "confidence": 0.9, "name": "Ana",
                             "id_number": "", "note": ""},
            },
        ))
        self.assertIn("SIGNATURE_SENDER_NOT_REQUIRED", self._codes(support, "ok"))
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_una_firma_dudosa_es_observacion_no_error(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            signatures={
                "sender": {"present": True, "confidence": 0.9, "name": "Juan",
                           "id_number": "", "note": ""},
                "receiver": {"present": True, "confidence": 0.3, "name": "",
                             "id_number": "", "note": "trazo tenue"},
            },
        ))
        self.assertIn("SIGNATURE_RECEIVER_UNCLEAR", self._codes(support, "warning"))
        self.assertNotIn("SIGNATURE_RECEIVER_MISSING", self._codes(support))

    def test_con_la_revision_de_firmas_apagada_no_se_exigen(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.signature_check", "False")
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            signatures={
                "sender": {"present": False, "confidence": 0.0, "name": "",
                           "id_number": "", "note": ""},
                "receiver": {"present": False, "confidence": 0.0, "name": "",
                             "id_number": "", "note": ""},
            },
        ))
        self.assertNotIn("SIGNATURE_SENDER_MISSING", self._codes(support))
        self.assertEqual(support.state, "approved")

    # ------------------------------------------------------------------
    # Partes: quien entrega y quien recibe
    # ------------------------------------------------------------------

    def test_nit_de_quien_entrega_distinto_es_error(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "800999888", "dv": "1", "name": "OTRA EMPRESA SAS"},
        ))
        self.assertEqual(support.state, "rejected")
        self.assertIn("SENDER_NIT", self._codes(support, "error"))

    def test_nit_de_quien_recibe_distinto_es_error(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            receiver={"nit": "800111222", "dv": "3", "name": "OTRA COMPANIA"},
        ))
        self.assertIn("RECEIVER_NIT", self._codes(support, "error"))

    def test_en_una_recepcion_entrega_el_proveedor_y_recibe_la_compania(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        # El NIT del proveedor va en sender y el de la compania en receiver:
        # asi armado, no hay hallazgo de NIT.
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
        ))
        self.assertNotIn("SENDER_NIT", self._codes(support, "error"))
        self.assertNotIn("RECEIVER_NIT", self._codes(support, "error"))

    def test_razon_social_muy_distinta_es_observacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "900123456", "dv": "7", "name": "FERRETERIA LA 80"},
        ))
        self.assertIn("SENDER_NAME", self._codes(support, "warning"))

    def test_la_forma_societaria_no_cuenta_como_diferencia(self):
        """'CAFES DEL SUR S.A.S.' es la misma empresa que 'CAFES DEL SUR SAS'.

        Salio de la primera prueba con una remision real: el documento escribe
        'S.A.S.' con puntos y el sistema 'SAS', y eso marcaba observacion en
        cada soporte.
        """
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "900123456", "dv": "7", "name": "CAFES DEL SUR S.A.S."},
        ))
        self.assertNotIn("SENDER_NAME", self._codes(support))

    def test_con_la_revision_de_partes_apagada_no_se_compara(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.party_check", "False")
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "800999888", "dv": "1", "name": "OTRA EMPRESA"},
        ))
        self.assertNotIn("SENDER_NIT", self._codes(support))
        self.assertFalse(support.party_check_enabled)

    # ------------------------------------------------------------------
    # Servicio caido y captura manual
    # ------------------------------------------------------------------

    def test_sin_lectura_se_pide_captura_manual_y_no_se_rechaza(self):
        from odoo.addons.stock_operation_support.services import vision_adapter

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, vision_adapter.degraded_result("test", "servicio caido"))
        self.assertEqual(support.state, "warning")
        self.assertIn("MANUAL_CAPTURE_REQUIRED", self._codes(support, "warning"))
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))

    def test_lo_capturado_a_mano_sobrevive_a_un_servicio_caido(self):
        from odoo.addons.stock_operation_support.services import vision_adapter

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        support.write({
            "sender_nit": "900123456",
            "receiver_nit": "901234567",
            "line_ids": [(0, 0, {
                "description": "Cafe verde excelso",
                "code": "CAFE-001",
                "quantity": 100.0,
            })],
        })
        self._validate_with(support, vision_adapter.degraded_result("test", "servicio caido"))
        self.assertEqual(support.sender_nit, "900123456")
        self.assertEqual(len(support.line_ids), 1)
        # Con datos capturados, las reglas de cantidades si corren.
        self.assertNotIn("MANUAL_CAPTURE_REQUIRED", self._codes(support))

    def test_la_captura_manual_completa_queda_aprobada(self):
        """Sin IA, lo que la persona digita en el formulario es lo que se valida."""
        from odoo.addons.stock_operation_support.services import vision_adapter

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        support.write({
            "remission_ref": "REM-555",
            "sender_nit": "900123456",
            "sender_name": "CAFES DEL SUR SAS",
            "receiver_nit": "901234567",
            "receiver_name": "LIBERTARIO COFFEE",
            "signature_sender_ok": True,
            "signature_receiver_ok": True,
            "line_ids": [(0, 0, {
                "description": "Cafe verde excelso",
                "code": "CAFE-001",
                "quantity": 100.0,
            })],
        })
        self._validate_with(support, vision_adapter.degraded_result("noop", "IA apagada"))
        self.assertEqual(support.state, "approved", self._codes(support))
        self.assertIn("MANUAL_CAPTURE", self._codes(support, "ok"))

    def test_si_la_ia_vuelve_solo_llena_lo_que_falta(self):
        """Primero se cayo y alguien capturo; despues la IA lee otra cosa."""
        from odoo.addons.stock_operation_support.services import vision_adapter

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, vision_adapter.degraded_result("test", "servicio caido"))
        support.write({"sender_nit": "900123456", "remission_ref": "REM-A-MANO"})

        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "800999888", "dv": "1", "name": "CAFES DEL SUR SAS"},
        ))
        self.assertEqual(support.sender_nit, "900123456")
        self.assertEqual(support.remission_ref, "REM-A-MANO")
        self.assertEqual(support.receiver_nit, "901234567")
        self.assertEqual(len(support.line_ids), 1)

    def test_una_foto_poco_legible_deja_observacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)], confidence=0.2,
        ))
        self.assertIn("LOW_LEGIBILITY", self._codes(support, "warning"))

    # ------------------------------------------------------------------
    # Emparejamiento manual y revalidacion
    # ------------------------------------------------------------------

    def test_el_emparejamiento_manual_se_conserva_al_revalidar(self):
        picking = self._create_picking()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Producto ilegible", "", 100.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        line = support.line_ids.filtered(lambda l: l.description == "Producto ilegible")
        move_cafe = picking.move_ids.filtered(lambda m: m.product_id == self.product_cafe)
        line.write({
            "move_id": move_cafe.id,
            "match_method": "manual",
            "match_confidence": 1.0,
        })

        self._validate_with(support, parsed_result([
            ("Producto ilegible", "", 100.0),
            ("Empaque 500 g", "EMP-500", 50.0),
        ]))
        line = support.line_ids.filtered(lambda l: l.description == "Producto ilegible")
        self.assertEqual(line.match_method, "manual")
        self.assertEqual(line.move_id, move_cafe)

    def test_revalidar_no_vuelve_a_leer_ni_pisa_lo_corregido(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 90.0)],
            signatures={
                "sender": {"present": True, "confidence": 0.9, "name": "Juan",
                           "id_number": "", "note": ""},
                "receiver": {"present": False, "confidence": 0.8, "name": "",
                             "id_number": "", "note": "firma encima del renglon"},
            },
        ))
        self.assertEqual(support.state, "rejected")

        # La persona mira la foto: la firma si esta y eran 100, no 90.
        support.write({"signature_receiver_ok": True, "signature_receiver_confidence": 1.0})
        support.line_ids.write({"quantity": 100.0})
        adapter = self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 90.0)],
        ))
        self.assertEqual(adapter.calls, [], "Revalidar no debe volver a llamar a la IA")
        self.assertEqual(support.line_ids.quantity, 100.0)
        self.assertEqual(support.state, "approved", self._codes(support))

    def test_volver_a_leer_la_foto_reemplaza_los_datos(self):
        from unittest.mock import patch

        from odoo.addons.stock_operation_support.services import vision_adapter
        from .common import FakeVisionAdapter

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        support.write({"remission_ref": "MAL DIGITADO"})

        adapter = FakeVisionAdapter(parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        with patch.object(vision_adapter, "get_vision_adapter", return_value=adapter):
            support.action_reread()
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(support.remission_ref, "REM-001")

    def test_cambiar_la_foto_empieza_de_cero(self):
        import base64

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        first = support.attachment_id
        self._validate_with(support, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        support.action_reset_to_draft()
        other_photo = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x01" * 64 + b"\xff\xd9")
        support.write({"support_file": other_photo, "support_filename": "otra.jpg"})
        self.assertNotEqual(support.attachment_id, first)
        self.assertTrue(first.exists(), "La foto anterior sigue adjunta a la operacion")
        self.assertFalse(support.remission_ref)
        self.assertFalse(support.line_ids)
        self.assertFalse(support.extracted_json)

        adapter = self._validate_with(support, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)], remission_ref="REM-002",
        ))
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(support.remission_ref, "REM-002")

    def test_volver_a_borrador_limpia_la_validacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        support.action_reset_to_draft()
        self.assertEqual(support.state, "draft")
        self.assertFalse(support.validation_json)

    # ------------------------------------------------------------------
    # Reglas del documento y de la operacion
    # ------------------------------------------------------------------

    def test_la_misma_remision_no_respalda_dos_operaciones(self):
        first = self._create_support(self._create_picking([(self.product_cafe, 100.0)]))
        self._validate_with(first, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        second = self._create_support(self._create_picking([(self.product_cafe, 100.0)]))
        self._validate_with(second, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertIn("REMISSION_DUPLICATE", self._codes(second, "error"))

    def test_la_misma_remision_de_otro_proveedor_no_es_duplicado(self):
        """Cada proveedor numera sus remisiones: dos REM-001 pueden ser distintas."""
        first = self._create_support(self._create_picking([(self.product_cafe, 100.0)]))
        self._validate_with(first, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        second = self._create_support(self._create_picking([(self.product_cafe, 100.0)]))
        self._validate_with(second, parsed_result(
            [("Cafe verde excelso", "CAFE-001", 100.0)],
            sender={"nit": "800999888", "dv": "1", "name": "OTRO PROVEEDOR SAS"},
        ))
        self.assertNotIn("REMISSION_DUPLICATE", self._codes(second))

    def test_otra_foto_de_la_misma_operacion_no_es_duplicado(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        first = self._create_support(picking)
        self._validate_with(first, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        second = self._create_support(picking)
        self._validate_with(second, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        self.assertNotIn("REMISSION_DUPLICATE", self._codes(second))

    def test_una_operacion_cancelada_no_se_respalda(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        picking.action_cancel()
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertIn("PICKING_CANCELLED", self._codes(support, "error"))

    def test_subir_el_mismo_archivo_otra_vez_no_cambia_nada(self):
        from .common import DUMMY_JPEG

        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        first = support.attachment_id
        support.write({"support_file": DUMMY_JPEG, "support_filename": "remision.jpg"})
        self.assertEqual(support.attachment_id, first)
        self.assertEqual(support.remission_ref, "REM-001")

    def test_el_comprobante_queda_adjunto_a_la_operacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        attachment = support.attachment_id
        self.assertEqual((attachment.res_model, attachment.res_id), ("stock.picking", picking.id))
        self.assertEqual(attachment.name, "remision.jpg")
        self.assertFalse(attachment.res_field)

    def test_se_usa_la_foto_que_ya_estaba_adjunta_a_la_operacion(self):
        from .common import DUMMY_JPEG

        picking = self._create_picking([(self.product_cafe, 100.0)])
        photo = self.env["ir.attachment"].create({
            "name": "WhatsApp Image.jpeg", "datas": DUMMY_JPEG,
            "res_model": "stock.picking", "res_id": picking.id,
        })
        action = picking.action_add_operation_support()
        self.assertEqual(action["context"]["default_attachment_id"], photo.id)

        before = self.env["ir.attachment"].search_count([])
        support = self.env["stock.operation.support"].create({
            "picking_id": picking.id, "attachment_id": photo.id,
        })
        adapter = self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertEqual(adapter.calls[0]["filename"], "WhatsApp Image.jpeg")
        self.assertEqual(support.state, "approved")
        self.assertEqual(self.env["ir.attachment"].search_count([]), before,
                         "No se debe copiar la foto")

    def test_no_se_acepta_un_adjunto_de_otra_operacion(self):
        from odoo.exceptions import ValidationError
        from .common import DUMMY_JPEG

        other = self._create_picking([(self.product_cafe, 1.0)])
        foreign = self.env["ir.attachment"].create({
            "name": "otra.jpg", "datas": DUMMY_JPEG,
            "res_model": "stock.picking", "res_id": other.id,
        })
        picking = self._create_picking([(self.product_cafe, 100.0)])
        with self.assertRaises(ValidationError):
            self.env["stock.operation.support"].create({
                "picking_id": picking.id, "attachment_id": foreign.id,
            })

    def test_validar_sin_comprobante_avisa(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking, support_file=False)
        with self.assertRaises(UserError):
            support.action_validate()

    # ------------------------------------------------------------------
    # Integracion con la operacion de inventario
    # ------------------------------------------------------------------

    def test_el_modulo_no_bloquea_la_validacion_de_la_operacion(self):
        """Lo acordado: el soporte solo advierte."""
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 10.0),
        ]))
        self.assertEqual(support.state, "rejected")

        picking.move_ids.write({"quantity": 100.0, "picked": True})
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_el_contador_y_el_estado_del_soporte_suben_a_la_operacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        self.assertEqual(picking.support_state, "none")
        support = self._create_support(picking)
        self.assertEqual(picking.support_count, 1)
        self.assertEqual(picking.support_state, "draft")
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertEqual(picking.support_state, "approved")

    def test_el_soporte_mas_reciente_manda_en_la_operacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        bad = self._create_support(picking)
        self._validate_with(bad, parsed_result([("Cafe verde excelso", "CAFE-001", 10.0)]))
        self.assertEqual(picking.support_state, "rejected")
        good = self._create_support(picking)
        self._validate_with(good, parsed_result([("Cafe verde excelso", "CAFE-001", 100.0)]))
        self.assertEqual(picking.support_state, "approved")

    def test_el_veredicto_queda_en_el_chatter_de_la_operacion(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        support = self._create_support(picking)
        before = len(picking.message_ids)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 100.0),
        ]))
        self.assertGreater(len(picking.message_ids), before)

    def test_el_boton_de_la_operacion_abre_el_soporte_con_todo_puesto(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        action = picking.action_add_operation_support()
        self.assertEqual(action["res_model"], "stock.operation.support")
        self.assertEqual(action["context"]["default_picking_id"], picking.id)

    def test_cuando_la_operacion_esta_hecha_se_compara_contra_lo_registrado(self):
        picking = self._create_picking([(self.product_cafe, 100.0)])
        picking.move_ids.write({"quantity": 95.0, "picked": True})
        picking.button_validate()
        support = self._create_support(picking)
        self._validate_with(support, parsed_result([
            ("Cafe verde excelso", "CAFE-001", 95.0),
        ]))
        self.assertEqual(support.line_ids.quantity_basis, "registrada")
        self.assertNotIn("QTY_UNDER_OPERATION", self._codes(support))
