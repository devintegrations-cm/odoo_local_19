#!/usr/bin/env python3
"""
Emulador de webhook de orden Shopify.

Lee el payload desde test_shopify_data.json (mismo directorio) y lo
envía al endpoint /shopify/order/<company_id> del controller
ShopifyOrderController.

Por defecto emula la entrega DUPLICADA observada en producción: lanza
dos POST concurrentes (mismo payload, misma firma HMAC) en hilos
separados para reproducir la condición de carrera que genera órdenes
duplicadas. Esperado tras aplicar la idempotencia por
``shopify_order_id``:

    1 respuesta  → 200 {"status": "success", "order_id": <id>}
    1 respuesta  → 200 {"status": "skipped", "reason": "already_processed"}

Configuración (variables de entorno; el secreto nunca se versiona):
    SHOPIFY_TEST_ODOO_URL        URL de la instancia de pruebas
    SHOPIFY_TEST_COMPANY_ID      id de la compañía (por defecto 1)
    SHOPIFY_TEST_WEBHOOK_SECRET  secreto de firma de la compañía de pruebas

Uso:
    python3 test/send_test_order.py            # envío doble concurrente
    python3 test/send_test_order.py --single   # un solo envío
    python3 test/send_test_order.py --count 5  # N envíos concurrentes
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ------------------------------------------------------------------ #
#  Configuración                                                       #
# ------------------------------------------------------------------ #

# URL de la instancia de PRUEBAS (nunca producción). Se toma del entorno.
ODOO_URL = os.environ.get("SHOPIFY_TEST_ODOO_URL", "http://localhost:8069")

# ID de la compañía Odoo que recibirá el webhook. Cada compañía con el
# módulo habilitado tiene su propia URL: /shopify/order/<COMPANY_ID>.
COMPANY_ID = int(os.environ.get("SHOPIFY_TEST_COMPANY_ID", "1"))

# El secreto de firma NUNCA se versiona: se lee de la variable de entorno
# SHOPIFY_TEST_WEBHOOK_SECRET (el mismo valor configurado en la compañía de
# pruebas). Sin ella se omite la cabecera HMAC; desde 19.0.1.9.3 el webhook
# rechaza (401) toda solicitud sin firma válida, también si la compañía no
# tiene secreto configurado.
WEBHOOK_SECRET = os.environ.get("SHOPIFY_TEST_WEBHOOK_SECRET") or None

PAYLOAD_FILE = "test_shopify_data.json"


# ------------------------------------------------------------------ #
#  HMAC-SHA256 (igual que Shopify)                                     #
# ------------------------------------------------------------------ #

def compute_hmac(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


# ------------------------------------------------------------------ #
#  Envío                                                              #
# ------------------------------------------------------------------ #

def _build_request():
    """Read payload + build (endpoint, body, headers) once.

    The body + HMAC are computed a single time so every concurrent
    request carries an *identical* signature, exactly matching what a
    duplicate Shopify subscription would deliver.
    """
    data_file = Path(__file__).parent / PAYLOAD_FILE
    payload = json.loads(data_file.read_text(encoding="utf-8"))

    endpoint = f"{ODOO_URL.rstrip('/')}/shopify/order/{COMPANY_ID}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": "orders/create",
        "X-Shopify-Shop-Domain": "mi-tienda.myshopify.com",
    }
    if WEBHOOK_SECRET:
        headers["X-Shopify-Hmac-SHA256"] = compute_hmac(WEBHOOK_SECRET, body)

    return endpoint, body, headers, payload


def _post_once(tag: str, endpoint: str, body: bytes, headers: dict) -> dict:
    """Single POST. Returns a small dict for the summary table."""
    try:
        response = requests.post(endpoint, data=body, headers=headers, timeout=30)
    except requests.exceptions.ConnectionError as exc:
        return {"tag": tag, "status": None, "reason": "ConnectionError", "body": str(exc)}

    try:
        parsed = response.json()
    except ValueError:
        parsed = {"raw": response.text}

    return {
        "tag":    tag,
        "status": response.status_code,
        "reason": response.reason,
        "body":   parsed,
    }


def send_orders(count: int) -> None:
    endpoint, body, headers, payload = _build_request()

    print(f"[HMAC]  {'firma calculada' if WEBHOOK_SECRET else 'sin secret — header omitido'}")
    print(f"[COMP]  company_id={COMPANY_ID}")
    print(f"[POST]  {endpoint}")
    print(f"[ORDEN] {payload.get('name')}  id={payload.get('id')}  "
          f"total: {payload.get('total_price')} {payload.get('currency')}")
    print(f"[MODO]  {count} request(s) concurrente(s)\n")

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = {
            pool.submit(_post_once, f"req-{i+1}", endpoint, body, headers): i
            for i in range(count)
        }
        results = [f.result() for f in as_completed(futures)]

    results.sort(key=lambda r: r["tag"])

    success_ids = set()
    skipped = 0
    for r in results:
        status_label = f"{r['status']} {r['reason']}" if r["status"] else r["reason"]
        body_repr = (json.dumps(r["body"], ensure_ascii=False)
                     if isinstance(r["body"], dict) else r["body"])
        print(f"[{r['tag']}] HTTP {status_label}  →  {body_repr}")

        if isinstance(r["body"], dict):
            if r["body"].get("status") == "success":
                success_ids.add(r["body"].get("order_id"))
            elif r["body"].get("status") == "skipped":
                skipped += 1

    print("\n[RESUMEN]")
    print(f"  órdenes creadas únicas: {len(success_ids)}  (ids: {sorted(success_ids)})")
    print(f"  respuestas 'skipped'  : {skipped}")
    if count > 1:
        if len(success_ids) == 1 and skipped == count - 1:
            print("  ✓ idempotencia OK — solo se creó una sale.order")
        else:
            print("  ✗ idempotencia FALLA — revisar shopify_order_id / advisory lock")


# ------------------------------------------------------------------ #
#  CLI                                                                #
# ------------------------------------------------------------------ #

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulador de webhook Shopify (con soporte de envío duplicado).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--single", action="store_true",
                       help="Enviar una sola vez (no emula duplicación).")
    group.add_argument("--count", type=int, default=2,
                       help="Cantidad de POSTs concurrentes (default: 2).")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    send_orders(count=1 if args.single else args.count)
