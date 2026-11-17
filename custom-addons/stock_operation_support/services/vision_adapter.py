# -*- coding: utf-8 -*-
"""Adaptador de IA de vision para digitalizar la remision de una operacion.

La mayoria de los soportes son **fotos** de remisiones firmadas a mano, no
documentos electronicos: no hay XML ni texto seleccionable. Por eso aqui no
hay un OCR de texto plano sino un modelo con vision que devuelve directamente
el JSON del contrato: numero, fecha, partes (razon social y NIT de quien
entrega y de quien recibe), lineas con cantidades, y si cada casilla de firma
tiene o no un trazo.

Reglas que no cambian:

1. **La IA solo digitaliza.** No decide si la operacion esta bien: eso lo
   hacen las reglas duras de ``support_rules.py`` sobre lo que ella extrajo.
2. **Nunca crea ni modifica registros.** La respuesta se guarda como JSON y
   pasa por las reglas.
3. **Cualquier fallo es degradado, no fatal.** Si el servicio no responde, el
   soporte queda en captura manual y la operacion de inventario sigue su
   curso: este modulo nunca bloquea el almacen.

Se usa ``requests`` y no el SDK ``anthropic`` porque la imagen ``odoo:17.0``
no lo trae y el modulo no agrega dependencias Python (ver README).
"""

import base64
import datetime
import io
import json
import logging
import re

import requests

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - Pillow viene en la imagen de Odoo
    Image = ImageOps = None

_logger = logging.getLogger(__name__)

VISION_UNAVAILABLE = "IA de vision no disponible, capturar manualmente."

DEFAULT_TIMEOUT = 90  # una foto tarda mas que un texto
CONNECT_TIMEOUT = 10
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-5-5"
# Opus 5.5 siempre razona antes de responder y eso tambien gasta salida: con
# 8192 una remision larga podia quedar cortada (stop_reason max_tokens).
MAX_TOKENS = 16000

# El puente local de CLI (ver el modulo supplier_invoice_portal, DECISIONS #29).
DEFAULT_CLI_TIMEOUT = 240
DEFAULT_CLI_URL = "http://host.docker.internal:8787/v1/messages"
CLI_TOOLS = ("claude-empresa", "claude-team", "claude-personal", "agy", "codex")

# Limite de la API por imagen, medido sobre el base64 que viaja. Una foto de
# celular pasa de esto con facilidad; por eso las imagenes se reducen antes de
# enviarlas (``prepare_image``) y este tope solo lo alcanza un PDF pesado.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Lado largo con el que se manda una foto. El modelo no lee mejor por encima de
# esto (la API reescala igual) y una remision se sigue leyendo bien.
MAX_IMAGE_SIDE = 1600
JPEG_QUALITY = 85

IMAGE_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

