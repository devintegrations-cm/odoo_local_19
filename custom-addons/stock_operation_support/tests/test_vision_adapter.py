# -*- coding: utf-8 -*-
"""Tests del adaptador de vision. Codigo puro: no tocan la base de datos."""

import json
from unittest.mock import patch

import requests

from odoo.tests.common import TransactionCase
from odoo.tests import tagged

from ..services import vision_adapter


@tagged("post_install", "-at_install")
class TestVisionAdapter(TransactionCase):

    # ------------------------------------------------------------------
    # Normalizacion
    # ------------------------------------------------------------------

    def test_normalize_nit_deja_solo_digitos(self):
        self.assertEqual(vision_adapter.normalize_nit("900.123.456-7"), "9001234567")
        self.assertEqual(vision_adapter.normalize_nit("  901234567 "), "901234567")
        self.assertEqual(vision_adapter.normalize_nit(None), "")

    def test_same_nit_ignora_el_digito_de_verificacion(self):
        # El caso real: el partner lo guarda con DV y el documento sin el.
        self.assertTrue(vision_adapter.same_nit("900.123.456-7", "900123456"))
        self.assertTrue(vision_adapter.same_nit("900123456", "900123456"))
        self.assertTrue(vision_adapter.same_nit("9001234567", "900123456"))

    def test_same_nit_no_confunde_dos_nit_distintos(self):
        self.assertFalse(vision_adapter.same_nit("900123456", "800999888"))
        # Dos digitos de diferencia al final no es un DV.
        self.assertFalse(vision_adapter.same_nit("90012345678", "900123456"))
        self.assertFalse(vision_adapter.same_nit("", "900123456"))
        self.assertFalse(vision_adapter.same_nit(None, None))

    def test_to_float_acepta_formato_colombiano_y_anglosajon(self):
        self.assertEqual(vision_adapter._to_float("1.234,50"), 1234.50)
        self.assertEqual(vision_adapter._to_float("1,234.50"), 1234.50)
        self.assertEqual(vision_adapter._to_float("1234,5"), 1234.5)
        self.assertEqual(vision_adapter._to_float("basura"), 0.0)
        self.assertEqual(vision_adapter._to_float(None), 0.0)

    def test_issue_date_acepta_iso_y_dia_mes_ano(self):
        self.assertEqual(vision_adapter._issue_date("2026-09-10"), "2026-09-10")
        # Lo que devolvio el modelo en staging: la fecha tal como esta en el
        # papel. En Colombia es dia/mes/ano.
        self.assertEqual(vision_adapter._issue_date("07/10/2026"), "2026-10-07")
        self.assertEqual(vision_adapter._issue_date("31-12-2026"), "2026-12-31")

    def test_issue_date_descarta_lo_que_no_es_una_fecha(self):
        self.assertEqual(vision_adapter._issue_date("ayer"), "")
        self.assertEqual(vision_adapter._issue_date("10/31/2026"), "")
        self.assertEqual(vision_adapter._issue_date("2026-02-30"), "")

    def test_normalize_response_tolera_una_respuesta_incompleta(self):
        result = vision_adapter.normalize_vision_response({"lines": "no es lista"}, "test")
        self.assertTrue(result["available"])
        self.assertEqual(result["lines"], [])
        self.assertFalse(result["signatures"]["sender"]["present"])
        self.assertTrue(any("lineas legibles" in w for w in result["raw_warnings"]))

    def test_normalize_response_rechaza_lo_que_no_es_objeto(self):
        result = vision_adapter.normalize_vision_response(["lista"], "test")
        self.assertFalse(result["available"])

    def test_normalize_response_avisa_cantidad_en_cero(self):
        payload = {
            "lines": [{"description": "Cafe", "code": "", "quantity": 0, "unit": ""}],
        }
        result = vision_adapter.normalize_vision_response(payload, "test")
        self.assertTrue(any("cantidad" in w for w in result["raw_warnings"]))

    def test_normalize_response_acota_la_confianza(self):
        result = vision_adapter.normalize_vision_response({"confidence": 5}, "test")
        self.assertEqual(result["confidence"], 1.0)

    # ------------------------------------------------------------------
    # Tipo de archivo
    # ------------------------------------------------------------------

    def test_media_type_por_extension_y_por_firma(self):
        self.assertEqual(vision_adapter.media_type_for("foto.JPG", b""), "image/jpeg")
        self.assertEqual(vision_adapter.media_type_for("doc.pdf", b""), "application/pdf")
        self.assertEqual(
            vision_adapter.media_type_for("sin_extension", b"%PDF-1.4"), "application/pdf"
        )
        self.assertEqual(
            vision_adapter.media_type_for("sin_extension", b"\xff\xd8\xff\xe0"), "image/jpeg"
        )
        self.assertIsNone(vision_adapter.media_type_for("cosa.txt", b"hola"))

    def test_formato_no_reconocido_queda_degradado(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        result = adapter.extract(b"hola", "cosa.txt")
        self.assertFalse(result["available"])
        self.assertIn("formato no reconocido", result["error"])

    def test_archivo_demasiado_grande_queda_degradado(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        big = b"\xff\xd8\xff" + b"\x00" * vision_adapter.MAX_IMAGE_BYTES
        result = adapter.extract(big, "foto.jpg")
        self.assertFalse(result["available"])
        self.assertIn("limite", result["error"])

    # ------------------------------------------------------------------
    # Reduccion de la foto
    # ------------------------------------------------------------------

    def _photo(self, size, fmt="JPEG", exif_orientation=None):
        import io

        from PIL import Image

        image = Image.new("RGB", size, (200, 180, 150))
        output = io.BytesIO()
        kwargs = {}
        if exif_orientation:
            exif = Image.Exif()
            exif[0x0112] = exif_orientation
            kwargs["exif"] = exif.tobytes()
        image.save(output, format=fmt, **kwargs)
        return output.getvalue()

    def _size_of(self, file_bytes):
        import io

        from PIL import Image

        return Image.open(io.BytesIO(file_bytes)).size

    def test_una_foto_de_celular_se_reduce_antes_de_enviarla(self):
        photo = self._photo((4000, 3000))
        reduced, filename = vision_adapter.prepare_image(photo, "IMG_2031.jpeg")
        self.assertEqual(self._size_of(reduced), (1600, 1200))
        self.assertEqual(filename, "IMG_2031.jpg")

    def test_una_foto_que_pesa_mas_del_limite_queda_por_debajo(self):
        # Ruido: el peor caso para el JPEG, como una foto real con mucho detalle.
        import io
        import os

        from PIL import Image

        image = Image.frombytes("RGB", (2400, 2400), os.urandom(2400 * 2400 * 3))
        output = io.BytesIO()
        image.save(output, format="PNG")
        photo = output.getvalue()
        self.assertGreater(vision_adapter.encoded_size(photo), vision_adapter.MAX_IMAGE_BYTES)
        reduced, filename = vision_adapter.prepare_image(photo, "remision.png")
        self.assertLessEqual(vision_adapter.encoded_size(reduced), vision_adapter.MAX_IMAGE_BYTES)
        self.assertEqual(vision_adapter.media_type_for(filename, reduced), "image/jpeg")

    def test_una_foto_vertical_se_endereza_segun_el_exif(self):
        # Orientacion 6: el celular la guardo acostada y la marca para rotarla.
        photo = self._photo((4000, 3000), exif_orientation=6)
        reduced, _filename = vision_adapter.prepare_image(photo, "foto.jpg")
        self.assertEqual(self._size_of(reduced), (1200, 1600))

    def test_una_foto_pequena_se_envia_tal_cual(self):
        photo = self._photo((1200, 900))
        self.assertEqual(vision_adapter.prepare_image(photo, "foto.jpg"), (photo, "foto.jpg"))

    def test_un_pdf_o_un_archivo_raro_no_se_tocan(self):
        pdf = b"%PDF-1.4 contenido"
        self.assertEqual(vision_adapter.prepare_image(pdf, "remision.pdf"), (pdf, "remision.pdf"))
        broken = b"\xff\xd8\xff" + b"\x00" * 50
        self.assertEqual(vision_adapter.prepare_image(broken, "rota.jpg"), (broken, "rota.jpg"))

    # ------------------------------------------------------------------
    # Cuerpo de la peticion
    # ------------------------------------------------------------------

    def test_el_cuerpo_lleva_la_imagen_antes_del_texto(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        body = adapter._body(b"\xff\xd8\xff\xe0datos", "foto.jpg", None)
        content = body["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["media_type"], "image/jpeg")
        self.assertEqual(content[1]["type"], "text")
        self.assertEqual(
            body["output_config"]["format"]["type"], "json_schema"
        )

    def test_un_pdf_va_como_documento_no_como_imagen(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        body = adapter._body(b"%PDF-1.4 datos", "remision.pdf", None)
        self.assertEqual(body["messages"][0]["content"][0]["type"], "document")

    def test_el_hint_no_le_dice_a_la_ia_que_resultado_queremos(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        text = adapter._user_text({"expected_sender": "CAFES DEL SUR"})
        self.assertIn("CAFES DEL SUR", text)
        self.assertIn("transcribe lo que dice el documento", text)

    # ------------------------------------------------------------------
    # Fallos del servicio: ninguno es fatal
    # ------------------------------------------------------------------

    def _response(self, status=200, payload=None, raise_value_error=False):
        class FakeResponse:
            status_code = status

            def json(self):
                if raise_value_error:
                    raise ValueError("no es json")
                return payload

        return FakeResponse()

    def test_sin_api_key_queda_degradado(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="")
        result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])

    def test_error_de_red_no_es_fatal(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        with patch.object(requests, "post", side_effect=requests.ConnectionError()):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "ConnectionError")

    def test_timeout_no_es_fatal(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        with patch.object(requests, "post", side_effect=requests.Timeout()):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])

    def test_http_401_no_es_fatal(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        response = self._response(401, {"error": {"message": "invalid key"}})
        with patch.object(requests, "post", return_value=response):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])
        self.assertIn("401", result["error"])

    def test_respuesta_basura_no_es_fatal(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        response = self._response(200, None, raise_value_error=True)
        with patch.object(requests, "post", return_value=response):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])

    def test_un_rechazo_del_modelo_no_asigna_nada(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        response = self._response(200, {"stop_reason": "refusal", "content": []})
        with patch.object(requests, "post", return_value=response):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])
        self.assertIn("rechazo", result["error"])

    def test_max_tokens_se_trata_como_fallo(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        response = self._response(200, {"stop_reason": "max_tokens", "content": []})
        with patch.object(requests, "post", return_value=response):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])

    def test_respuesta_buena_se_normaliza(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        payload = {
            "remission_ref": "REM-9",
            "issue_date": "2026-09-10",
            "sender": {"nit": "900.123.456-7", "dv": "7", "name": "CAFES"},
            "receiver": {"nit": "901234567", "dv": "8", "name": "LIBERTARIO"},
            "lines": [{"description": "Cafe", "code": "CAFE-001",
                       "quantity": "10,5", "unit": "KG"}],
            "signatures": {
                "sender": {"present": True, "confidence": 0.9, "name": "Juan",
                           "id_number": "", "note": ""},
                "receiver": {"present": False, "confidence": 0.8, "name": "",
                             "id_number": "", "note": "no hay casilla"},
            },
            "confidence": 0.85,
            "raw_warnings": [],
        }
        response = self._response(200, {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "usage": {"input_tokens": 100},
            "model": "claude-opus-5",
        })
        with patch.object(requests, "post", return_value=response):
            result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertTrue(result["available"])
        self.assertEqual(result["sender"]["nit"], "9001234567")
        self.assertEqual(result["lines"][0]["quantity"], 10.5)
        self.assertTrue(result["signatures"]["sender"]["present"])
        self.assertFalse(result["signatures"]["receiver"]["present"])

    def test_servicio_http_propio_sin_url_queda_degradado(self):
        adapter = vision_adapter.HttpVisionAdapter(url="")
        result = adapter.extract(b"\xff\xd8\xff", "foto.jpg")
        self.assertFalse(result["available"])

    def test_el_puente_de_cli_usa_la_herramienta_como_modelo(self):
        adapter = vision_adapter.CliVisionAdapter("claude-empresa")
        self.assertEqual(adapter.model, "claude-empresa")
        self.assertEqual(adapter.url, vision_adapter.DEFAULT_CLI_URL)
        # Una herramienta desconocida cae en la primera, no revienta.
        self.assertEqual(
            vision_adapter.CliVisionAdapter("inventada").model, vision_adapter.CLI_TOOLS[0]
        )

    # ------------------------------------------------------------------
    # Fabrica
    # ------------------------------------------------------------------

    def test_la_vision_apagada_devuelve_noop(self):
        self.env["ir.config_parameter"].sudo().set_param("sos.vision_enabled", "False")
        adapter = vision_adapter.get_vision_adapter(self.env)
        self.assertIsInstance(adapter, vision_adapter.NoopVisionAdapter)

    def test_la_cli_manda_sobre_el_proveedor(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sos.vision_enabled", "True")
        params.set_param("sos.vision_provider", "anthropic")
        params.set_param("sos.vision_api_key", "sk-test")
        params.set_param("sos.vision_cli_enabled", "True")
        params.set_param("sos.vision_cli_tool", "claude-empresa")
        adapter = vision_adapter.get_vision_adapter(self.env)
        self.assertIsInstance(adapter, vision_adapter.CliVisionAdapter)

    def test_anthropic_sin_api_key_cae_en_noop(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sos.vision_enabled", "True")
        params.set_param("sos.vision_cli_enabled", "False")
        params.set_param("sos.vision_provider", "anthropic")
        params.set_param("sos.vision_api_key", "")
        adapter = vision_adapter.get_vision_adapter(self.env)
        self.assertIsInstance(adapter, vision_adapter.NoopVisionAdapter)

    # ------------------------------------------------------------------
    # Emparejamiento de unidades por IA
    # ------------------------------------------------------------------

    def test_match_units_manda_texto_y_normaliza_la_respuesta(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        payload = {"lines": [{"index": 7, "move_id": 31, "factor": "24", "source": "document",
                              "evidence": "caja x 24", "confidence": 1.4}]}
        response = self._response(200, {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(payload)}],
        })
        with patch.object(requests, "post", return_value=response) as post:
            result = adapter.match_units(
                [{"index": 7, "code": "", "description": "caja x 24", "quantity": 2, "unit": "CAJA"}],
                [{"move_id": 31, "code": "EMP", "product": "Empaque", "uom": "Units",
                  "purchase_uom": "Units", "packagings": []}],
            )
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["output_config"]["format"]["schema"], vision_adapter.UNITS_SCHEMA)
        self.assertNotIn("image", json.dumps(body["messages"]))
        self.assertEqual(result, [{"index": 7, "move_id": 31, "factor": 24.0,
                                   "source": "document", "evidence": "caja x 24",
                                   "confidence": 1.0}])

    def test_match_units_con_fallo_devuelve_none(self):
        adapter = vision_adapter.AnthropicVisionAdapter(api_key="k")
        with patch.object(requests, "post", side_effect=requests.Timeout()):
            self.assertIsNone(adapter.match_units([{"index": 1}], [{"move_id": 1}]))

    def test_tipo_de_documento_y_servicios_se_normalizan(self):
        result = vision_adapter.normalize_vision_response({
            "document_type": "cualquier cosa",
            "lines": [{"description": "Envio", "quantity": 1, "is_service": True}],
        }, "test")
        self.assertEqual(result["document_type"], "otro")
        self.assertTrue(result["lines"][0]["is_service"])
