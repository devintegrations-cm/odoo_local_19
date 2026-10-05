# -*- coding: utf-8 -*-
"""Adaptador de IA para emparejar lineas de factura con lineas de orden de compra.

La IA NUNCA crea ni modifica registros: devuelve sugerencias que despues pasan
por las reglas duras y por el criterio del validador. Solo viajan
descripciones, codigos, cantidades y precios; nunca NITs ni datos personales.

Dos proveedores:

- ``anthropic``: llama la Messages API directamente con ``requests`` y salida
  estructurada (``output_config.format``), asi la respuesta es JSON valido
  contra el esquema sin tener que limpiar texto. Se usa HTTP crudo y no el SDK
  ``anthropic`` porque la imagen ``odoo:19.0`` no lo trae y el modulo no
  agrega dependencias Python (DECISIONS.md #1 y #25).
- ``http``: un servicio propio (n8n, FastAPI) que implementa el contrato del
  README y puede usar el modelo que quiera.
- ``cli`` (conexion de prueba): la misma Messages API, pero apuntando al
  puente local ``anthropic_cli_bridge`` que corre en el equipo del
  administrador y ejecuta una CLI con sesion iniciada (``claude`` con un
  perfil, ``agy`` o ``codex``). El campo ``model`` elige la herramienta. Odoo
  no ejecuta nada: solo HTTP. Para desarrollo, no para produccion.

Cualquier fallo devuelve una respuesta vacia con ``summary_es`` explicando el
motivo. La validacion sigue: las lineas quedan para emparejar a mano.
"""

import json
import logging

import requests

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45
# Tiempo maximo para abrir la conexion. El timeout configurado aplica a la
# respuesta; sin este limite, una URL inalcanzable cuelga todo el timeout.
CONNECT_TIMEOUT = 10
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
MAX_TOKENS = 4096
DEFAULT_CLI_TIMEOUT = 180
DEFAULT_CLI_URL = "http://host.docker.internal:8787/v1/messages"
CLI_TOOLS = ("claude-empresa", "claude-team", "claude-personal", "agy", "codex")