SYSTEM_PROMPT = """Eres un asistente de almacen en Colombia. Recibes la foto o
el escaneo del soporte de una recepcion de mercancia. Puede ser una remision,
una factura electronica de venta o un tiquete de caja (tirilla POS) de un
supermercado: los tres son normales y ninguno es un error.

Tu unica tarea es transcribir lo que ves a JSON. No juzgues si la entrega esta
bien ni corrijas lo que diga el documento: eso lo hace otro sistema.

Reglas:

- Transcribe solo lo que aparece en la imagen. Si un dato no se ve o no estas
  seguro de leerlo, dejalo vacio y anotalo en raw_warnings. NO adivines
  numeros, NIT ni cantidades.
- issue_date va en formato AAAA-MM-DD. En Colombia las fechas se escriben
  dia/mes/ano: 07/10/2026 es el 7 de octubre de 2026.
- En las lineas, quantity es la cantidad entregada tal como esta escrita. Si
  hay una cantidad pedida y una entregada distintas, usa la entregada. Si la
  cantidad esta tachada y corregida a mano, usa la corregida y anotalo en
  raw_warnings.
- code es el codigo o referencia del producto si el documento lo trae; si no,
  dejalo vacio.
- document_type: "remision" (remision o acta de entrega), "factura" (factura
  electronica de venta en hoja), "tiquete_pos" (tirilla de caja registradora)
  u "otro".
- En lines, is_service es true para lo que no es mercancia: envio, domicilio,
  flete, transporte, reintegro, propina, servicio, y la bolsa plastica o de
  empaque en que viene el pedido. Lo demas es false.
- En sender va la empresa que ENTREGA la mercancia y en receiver la que la
  RECIBE. Si la remision tiene membrete de una empresa, esa suele ser la que
  entrega. Transcribe el NIT solo con digitos, sin puntos ni guiones; si trae
  digito de verificacion despues del guion, ponlo aparte en dv.
- unit es la unidad tal como esta escrita (UND, KG, CAJA, BULTO, PACA). Si la
  linea dice el contenido del empaque ("caja x 24", "bulto 25 kg", "bolsa de
  500 g"), dejalo tal cual en description o en unit: hace falta para pasar a
  las unidades del sistema.
- signatures.sender: firma manuscrita de quien entrega, en su casilla.
  present es true solo si ves un trazo; un rotulo "firma" sin trazo es false.
- signatures.receiver es la constancia de recibido: present es true si hay
  CUALQUIER marca manuscrita de recibido en el documento, este o no en una
  casilla: una firma, un nombre, una fecha o un numero de orden de compra
  escritos a mano (por ejemplo "P44358 / Antonio Valencia / 28-09"). En
  note di que marca es y donde esta. Lo impreso no cuenta.
- En signatures, name es el nombre escrito junto a la marca, y id_number la
  cedula si aparece. Vacios si no se ven.
- confidence es que tan legible esta el documento en general, de 0 a 1. Una
  foto borrosa, cortada o muy oscura va por debajo de 0.5.
- raw_warnings es solo para lo que una persona deberia revisar en la foto
  porque afecta lo que transcribiste: un dato ilegible o cortado, una
  cantidad tachada y corregida, una linea dudosa. No anotes datos opcionales
  que el documento no trae (cedula, direccion, codigos), ni el formato de la
  fecha, ni el tipo de documento, ni que una linea es un servicio, ni nada
  sobre firmas o marcas de recibido: eso ya va en sus campos.

Responde unicamente con el JSON del esquema."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "remission_ref": {"type": "string"},
        "issue_date": {"type": "string"},
        "sender": {
            "type": "object",
            "properties": {
                "nit": {"type": "string"},
                "dv": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["nit", "dv", "name"],
            "additionalProperties": False,
        },
        "receiver": {
            "type": "object",
            "properties": {
                "nit": {"type": "string"},
                "dv": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["nit", "dv", "name"],
            "additionalProperties": False,
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "code": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "is_service": {"type": "boolean"},
                },
                "required": ["description", "code", "quantity", "unit", "is_service"],
                "additionalProperties": False,
            },
        },
        "signatures": {
            "type": "object",
            "properties": {
                "sender": {
                    "type": "object",
                    "properties": {
                        "present": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "name": {"type": "string"},
                        "id_number": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["present", "confidence", "name", "id_number", "note"],
                    "additionalProperties": False,
                },
                "receiver": {
                    "type": "object",
                    "properties": {
                        "present": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "name": {"type": "string"},
                        "id_number": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["present", "confidence", "name", "id_number", "note"],
                    "additionalProperties": False,
                },
            },
            "required": ["sender", "receiver"],
            "additionalProperties": False,
        },
        "document_type": {
            "type": "string", "enum": ["remision", "factura", "tiquete_pos", "otro"],
        },
        "confidence": {"type": "number"},
        "raw_warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "remission_ref", "issue_date", "document_type", "sender", "receiver", "lines",
        "signatures", "confidence", "raw_warnings",
    ],
    "additionalProperties": False,
}


UNITS_SYSTEM_PROMPT = """Eres un asistente de almacen en Colombia. Recibes las
lineas ya transcritas de una remision de proveedor y los productos de la
recepcion en el sistema, cada uno con su unidad de medida.

Para cada linea de la remision decide:

- move_id: a que producto de la recepcion corresponde (0 si a ninguno).
- factor: cuantas unidades del sistema equivalen a UNA unidad de la remision.
  Ejemplos: la remision dice 2 CAJA "x 24" y el sistema cuenta en Unidades:
  factor 24. La remision dice 5 KG y el sistema cuenta en g: factor 1000.
- source: de donde sale el factor. "document" si esta escrito en la linea,
  "packaging" si sale de un empaque registrado del producto,
  "unit_conversion" si es una conversion estandar entre unidades, "none" si
  no lo puedes justificar (y entonces factor 0).
- evidence: el texto exacto de la linea o del empaque que respalda el factor.

Empareja tambien cuando es el mismo articulo con otro nombre comercial o
abreviado ("Crema de Avellanas" con "SALSA AVELLANA", "CANA" o "CANASTA" con
"HUEVOS", "Baguette Tradicio..." con "PAN BAGUETTE"), con la confianza que
corresponda. No emparejes un producto con otro distinto solo porque es el
unico que queda.

No conoces las cantidades esperadas a proposito: el factor sale del
documento o del empaque, nunca de hacer cuadrar cifras. Si no hay como
justificarlo, usa factor 0 y source "none"; una persona lo revisara.

Responde unicamente con el JSON del esquema."""

UNITS_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "move_id": {"type": "integer"},
                    "factor": {"type": "number"},
                    "source": {
                        "type": "string",
                        "enum": ["document", "packaging", "unit_conversion", "none"],
                    },
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["index", "move_id", "factor", "source", "evidence", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["lines"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Helpers de normalizacion
# ---------------------------------------------------------------------------

def normalize_nit(value):
    """Deja solo los digitos de un NIT: '900.123.456-7' -> '9001234567'."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def same_nit(a, b):
    """Compara dos NITs ignorando formato y digito de verificacion.

    El comprobante suele traer el NIT sin DV, pero ``res.partner.vat`` lo
    guarda pegado ('900123456-7'). Como los NIT no tienen largo fijo (8 o 9
    digitos de persona juridica, cedulas de 6 a 10), no se recorta a ciegas:
    son iguales si coinciden digito a digito o si uno es el otro mas
    exactamente un digito al final (el DV).

    Mismo criterio que ``supplier_invoice_portal`` (su DECISIONS #3), para que
    los dos modulos no discrepen sobre si dos NIT son el mismo.
    """
    na, nb = normalize_nit(a), normalize_nit(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    longer, shorter = (na, nb) if len(na) > len(nb) else (nb, na)
    return len(longer) == len(shorter) + 1 and longer[:-1] == shorter


def _to_float(value, default=0.0):
    if value is None or value == "":
        return default
    text = str(value).strip()
    # "1.234,50" (Colombia) y "1,234.50" (anglosajon) llegan los dos.
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") \
            else text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _party(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "nit": normalize_nit(raw.get("nit")),
        "dv": re.sub(r"\D", "", str(raw.get("dv") or ""))[:1],
        "name": str(raw.get("name") or "").strip(),
    }


def _signature(raw):
    raw = raw if isinstance(raw, dict) else {}
    confidence = _to_float(raw.get("confidence"), 0.0)
    return {
        "present": bool(raw.get("present")),
        "confidence": max(0.0, min(1.0, confidence)),
        "name": str(raw.get("name") or "").strip()[:200],
        "id_number": str(raw.get("id_number") or "").strip()[:50],
        "note": str(raw.get("note") or "").strip()[:300],
    }


def _line(raw, index):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "sequence": index + 1,
        "description": str(raw.get("description") or "").strip()[:500],
        "code": str(raw.get("code") or "").strip()[:100],
        "quantity": _to_float(raw.get("quantity")),
        "unit": str(raw.get("unit") or "").strip()[:40],
        "is_service": bool(raw.get("is_service")),
    }


def _issue_date(value):
    """Fecha del documento en AAAA-MM-DD, o vacio si no es una fecha valida.

    Se pide ISO en el prompt, pero si el modelo transcribe la fecha tal como
    esta en el papel ('07/10/2026') se interpreta como dia/mes/ano, que es como
    se escribe en Colombia. Es preferible no tener fecha a tener una
    inventada, asi que lo que no sea una fecha real se descarta.
    """
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return ""


def empty_signatures():
    return {
        "sender": _signature(None),
        "receiver": _signature(None),
    }


DOCUMENT_TYPES = ("remision", "factura", "tiquete_pos", "otro")