SYSTEM_PROMPT = """Eres un asistente de contabilidad de compras en Colombia.
Recibes las lineas de una factura de proveedor y las lineas de la orden de compra
a la que el proveedor dice que corresponde. Tu unica tarea es decir que linea de
la factura corresponde a que linea de la orden.

Criterios, en orden: mismo codigo o codigo equivalente; misma descripcion o
descripcion equivalente aunque cambie el orden de las palabras, abreviaturas,
tildes o unidades; precio unitario igual o muy cercano; cantidad igual o cercana.
Una linea de la orden puede recibir varias lineas de la factura si es evidente
(por ejemplo, entregas parciales del mismo producto).

Da una confianza entre 0 y 1: 0.95 o mas solo si codigo o descripcion y precio
coinciden; entre 0.7 y 0.95 si la descripcion es equivalente pero cambia algo
menor; por debajo de 0.7 si es una suposicion. No inventes emparejamientos: si
una linea no corresponde a nada, dejala en unmatched_invoice. Las notas y el
resumen van en espanol, breves y sin datos que no esten en la entrada."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "invoice_idx": {"type": "integer"},
                    "po_line_id": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "note": {"type": "string"},
                },
                "required": ["invoice_idx", "po_line_id", "confidence", "note"],
                "additionalProperties": False,
            },
        },
        "unmatched_invoice": {"type": "array", "items": {"type": "integer"}},
        "unmatched_po": {"type": "array", "items": {"type": "integer"}},
        "summary_es": {"type": "string"},
    },
    "required": ["matches", "unmatched_invoice", "unmatched_po", "summary_es"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Respuesta normalizada
# ---------------------------------------------------------------------------

def empty_response(invoice_lines, po_lines, summary):
    return {
        "matches": [],
        "unmatched_invoice": list(range(len(invoice_lines))),
        "unmatched_po": [line.get("id") for line in po_lines],
        "summary_es": summary,
    }


def sanitize_response(payload, invoice_lines, po_lines, provider):
    """Deja la respuesta con la forma exacta del contrato, sin confiar en nada.

    Indices fuera de rango, ids de OC que no venian en la peticion o
    confianzas fuera de 0-1 se descartan o se acotan.
    """
    if not isinstance(payload, dict):
        return empty_response(invoice_lines, po_lines, "Respuesta de IA no reconocida.")
    valid_po_ids = {line.get("id") for line in po_lines}
    matches = []
    matched_idx = set()
    for match in payload.get("matches") or []:
        if not isinstance(match, dict):
            continue
        try:
            idx = int(match.get("invoice_idx"))
            po_line_id = int(match.get("po_line_id"))
            confidence = float(match.get("confidence") or 0.0)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(invoice_lines) or po_line_id not in valid_po_ids:
            continue
        if idx in matched_idx:
            continue
        matched_idx.add(idx)
        matches.append({
            "invoice_idx": idx,
            "po_line_id": po_line_id,
            "confidence": max(0.0, min(1.0, confidence)),
            "note": str(match.get("note") or "")[:500],
        })
    matched_po = {m["po_line_id"] for m in matches}
    return {
        "matches": matches,
        "unmatched_invoice": [i for i in range(len(invoice_lines)) if i not in matched_idx],
        "unmatched_po": [pid for pid in valid_po_ids if pid not in matched_po],
        "summary_es": str(payload.get("summary_es") or "Emparejamiento sugerido por %s." % provider)[:1000],
    }


def build_request_payload(invoice_lines, po_lines, context):
    """Lo unico que sale hacia la IA. Sin NITs, sin nombres de terceros."""
    return {
        "invoice_lines": [
            {
                "idx": line.get("idx"),
                "description": line.get("description") or "",
                "code": line.get("code") or "",
                "quantity": line.get("quantity"),
                "price_unit": line.get("price_unit"),
            }
            for line in invoice_lines
        ],
        "po_lines": [
            {
                "id": line.get("id"),
                "description": line.get("description") or "",
                "code": line.get("code") or "",
                "quantity": line.get("quantity"),
                "price_unit": line.get("price_unit"),
            }
            for line in po_lines
        ],
        "context": {"currency": (context or {}).get("currency") or "COP"},
    }


# ---------------------------------------------------------------------------
# Adaptadores
# ---------------------------------------------------------------------------

class AiAdapter:
    """Contrato del servicio de IA."""

    name = "base"

    def match_lines(self, invoice_lines, po_lines, context):
        """Devuelve un dict con la forma::

            {
                "matches": [
                    {"invoice_idx": int, "po_line_id": int,
                     "confidence": float, "note": str},
                ],
                "unmatched_invoice": [int],
                "unmatched_po": [int],
                "summary_es": str,
            }
        """
        raise NotImplementedError


class NoopAiAdapter(AiAdapter):
    """IA deshabilitada: el matching queda solo por codigo."""

    name = "noop"

    def match_lines(self, invoice_lines, po_lines, context):
        _logger.info("[SPR] IA deshabilitada, no se sugieren emparejamientos.")
        return empty_response(invoice_lines, po_lines, "Emparejamiento por IA deshabilitado.")


class HttpAiAdapter(AiAdapter):
    """Servicio HTTP propio que implementa el contrato del README."""

    name = "http"

    def __init__(self, url, api_key=None, timeout=DEFAULT_TIMEOUT):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout or DEFAULT_TIMEOUT

    def match_lines(self, invoice_lines, po_lines, context):
        if not self.url:
            return empty_response(invoice_lines, po_lines, "URL del servicio de IA no configurada.")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        body = build_request_payload(invoice_lines, po_lines, context)
        try:
            response = requests.post(self.url, headers=headers, json=body,
                                     timeout=(CONNECT_TIMEOUT, self.timeout))
        except requests.RequestException as error:
            _logger.warning("[SPR] IA (http): error de conexion (%s)", error.__class__.__name__)
            return empty_response(invoice_lines, po_lines,
                                  "IA no disponible (%s)." % error.__class__.__name__)
        if response.status_code != 200:
            _logger.warning("[SPR] IA (http): HTTP %s", response.status_code)
            return empty_response(invoice_lines, po_lines,
                                  "IA no disponible (HTTP %s)." % response.status_code)
        try:
            payload = response.json()
        except ValueError:
            return empty_response(invoice_lines, po_lines, "La respuesta de IA no es JSON.")
        return sanitize_response(payload, invoice_lines, po_lines, self.name)


class AnthropicAiAdapter(AiAdapter):
    """Messages API de Anthropic con salida estructurada."""

    name = "anthropic"

    def __init__(self, api_key, model=DEFAULT_ANTHROPIC_MODEL, url=None, timeout=DEFAULT_TIMEOUT):
        self.api_key = api_key
        self.model = model or DEFAULT_ANTHROPIC_MODEL
        self.url = url or ANTHROPIC_URL
        self.timeout = timeout or DEFAULT_TIMEOUT

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

    def _body(self, invoice_lines, po_lines, context):
        payload = build_request_payload(invoice_lines, po_lines, context)
        user_text = (
            "Empareja estas lineas. Responde solo con el JSON del esquema.\n\n%s"
            % json.dumps(payload, ensure_ascii=False, indent=1)
        )
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_text}],
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

    def match_lines(self, invoice_lines, po_lines, context):
        if not self.api_key:
            return empty_response(invoice_lines, po_lines, "API key de Anthropic no configurada.")
        try:
            response = requests.post(
                self.url, headers=self._headers(),
                json=self._body(invoice_lines, po_lines, context),
                timeout=(CONNECT_TIMEOUT, self.timeout),
            )
        except requests.RequestException as error:
            _logger.warning("[SPR] IA (anthropic): error de conexion (%s)", error.__class__.__name__)
            return empty_response(invoice_lines, po_lines,
                                  "IA no disponible (%s)." % error.__class__.__name__)
        if response.status_code != 200:
            # El cuerpo del error puede traer detalle util, pero nunca la key.
            detail = ""
            try:
                detail = (response.json().get("error") or {}).get("message") or ""
            except ValueError:
                pass
            _logger.warning("[SPR] IA (anthropic): HTTP %s %s", response.status_code, detail[:200])
            return empty_response(invoice_lines, po_lines,
                                  "IA no disponible (HTTP %s)." % response.status_code)
        try:
            message = response.json()
            payload = self._extract_json(message)
        except ValueError as error:
            _logger.warning("[SPR] IA (anthropic): respuesta invalida: %s", error)
            return empty_response(invoice_lines, po_lines, "Respuesta de IA invalida: %s." % error)
        usage = message.get("usage") or {}
        _logger.info(
            "[SPR] IA (anthropic) modelo %s: %s tokens entrada, %s salida, %s sugerencias",
            message.get("model") or self.model, usage.get("input_tokens"),
            usage.get("output_tokens"), len(payload.get("matches") or []),
        )
        return sanitize_response(payload, invoice_lines, po_lines, self.name)


class CliAiAdapter(AnthropicAiAdapter):
    """Conexion de prueba: Messages API contra el puente local de CLI.

    El puente (``claude_projects/anthropic_cli_bridge``) emula
    ``POST /v1/messages`` y ejecuta la CLI que diga ``model``. Todo lo demas
    (cuerpo, esquema, lectura de la respuesta) es identico a Anthropic.
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


def _param_int(env, key, default):
    try:
        return int(_param(env, key, default))
    except (TypeError, ValueError):
        return default


def get_ai_adapter(env):
    """Devuelve la implementacion configurada en Ajustes."""
    if str(_param(env, "spr.ai_enabled", "")).lower() not in ("true", "1"):
        return NoopAiAdapter()
    if str(_param(env, "spr.ai_cli_enabled", "")).lower() in ("true", "1"):
        return CliAiAdapter(
            tool=_param(env, "spr.ai_cli_tool", CLI_TOOLS[0]),
            url=_param(env, "spr.ai_cli_url", DEFAULT_CLI_URL),
            api_key=_param(env, "spr.ai_cli_api_key"),
            timeout=_param_int(env, "spr.ai_cli_timeout", DEFAULT_CLI_TIMEOUT),
        )
    provider = _param(env, "spr.ai_provider", "anthropic")
    api_key = _param(env, "spr.ai_api_key")
    timeout = _param_int(env, "spr.ai_timeout", DEFAULT_TIMEOUT)
    if provider == "http":
        url = _param(env, "spr.ai_url")
        if not url:
            _logger.warning("[SPR] IA habilitada (http) pero sin URL. Usando NoopAiAdapter.")
            return NoopAiAdapter()
        return HttpAiAdapter(url=url, api_key=api_key, timeout=timeout)
    if not api_key:
        _logger.warning("[SPR] IA habilitada (anthropic) pero sin API key. Usando NoopAiAdapter.")
        return NoopAiAdapter()
    return AnthropicAiAdapter(
        api_key=api_key,
        model=_param(env, "spr.ai_model", DEFAULT_ANTHROPIC_MODEL),
        url=_param(env, "spr.ai_url"),
        timeout=timeout,
    )