def degraded_result(provider, reason):
    """Respuesta vacia con el motivo, para cuando el servicio no sirvio."""
    _logger.info("[SOS] Vision degradada (%s): %s", provider, reason)
    return {
        "remission_ref": "",
        "issue_date": "",
        "document_type": "",
        "sender": _party(None),
        "receiver": _party(None),
        "lines": [],
        "signatures": empty_signatures(),
        "confidence": 0.0,
        "provider": provider,
        "available": False,
        "error": str(reason),
        "raw_warnings": [VISION_UNAVAILABLE],
        "raw": {},
    }


def normalize_vision_response(payload, provider):
    """Deja la respuesta con la forma exacta del contrato, sin confiar en nada.

    Numeros como texto, campos ausentes, listas que no son listas: nada de eso
    puede reventar. Lo raro queda anotado en ``raw_warnings``.
    """
    if not isinstance(payload, dict):
        return degraded_result(provider, "la respuesta no es un objeto JSON")

    warnings = [str(w)[:300] for w in (payload.get("raw_warnings") or [])
                if isinstance(payload.get("raw_warnings"), list)]

    raw_lines = payload.get("lines")
    lines = [_line(raw, i) for i, raw in enumerate(raw_lines)] if isinstance(raw_lines, list) else []
    if not isinstance(raw_lines, list):
        warnings.append("La respuesta no traia lineas legibles.")

    signatures_raw = payload.get("signatures")
    signatures_raw = signatures_raw if isinstance(signatures_raw, dict) else {}
    signatures = {
        "sender": _signature(signatures_raw.get("sender")),
        "receiver": _signature(signatures_raw.get("receiver")),
    }

    for line in lines:
        if line["quantity"] <= 0:
            warnings.append(
                "La linea '%s' quedo con cantidad %s." % (line["description"][:60], line["quantity"])
            )

    return {
        "remission_ref": str(payload.get("remission_ref") or "").strip()[:100],
        "issue_date": _issue_date(payload.get("issue_date")),
        "document_type": payload.get("document_type")
        if payload.get("document_type") in DOCUMENT_TYPES else "otro",
        "sender": _party(payload.get("sender")),
        "receiver": _party(payload.get("receiver")),
        "lines": lines,
        "signatures": signatures,
        "confidence": max(0.0, min(1.0, _to_float(payload.get("confidence"), 0.0))),
        "provider": provider,
        "available": True,
        "error": "",
        "raw_warnings": warnings,
        "raw": payload if isinstance(payload, dict) else {},
    }


def media_type_for(filename, file_bytes):
    """Tipo MIME del soporte: imagen conocida, PDF, o None si no se reconoce."""
    extension = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if extension in IMAGE_MEDIA_TYPES:
        return IMAGE_MEDIA_TYPES[extension]
    if extension == "pdf":
        return "application/pdf"
    # Sin extension util, se mira la firma del archivo.
    if file_bytes[:4] == b"%PDF":
        return "application/pdf"
    if file_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    if file_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def encoded_size(file_bytes):
    """Lo que pesa el archivo en base64, que es lo que mide el limite de la API."""
    return (len(file_bytes) + 2) // 3 * 4


def prepare_image(file_bytes, filename):
    """Reduce una foto para que la API la acepte. Devuelve ``(bytes, filename)``.

    Las fotos de celular llegan de 3 a 12 MB y de 4000 px o mas: se rotan segun
    el EXIF (si no, una foto vertical llega acostada), se llevan a
    ``MAX_IMAGE_SIDE`` por el lado largo y se guardan como JPEG. Solo se toca
    lo que se envia: el comprobante guardado en Odoo queda tal cual, como
    evidencia.

    Un PDF, un formato que Pillow no abre o cualquier error devuelven el
    archivo original: el adaptador decide despues si lo puede mandar.
    """
    media_type = media_type_for(filename, file_bytes)
    if Image is None or not media_type or not media_type.startswith("image/"):
        return file_bytes, filename
    if media_type == "image/gif":
        # Un GIF puede ser animado; no vale la pena convertirlo.
        return file_bytes, filename
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
        too_big = max(image.size) > MAX_IMAGE_SIDE
        if not too_big and encoded_size(file_bytes) <= MAX_IMAGE_BYTES:
            return file_bytes, filename
        if too_big:
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.LANCZOS)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    except Exception as error:  # noqa: BLE001 - una foto rara no debe tumbar la validacion
        _logger.warning("[SOS] No se pudo reducir la foto %s: %s", filename, error)
        return file_bytes, filename
    reduced = output.getvalue()
    base = (filename or "remision").rsplit(".", 1)[0]
    _logger.info("[SOS] Foto %s reducida de %.1f MB a %.1f MB (%sx%s)",
                 filename, len(file_bytes) / 1048576.0, len(reduced) / 1048576.0,
                 image.size[0], image.size[1])
    return reduced, "%s.jpg" % base


# ---------------------------------------------------------------------------
# Adaptadores
# ---------------------------------------------------------------------------

class VisionAdapter:
    """Contrato del servicio de vision."""

    name = "base"

    def extract(self, file_bytes, filename, hint=None):
        """Devuelve el dict normalizado del contrato. Nunca lanza excepcion."""
        raise NotImplementedError

    def match_units(self, lines, moves):
        """Empareja lineas y propone factores de unidad. ``None`` si no se puede.

        :param lines: ``[{"index", "code", "description", "quantity", "unit"}]``
        :param moves: ``[{"move_id", "code", "product", "uom", "purchase_uom",
                          "packagings"}]`` -- sin cantidades, a proposito
        :return: lista de dicts ``{"index", "move_id", "factor", "source",
                 "evidence", "confidence"}`` o ``None``
        """
        return None


class NoopVisionAdapter(VisionAdapter):
    """Cuando la vision esta apagada en Ajustes: captura manual."""

    name = "noop"

    def extract(self, file_bytes, filename, hint=None):
        return degraded_result(self.name, "IA de vision desactivada en Ajustes")


class AnthropicVisionAdapter(VisionAdapter):
    """Messages API de Anthropic con bloque de imagen y salida estructurada."""

    name = "anthropic"

    def __init__(self, api_key, model=DEFAULT_MODEL, url=None, timeout=DEFAULT_TIMEOUT):
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.url = url or ANTHROPIC_URL
        self.timeout = timeout or DEFAULT_TIMEOUT

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

    @staticmethod
    def _user_text(hint):
        hint = hint or {}
        parts = ["Transcribe esta remision al JSON del esquema."]
        if hint.get("expected_sender"):
            parts.append(
                "Para ubicarte: se espera que entregue '%s'. Si el documento dice otra "
                "cosa, transcribe lo que dice el documento." % hint["expected_sender"]
            )
        if hint.get("expected_receiver"):
            parts.append(
                "Y que reciba '%s', con el mismo criterio." % hint["expected_receiver"]
            )
        if hint.get("expected_lines"):
            parts.append(
                "La operacion en el sistema tiene estas lineas, solo como referencia de "
                "vocabulario; no las copies si el documento dice otra cosa:\n%s"
                % json.dumps(hint["expected_lines"], ensure_ascii=False, indent=1)
            )
        return "\n\n".join(parts)

    def _body(self, file_bytes, filename, hint):
        media_type = media_type_for(filename, file_bytes)
        encoded = base64.b64encode(file_bytes).decode("ascii")
        if media_type == "application/pdf":
            source_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": media_type, "data": encoded},
            }
        else:
            source_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": encoded},
            }
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            # El documento va antes del texto: es lo recomendado para vision.
            "messages": [{
                "role": "user",
                "content": [source_block, {"type": "text", "text": self._user_text(hint)}],
            }],
            "output_config": {
                "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
            },
        }

    @staticmethod
    def _extract_json(message):
        """Saca el JSON del primer bloque de texto de la respuesta."""
        stop_reason = message.get("stop_reason")
        if stop_reason == "refusal":
            raise ValueError("el modelo rechazo la solicitud")
        if stop_reason == "max_tokens":
            raise ValueError("la respuesta quedo incompleta (max_tokens)")
        for block in message.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                return json.loads(block["text"])
        raise ValueError("la respuesta no trae texto")

    def extract(self, file_bytes, filename, hint=None):
        if not self.api_key:
            return degraded_result(self.name, "API key no configurada")
        if not file_bytes:
            return degraded_result(self.name, "el soporte esta vacio")
        media_type = media_type_for(filename, file_bytes)
        if not media_type:
            return degraded_result(
                self.name, "formato no reconocido (se aceptan JPG, PNG, WEBP, GIF y PDF)"
            )
        if encoded_size(file_bytes) > MAX_IMAGE_BYTES:
            return degraded_result(
                self.name,
                "el archivo pesa %.1f MB y el limite es unos %s MB; si es un PDF, "
                "envie una foto de la remision en su lugar"
                % (len(file_bytes) / 1024.0 / 1024.0, MAX_IMAGE_BYTES * 3 // 4 // (1024 * 1024)),
            )
        try:
            response = requests.post(
                self.url, headers=self._headers(),
                json=self._body(file_bytes, filename, hint),
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
        except requests.RequestException as error:
            _logger.warning("[SOS] Vision (%s): error de conexion (%s)",
                            self.name, error.__class__.__name__)
            return degraded_result(self.name, error.__class__.__name__)
        if response.status_code != 200:
            # El cuerpo del error puede traer detalle util, pero nunca la key.
            detail = ""
            try:
                detail = (response.json().get("error") or {}).get("message") or ""
            except ValueError:
                pass
            _logger.warning("[SOS] Vision (%s): HTTP %s %s",
                            self.name, response.status_code, detail[:200])
            return degraded_result(self.name, "HTTP %s" % response.status_code)
        try:
            message = response.json()
            payload = self._extract_json(message)
        except ValueError as error:
            _logger.warning("[SOS] Vision (%s): respuesta invalida: %s", self.name, error)
            return degraded_result(self.name, "respuesta invalida: %s" % error)
        usage = message.get("usage") or {}
        result = normalize_vision_response(payload, self.name)
        _logger.info(
            "[SOS] Vision (%s) modelo %s: %s lineas, firmas entrega=%s recibe=%s, "
            "legibilidad %.2f, %s tokens entrada",
            self.name, message.get("model") or self.model, len(result["lines"]),
            result["signatures"]["sender"]["present"],
            result["signatures"]["receiver"]["present"],
            result["confidence"], usage.get("input_tokens"),
        )
        return result


    def match_units(self, lines, moves):
        if not self.api_key or not lines or not moves:
            return None
        body = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": UNITS_SYSTEM_PROMPT,
            "messages": [{
                "role": "user",
                "content": json.dumps(
                    {"lineas_remision": lines, "productos_recepcion": moves},
                    ensure_ascii=False, indent=1,
                ),
            }],
            "output_config": {"format": {"type": "json_schema", "schema": UNITS_SCHEMA}},
        }
        try:
            response = requests.post(
                self.url, headers=self._headers(), json=body,
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
            if response.status_code != 200:
                _logger.warning("[SOS] Unidades (%s): HTTP %s", self.name, response.status_code)
                return None
            payload = self._extract_json(response.json())
        except (requests.RequestException, ValueError) as error:
            _logger.warning("[SOS] Unidades (%s): %s", self.name, error)
            return None
        result = []
        for raw in payload.get("lines") or []:
            if not isinstance(raw, dict):
                continue
            result.append({
                "index": int(_to_float(raw.get("index"), -1)),
                "move_id": int(_to_float(raw.get("move_id"), 0)),
                "factor": max(0.0, _to_float(raw.get("factor"), 0.0)),
                "source": str(raw.get("source") or "none"),
                "evidence": str(raw.get("evidence") or "").strip()[:200],
                "confidence": max(0.0, min(1.0, _to_float(raw.get("confidence"), 0.0))),
            })
        _logger.info("[SOS] Unidades (%s): %s propuestas para %s lineas",
                     self.name, len(result), len(lines))
        return result


class HttpVisionAdapter(VisionAdapter):
    """Servicio propio (n8n, FastAPI) que implementa el contrato del README."""

    name = "http"

    def __init__(self, url, api_key=None, timeout=DEFAULT_TIMEOUT):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout or DEFAULT_TIMEOUT

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        return headers

    def extract(self, file_bytes, filename, hint=None):
        if not self.url:
            return degraded_result(self.name, "URL del servicio no configurada")
        if not file_bytes:
            return degraded_result(self.name, "el soporte esta vacio")
        media_type = media_type_for(filename, file_bytes) or "application/octet-stream"
        files = {"file": (filename or "remision.jpg", file_bytes, media_type)}
        data = {"hint": json.dumps(hint or {}, ensure_ascii=False)}
        try:
            response = requests.post(
                self.url, headers=self._headers(), files=files, data=data,
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
        except requests.RequestException as error:
            _logger.warning("[SOS] Vision (%s): error de conexion (%s)",
                            self.name, error.__class__.__name__)
            return degraded_result(self.name, error.__class__.__name__)
        if response.status_code != 200:
            _logger.warning("[SOS] Vision (%s): HTTP %s", self.name, response.status_code)
            return degraded_result(self.name, "HTTP %s" % response.status_code)
        try:
            payload = response.json()
        except ValueError:
            _logger.warning("[SOS] Vision (%s): la respuesta no es JSON", self.name)
            return degraded_result(self.name, "respuesta no es JSON")
        return normalize_vision_response(payload, self.name)


class CliVisionAdapter(AnthropicVisionAdapter):
    """Conexion de prueba: la misma Messages API contra el puente local.

    El puente (``claude_projects/anthropic_cli_bridge``) emula
    ``POST /v1/messages`` y ejecuta la CLI que diga ``model``. Solo para
    desarrollo: sirve para probar con la suscripcion que uno ya tiene, sin API
    key. Si la CLI configurada no acepta imagenes, el puente responde con un
    error y el soporte queda en captura manual, como cualquier otro fallo.
    """

    name = "cli"

    def __init__(self, tool, url=None, api_key=None, timeout=DEFAULT_CLI_TIMEOUT):
        self.tool = tool if tool in CLI_TOOLS else CLI_TOOLS[0]
        super().__init__(
            api_key=api_key or "local", model=self.tool,
            url=url or DEFAULT_CLI_URL, timeout=timeout or DEFAULT_CLI_TIMEOUT,
        )


# ---------------------------------------------------------------------------
# Fabrica
# ---------------------------------------------------------------------------

def _param(env, key, default=None):
    value = env["ir.config_parameter"].sudo().get_param(key)
    return value if value not in (None, False, "") else default


def _param_bool(env, key):
    return str(_param(env, key, "")).lower() in ("true", "1")


def _param_int(env, key, default):
    try:
        return int(_param(env, key, default))
    except (TypeError, ValueError):
        return default


def get_vision_adapter(env):
    """Devuelve la implementacion configurada en Ajustes -> Inventario."""
    if not _param_bool(env, "sos.vision_enabled"):
        return NoopVisionAdapter()

    # La conexion de prueba por CLI manda sobre el proveedor de arriba.
    if _param_bool(env, "sos.vision_cli_enabled"):
        return CliVisionAdapter(
            tool=_param(env, "sos.vision_cli_tool", CLI_TOOLS[0]),
            url=_param(env, "sos.vision_cli_url", DEFAULT_CLI_URL),
            api_key=_param(env, "sos.vision_cli_api_key"),
            timeout=_param_int(env, "sos.vision_cli_timeout", DEFAULT_CLI_TIMEOUT),
        )

    provider = _param(env, "sos.vision_provider", "anthropic")
    if provider == "http":
        url = _param(env, "sos.vision_url")
        if not url:
            _logger.warning("[SOS] Vision HTTP habilitada sin URL. Se usa NoopVisionAdapter.")
            return NoopVisionAdapter()
        return HttpVisionAdapter(
            url=url,
            api_key=_param(env, "sos.vision_api_key"),
            timeout=_param_int(env, "sos.vision_timeout", DEFAULT_TIMEOUT),
        )

    api_key = _param(env, "sos.vision_api_key")
    if not api_key:
        _logger.warning("[SOS] Vision Anthropic habilitada sin API key. Se usa NoopVisionAdapter.")
        return NoopVisionAdapter()
    return AnthropicVisionAdapter(
        api_key=api_key,
        model=_param(env, "sos.vision_model", DEFAULT_MODEL),
        # Solo para pasar por un proxy; con el proveedor anthropic la pantalla
        # de Ajustes no muestra este campo.
        url=_param(env, "sos.vision_url"),
        timeout=_param_int(env, "sos.vision_timeout", DEFAULT_TIMEOUT),
    )
