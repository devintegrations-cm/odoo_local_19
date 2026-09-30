#!/usr/bin/env python3
"""Prueba de carga de VENTAS del POS con la cola de inventario (pos_inventory_queue).

Qué simula
----------
Varias tiendas vendiendo a la vez, como en la operación real (un proceso por
cajero, cada uno con su conexión, como un cliente del POS):

- Cada sesión POS abierta es una tienda (``--sessions`` o todas las abiertas).
- Cada tienda tiene ``--cashiers`` cajeros (3 por defecto) que envían
  ``--orders`` ventas cada uno, una detrás de otra, como un cajero real.
- Las ventas van facturadas (``--invoice``, por defecto), como en producción:
  con stock "al cierre", solo así Odoo crea el picking en tiempo real.
- Cada venta entra por el MISMO camino que el POS: ``pos.order.sync_from_ui``
  envuelto en ``odoo.service.model.retrying``, el reintento automático que el
  servidor aplica a cada petición (hasta 5 intentos ante choques de base).
- Si una venta falla igual, se reenvía más tarde, como hace el POS con las
  órdenes que no pudo sincronizar.
- La cola la drena el cron REAL del servidor (el que dispara cada venta), no
  la prueba. Se mide cuánto tarda el inventario en ponerse al día.

Cómo leer el resultado
----------------------
- ⛔ ERROR DEL ENTORNO / DEL TEST: faltan sesiones, stock o conexiones, o el
  cron del servidor no está corriendo. No dice nada del módulo.
- ❌ ERROR DEL MÓDULO O DE DATOS: al terminar hay ventas
  duplicadas, pickings sin validar, ítems de cola sin 'done' o sin fechas,
  stock físico descuadrado o locks de stock pegados.
- ⚠️ OPORTUNIDAD DE MEJORA: todo cuadró, pero hubo ventas que necesitaron
  reintento o reenvío (choques de numeración de órdenes del core, cajeros de
  la misma tienda), o el inventario tardó en ponerse al día.
- ✅ OK.

Códigos de salida: 0 = OK o solo mejoras, 1 = error del módulo/datos, 2 = entorno.

Ejemplos
--------
Con los valores por defecto (base local odoo_col_19: todas las sesiones abiertas,
productos E-COM06, E-COM07, E-COM11 y FURN_0001, clientes 6, 437, 438, 532, 537, 539):

    docker compose -f stack.yml exec web python3 \\
        /mnt/extra-addons/custom-addons/pos_inventory_queue/tools/test_pos_sales_concurrency.py

Ritmo real de caja (pausa media de 20 s entre ventas de un cajero):

    ... test_pos_sales_concurrency.py --orders 5 --think 20

"Consumidor final" (todas las tiendas le facturan al mismo cliente):

    ... test_pos_sales_concurrency.py --partner-ids 6

Otra base:

    ... test_pos_sales_concurrency.py --db pruebas --sessions "POS/00148" \\
        --product-ids 70,81,82,83,84 --partner-ids 84,85,86 --cashiers 3
"""

import argparse
import logging
import multiprocessing
import random
import sys
import threading
import time
import uuid as uuidlib

# Valores por defecto de la base local odoo_col_19 (Libertario). En otra base,
# pasá --db, --product-codes/--product-ids y --partner-ids.
DEFAULT_CONFIG = "/etc/odoo/odoo.conf"
DEFAULT_DB = "odoo_col_19"
DEFAULT_PRODUCT_CODES = "E-COM06,E-COM07,E-COM11,FURN_0001"
DEFAULT_PARTNER_IDS = "6,437,438,532,537,539"

CONNECTIONS_MARGIN = 5
# Reenvío de una venta que no se pudo sincronizar. El POS real la guarda en el
# navegador y la sigue reenviando hasta que entra; aquí se reintenta con
# esperas crecientes (2, 4, 8, 15, 15... s: ~1,5 min en total) para que una
# venta que el POS terminaría sincronizando no se cuente como perdida.
RESEND_ATTEMPTS = 8
RESEND_DELAYS = (2, 4, 8, 15)
CRON_STALL_SECONDS = 90    # sin avance de la cola en este tiempo = cron parado


class EnvironmentProblem(Exception):
    """El entorno no permite correr la prueba: no es un error del módulo."""


def _registry(config_path, db_name):
    import odoo.tools.config
    from odoo.modules.registry import Registry

    odoo.tools.config.parse_config(["-c", config_path, "-d", db_name])
    return Registry(db_name)


def _env(cr, uid=None, context=None):
    from odoo import api, SUPERUSER_ID

    return api.Environment(cr, uid or SUPERUSER_ID, context or {})


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


# ---------------------------------------------------------------------------
# PASO 0: ENTORNO Y DATOS DE CADA TIENDA
# ---------------------------------------------------------------------------

def prepare(args):
    registry = _registry(args.config, args.db)
    problems = []
    with registry.cursor() as cr:
        env = _env(cr)
        Session = env["pos.session"]
        if args.sessions:
            sessions = Session.search([("name", "in", args.sessions)])
            missing = set(args.sessions) - set(sessions.mapped("name"))
            if missing:
                problems.append(f"No existen las sesiones {sorted(missing)}")
        else:
            sessions = Session.search([("state", "=", "opened")])
        partners = env["res.partner"].browse(args.partner_ids).exists()
        if len(partners) != len(args.partner_ids):
            problems.append(
                f"No existen los clientes {sorted(set(args.partner_ids) - set(partners.ids))}")
        if args.invoice and not partners:
            problems.append("Las ventas facturadas necesitan un cliente: indicá --partner-ids")
        # Con un solo cliente se usa su posición fiscal; con varios, la del POS.
        partner = partners if len(partners) == 1 else None
        # Con stock "al cierre", Odoo solo crea el picking en tiempo real (y la
        # cola participa) si la venta va facturada y la compañía es anglosajona
        # (pos.order._force_create_picking_real_time). Así opera producción.
        at_closing = sessions.filtered("update_stock_at_closing")
        blind = at_closing.filtered(
            lambda s: not (args.invoice and s.company_id.anglo_saxon_accounting))
        if blind:
            problems.append(
                f"Las sesiones {blind.mapped('name')} actualizan el stock AL CIERRE y estas "
                "ventas no fuerzan el picking en tiempo real (hace falta venta facturada y "
                "contabilidad anglosajona): la cola no participaría. Usá --invoice o una "
                "compañía 'En tiempo real'.")
        elif at_closing:
            print("Stock al cierre, pero ventas facturadas + contabilidad anglosajona: el "
                  "picking se crea en tiempo real y pasa por la cola (como en producción).")
        no_journal = sessions.filtered(lambda s: args.invoice and not s.config_id.invoice_journal_id)
        if no_journal:
            problems.append(f"Sin diario de facturas: {no_journal.mapped('config_id.name')}")
        not_open = sessions.filtered(lambda s: s.state != "opened")
        if not_open:
            problems.append(f"Sesiones no abiertas: {not_open.mapped('name')}")
        sessions -= not_open
        if not sessions:
            problems.append("No hay sesiones POS abiertas para usar como tiendas")

        if args.product_ids:
            products = env["product.product"].browse(args.product_ids).exists()
            if len(products) != len(args.product_ids):
                problems.append(
                    f"No existen los product.product "
                    f"{sorted(set(args.product_ids) - set(products.ids))}")
        else:
            products = env["product.product"].search(
                [("default_code", "in", args.product_codes)])
            found = products.mapped("default_code")
            missing = [c for c in args.product_codes if c not in found]
            if missing:
                problems.append(f"No hay productos activos con código {missing}")
            repeated = sorted({c for c in found if found.count(c) > 1})
            if repeated:
                problems.append(
                    f"Códigos repetidos en varios productos {repeated}: usá --product-ids")
        for product in products:
            if not product.is_storable:
                problems.append(f"{product.display_name} no controla inventario")
            if not product.available_in_pos:
                problems.append(f"{product.display_name} no está disponible en el POS")

        queue_on = env["pos.inventory.queue"]._is_queue_enabled()
        if not queue_on:
            problems.append("La cola de inventario está APAGADA: la prueba no mediría el módulo")

        stores = []
        total_orders = len(sessions) * args.cashiers * args.orders
        orders_per_store = args.cashiers * args.orders
        for session in sessions:
            config = session.config_id
            cash = config.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and not pm.split_transactions)[:1]
            if not cash:
                problems.append(f"{config.name} no tiene medio de pago en efectivo")
                continue
            source = config.picking_type_id.default_location_src_id
            if not source:
                problems.append(f"{config.name}: el tipo de operación no tiene ubicación origen")
                continue
            fiscal = (partner.property_account_position_id if partner else None) \
                or config.default_fiscal_position_id
            lines = []
            for product in products:
                taxes = product.taxes_id.filtered(lambda t: t.company_id == config.company_id)
                taxes = fiscal.map_tax(taxes) if fiscal else taxes
                price = config.pricelist_id._get_product_price(product, args.qty) \
                    if config.pricelist_id else product.lst_price
                values = taxes.compute_all(price, config.currency_id, args.qty) if taxes else {
                    "total_excluded": price * args.qty, "total_included": price * args.qty}
                lines.append({
                    "product_id": product.id, "price_unit": price, "qty": args.qty,
                    "tax_ids": taxes.ids,
                    "price_subtotal": values["total_excluded"],
                    "price_subtotal_incl": values["total_included"],
                })
            stores.append({
                "session_id": session.id, "session": session.name, "config": config.name,
                "config_id": config.id,
                "company_id": config.company_id.id, "user_id": session.user_id.id,
                "pricelist_id": config.pricelist_id.id, "fiscal_position_id": fiscal.id,
                "cash_pm_id": cash.id, "source_id": source.id, "lines": lines,
                "partner_ids": partners.ids,
            })

        sources = {store["source_id"] for store in stores}
        initial_on_hand = {}
        for source_id in sources:
            for product in products:
                ctx = product.with_context(location=source_id)
                initial_on_hand[(source_id, product.id)] = ctx.qty_available
                # Peor caso: el producto sale en TODAS las ventas de las tiendas
                # que descuentan de esta ubicación.
                share = sum(1 for s in stores if s["source_id"] == source_id)
                worst = orders_per_store * share * args.qty
                if ctx.free_qty < worst:
                    problems.append(
                        f"Stock libre insuficiente de {product.display_name} en "
                        f"{env['stock.location'].browse(source_id).display_name}: "
                        f"libre={ctx.free_qty}, peor caso={worst:.0f}")

        stuck = env["pos.inventory.queue"].search_count([("state", "in", ["pending", "processing"])])
        if stuck:
            problems.append(
                f"Hay {stuck} ítem(s) pending/processing en la cola: esperá a que el cron los "
                "procese antes de medir")

        product_names = products.mapped("display_name")

        cr.execute("SHOW max_connections")
        max_connections = int(cr.fetchone()[0])
        cr.execute("SHOW superuser_reserved_connections")
        reserved = int(cr.fetchone()[0])
        cr.execute("SELECT count(*) FROM pg_stat_activity")
        in_use = cr.fetchone()[0]
        available = max_connections - reserved - in_use
        needed = len(stores) * args.cashiers + CONNECTIONS_MARGIN
        print(f"Conexiones PostgreSQL : libres={available}, necesarias={needed} "
              f"({len(stores)} tienda(s) × {args.cashiers} cajero(s))")
        if needed > available:
            problems.append(
                f"Se necesitan ~{needed} conexiones y hay {available} libres: bajá --cashiers "
                "o la cantidad de tiendas, o subí max_connections. En producción los cajeros "
                "no abren conexión propia: comparten los workers de Odoo.")

    if problems:
        raise EnvironmentProblem("\n".join(f"  - {p}" for p in problems))

    for store in stores:
        print(f"Tienda                : {store['config']} · sesión {store['session']}")
    print(f"Productos             : {product_names}")
    print(f"Ventas a enviar       : {total_orders} ({args.lines} línea(s) de {args.qty} c/u)")
    return {"stores": stores, "initial_on_hand": initial_on_hand, "product_ids": products.ids}


# ---------------------------------------------------------------------------
# PASO 1: CAJEROS VENDIENDO (un proceso por tienda, un hilo por cajero)
# ---------------------------------------------------------------------------

class _RetryCounter(logging.Handler):
    """Cuenta los reintentos automáticos del servidor (service.model.retrying)."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.retries = 0

    def emit(self, record):
        # emit ya corre con el lock propio del Handler (self.lock): no tomar
        # otro con ese nombre, o el proceso se bloquea contra sí mismo.
        if "tries left" in record.getMessage():
            self.retries += 1


class _ConflictCounter(logging.Handler):
    """Cuenta los choques de base por recurso (log 'bad query' de odoo.sql_db)."""

    RESOURCES = (
        ("ir_sequence", "numeración de órdenes/líneas"),
        ("stock_quant", "stock (stock_quant)"),
        ("res_partner", "cliente (res_partner)"),
        ("account_move", "factura (account_move)"),
    )

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.by_resource = {}

    def emit(self, record):
        message = record.getMessage()
        if "bad query" not in message:
            return
        label = next((name for key, name in self.RESOURCES if key in message), "otro")
        self.by_resource[label] = self.by_resource.get(label, 0) + 1


def _order_data(store, args, rng, device):
    """Arma la venta como el POS 19 en el navegador.

    pos_reference y tracking_number los genera el navegador con el contador de
    su dispositivo (pos_store.js setNextOrderRefs), así que el servidor NO usa
    la secuencia 'backend' de órdenes. sequence_number va en 0, igual que el
    POS (pos_store.js createNewOrder): el servidor lo numera con la secuencia
    sin huecos del POS (pos.order._update_sequence_number), que es donde
    compiten los cajeros de una misma tienda.
    """
    uid = str(uuidlib.uuid4())
    device["next"] += 1
    number = f"{device['next']:06d}"
    pos_reference = f"{time.strftime('%y')}{device['id']}-{store['config_id']}-{number}"
    tracking_number = f"{device['id']}{int(number) % 1000:03d}"
    chosen = rng.sample(store["lines"], min(args.lines, len(store["lines"])))
    lines = [(0, 0, {
        "id": rng.randint(1, 10**9), "pack_lot_ids": [],
        "product_id": line["product_id"], "qty": line["qty"],
        "price_unit": line["price_unit"], "discount": 0.0,
        "price_subtotal": line["price_subtotal"],
        "price_subtotal_incl": line["price_subtotal_incl"],
        "tax_ids": [(6, 0, line["tax_ids"])],
    }) for line in chosen]
    total = sum(l[2]["price_subtotal_incl"] for l in lines)
    base = sum(l[2]["price_subtotal"] for l in lines)
    from odoo import fields
    return {
        "amount_paid": total, "amount_return": 0, "amount_tax": total - base,
        "amount_total": total,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()),
        "fiscal_position_id": store["fiscal_position_id"] or False,
        "pricelist_id": store["pricelist_id"], "name": f"Order {uid}",
        "last_order_preparation_change": "{}", "lines": lines,
        "partner_id": rng.choice(store["partner_ids"]) if store["partner_ids"] else False,
        "session_id": store["session_id"],
        "payment_ids": [(0, 0, {
            "amount": total, "name": fields.Datetime.now(),
            "payment_method_id": store["cash_pm_id"]})],
        "uuid": uid, "user_id": store["user_id"], "to_invoice": args.invoice,
        "pos_reference": pos_reference, "tracking_number": tracking_number,
        "sequence_number": 0,
    }


def _send(registry, store, data, pdf_after_commit=False):
    """Envía una venta como el POS: sync_from_ui con el reintento del servidor.

    pdf_after_commit (EXPERIMENTO, --pdf-after-commit): simula generar el PDF
    de la factura DESPUÉS de confirmar la venta, en otra transacción, antes de
    "responder" al POS. El tiempo medido incluye el PDF, como lo vería el
    cajero, pero el número de factura se libera al confirmar la venta.
    """
    from odoo.service.model import retrying

    context = {"allowed_company_ids": [store["company_id"]]}
    if pdf_after_commit:
        context["generate_pdf"] = False
    with registry.cursor() as cr:
        env = _env(cr, store["user_id"], context)
        retrying(lambda: env["pos.order"].sync_from_ui([data]), env)
        cr.commit()
    if pdf_after_commit:
        with registry.cursor() as cr:
            env = _env(cr, store["user_id"], {"allowed_company_ids": [store["company_id"]]})
            invoice = env["pos.order"].search([("uuid", "=", data["uuid"])]).account_move
            if invoice:
                retrying(lambda: invoice.with_context(skip_invoice_sync=True)._generate_and_send(), env)
            cr.commit()


def cashier_process(config_path, db_name, store, cashier, args, barrier, results):
    """Un cajero: su propio proceso y su propia conexión, como un cliente del POS."""
    registry = _registry(config_path, db_name)
    counter = _RetryCounter()
    logging.getLogger("odoo.service.model").addHandler(counter)
    logging.getLogger("odoo.service.model").setLevel(logging.INFO)
    conflicts = _ConflictCounter()
    logging.getLogger("odoo.sql_db").addHandler(conflicts)
    sent, failed, latencies = [], [], []
    rng = random.Random(f"{store['session_id']}-{cashier}-{time.time()}")
    # Cada cajero es un dispositivo con su propio identificador y contador.
    device = {"id": f"{cashier + 1}{rng.randint(100, 999)}", "next": 0}

    try:
        barrier.wait()
    except threading.BrokenBarrierError:
        results.put({"store": store["session"], "aborted": True})
        return
    start = time.monotonic()
    for _ in range(args.orders):
        data = _order_data(store, args, rng, device)
        t0 = time.monotonic()
        try:
            _send(registry, store, data, args.pdf_after_commit)
            sent.append(data["uuid"])
            latencies.append(time.monotonic() - t0)
        except Exception as exc:
            failed.append((data, f"{type(exc).__name__}: {str(exc)[:160]}"))
        if args.think:
            time.sleep(rng.uniform(0, 2 * args.think))
    selling = time.monotonic() - start

    # Reenvío de las ventas que fallaron, como hace el POS con las no sincronizadas.
    resent, lost = 0, []
    for data, error in failed:
        for attempt in range(RESEND_ATTEMPTS):
            time.sleep(RESEND_DELAYS[min(attempt, len(RESEND_DELAYS) - 1)])
            try:
                _send(registry, store, data, args.pdf_after_commit)
                sent.append(data["uuid"])
                resent += 1
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:160]}"
        else:
            lost.append((data["uuid"], error))

    results.put({
        "store": store["session"], "aborted": False, "sent": sent,
        "first_try_failures": [e for _, e in failed], "resent": resent, "lost": lost,
        "latencies": latencies, "retries": counter.retries, "selling": selling,
        "conflicts": conflicts.by_resource,
    })


def run_stores(args, state):
    jobs = [(store, c) for store in state["stores"] for c in range(args.cashiers)]
    barrier = multiprocessing.Barrier(len(jobs))
    results = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=cashier_process,
            args=(args.config, args.db, store, cashier, args, barrier, results))
        for store, cashier in jobs
    ]
    for process in processes:
        process.start()
    outcomes = [results.get() for _ in processes]
    for process in processes:
        process.join()
    return outcomes


# ---------------------------------------------------------------------------
# PASO 2: ESPERAR AL CRON DEL SERVIDOR
# ---------------------------------------------------------------------------

def wait_for_queue(args, uuids):
    """Espera a que el cron real deje en 'done' la cola de estas ventas."""
    registry = _registry(args.config, args.db)
    start = time.monotonic()
    last_progress, last_pending = start, None
    while True:
        with registry.cursor() as cr:
            cr.execute("""
                SELECT count(*) FILTER (WHERE q.state <> 'done'), count(q.id)
                  FROM pos_order o
                  JOIN stock_picking p ON p.pos_order_id = o.id
             LEFT JOIN pos_inventory_queue q ON q.picking_id = p.id
                 WHERE o.uuid = ANY(%s)
            """, (list(uuids),))
            pending, total = cr.fetchone()
        now = time.monotonic()
        if pending == 0:
            return now - start, False
        if pending != last_pending:
            last_pending, last_progress = pending, now
        if now - last_progress > CRON_STALL_SECONDS or now - start > args.wait:
            return now - start, True
        time.sleep(1)


# ---------------------------------------------------------------------------
# PASO 3: VALIDACIÓN
# ---------------------------------------------------------------------------

def validate(args, state, outcomes, lag, stalled):
    module_errors, env_errors, improvements = [], [], []
    sent = [u for o in outcomes if not o["aborted"] for u in o["sent"]]
    lost = [l for o in outcomes if not o["aborted"] for l in o["lost"]]
    first_fail = [e for o in outcomes if not o["aborted"] for e in o["first_try_failures"]]
    resent = sum(o["resent"] for o in outcomes if not o["aborted"])
    retries = sum(o["retries"] for o in outcomes if not o["aborted"])
    latencies = [x for o in outcomes if not o["aborted"] for x in o["latencies"]]
    selling = max((o["selling"] for o in outcomes if not o["aborted"]), default=0)
    if any(o["aborted"] for o in outcomes):
        env_errors.append("Alguna tienda no pudo arrancar")

    # Una venta que no sincronizó NO es un error del módulo: nunca llegó a Odoo
    # (no hay orden, picking ni ítem de cola) y el POS real la seguiría
    # reenviando. Se reporta como mejora porque el cajero la vería pendiente.
    unsynced_note = None
    if lost:
        unsynced_note = (
            f"{len(lost)} venta(s) no alcanzaron a sincronizar en ~1,5 min de reenvíos. "
            "No se perdieron datos: nunca llegaron a Odoo (sin orden, picking ni ítem de "
            "cola) y el POS real las seguiría reenviando, pero el cajero las vería "
            "pendientes. Causa: " + "; ".join(sorted({e.split(':')[0] for _, e in lost})))
    if stalled:
        env_errors.append(
            f"La cola no terminó en {lag:.0f}s: el cron del servidor no está drenando "
            "(¿servidor detenido, max_cron_threads=0 o cron inactivo?)")

    registry = _registry(args.config, args.db)
    with registry.cursor() as cr:
        env = _env(cr)
        orders = env["pos.order"].search([("uuid", "in", sent)])
        cr.execute("SELECT uuid, count(*) FROM pos_order WHERE uuid = ANY(%s) "
                   "GROUP BY uuid HAVING count(*) > 1", (sent,))
        duplicated = cr.fetchall()
        if duplicated:
            module_errors.append(f"{len(duplicated)} venta(s) duplicadas (mismo uuid)")
        if len(set(orders.mapped("uuid"))) != len(set(sent)):
            module_errors.append(
                f"Se confirmaron {len(set(sent))} ventas y hay {len(orders)} órdenes en la base")

        if args.invoice:
            no_invoice = orders.filtered(lambda o: not o.account_move)
            if no_invoice:
                module_errors.append(f"{len(no_invoice)} venta(s) facturadas sin factura")
        no_picking = orders.filtered(lambda o: not o.picking_ids)
        if no_picking:
            module_errors.append(
                f"{len(no_picking)} venta(s) sin picking: el inventario no se movió en tiempo real")
        pickings = orders.picking_ids
        not_done = pickings.filtered(lambda p: p.state != "done")
        if not_done and not stalled:
            module_errors.append(f"{len(not_done)} picking(s) sin validar: "
                                 f"{', '.join(not_done[:10].mapped('name'))}")
        items = env["pos.inventory.queue"].search([("picking_id", "in", pickings.ids)])
        if len(items) != len(pickings):
            module_errors.append(
                f"{len(pickings)} pickings y {len(items)} ítems de cola: alguna venta no se encoló")
        bad_items = items.filtered(lambda i: i.state != "done" or not i.start_date or not i.done_date)
        if bad_items and not stalled:
            module_errors.append(f"{len(bad_items)} ítem(s) de cola sin 'done' o sin fechas")
        queue_latency = [(i.done_date - i.create_date).total_seconds()
                         for i in items if i.done_date and i.create_date]

        sold = {}
        for line in orders.lines:
            source_id = line.order_id.config_id.picking_type_id.default_location_src_id.id
            key = (source_id, line.product_id.id)
            sold[key] = sold.get(key, 0) + line.qty
        for (source_id, product_id), initial in state["initial_on_hand"].items():
            product = env["product.product"].browse(product_id)
            final = product.with_context(location=source_id).qty_available
            expected = initial - sold.get((source_id, product_id), 0)
            print(f"Stock a mano {product.display_name}: inicial={initial} final={final} "
                  f"esperado={expected}")
            if abs(final - expected) > 1e-6 and not stalled:
                module_errors.append(
                    f"Stock físico descuadrado en {product.display_name}: final={final}, "
                    f"esperado={expected}")

        cr.execute("""SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid
                       WHERE l.locktype = 'advisory' AND a.datname = current_database()""")
        leaked = cr.fetchone()[0]
        if leaked:
            module_errors.append(f"{leaked} lock(s) advisory siguen tomados")

    total = len(sent) + len(lost)
    print()
    print("=" * 70)
    print(" MÉTRICAS")
    print("=" * 70)
    print(f"Tiendas × cajeros     : {len(state['stores'])} × {args.cashiers}")
    print(f"Ventas                : {len(set(sent))}/{total} confirmadas, "
          f"{len(lost)} sin sincronizar al terminar la prueba")
    if selling:
        print(f"Ritmo de venta        : {total / selling:.1f} ventas/s durante {selling:.1f}s")
    print(f"Duración de la venta  : p50={_percentile(latencies, .5):.2f}s "
          f"p95={_percentile(latencies, .95):.2f}s max={max(latencies or [0]):.2f}s")
    print(f"Reintentos servidor   : {retries} (choques resueltos dentro de la misma venta)")
    conflicts = {}
    for outcome in outcomes:
        for key, value in outcome.get("conflicts", {}).items():
            conflicts[key] = conflicts.get(key, 0) + value
    print(f"Choques por recurso   : {conflicts or 'ninguno'}")
    print(f"Fallos al 1er envío   : {len(first_fail)}, reenviadas con éxito: {resent}")
    print(f"Inventario al día en  : {lag:.1f}s después de terminar de vender")
    print(f"Espera en cola/ítem   : p50={_percentile(queue_latency, .5):.1f}s "
          f"p95={_percentile(queue_latency, .95):.1f}s max={max(queue_latency or [0]):.1f}s")
    if first_fail:
        causes = {}
        for error in first_fail:
            key = error.split(":")[0] + (" (numeración de órdenes)" if "ir_sequence" in error else "")
            causes[key] = causes.get(key, 0) + 1
        print(f"Causas de fallo       : {causes}")

    if unsynced_note:
        improvements.append(unsynced_note)
    if retries or first_fail:
        improvements.append(
            f"{retries} reintento(s) del servidor y {len(first_fail)} venta(s) que fallaron al "
            "primer envío (el POS las reenvía). Si la causa es 'ir_sequence', es la numeración "
            "de órdenes del core (secuencia sin huecos por POS): compiten los cajeros de la "
            "misma tienda, no la cola.")
    if queue_latency and _percentile(queue_latency, .95) > 60:
        improvements.append(
            "El 5 % más lento de las ventas esperó más de 1 minuto en la cola: el drenaje no "
            "alcanza el ritmo de venta de esta prueba.")
    return module_errors, env_errors, improvements


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--sessions", default="",
                        help="CSV de sesiones (tiendas). Por defecto, todas las abiertas")
    parser.add_argument("--product-codes", default=DEFAULT_PRODUCT_CODES,
                        help=f"CSV de códigos internos (por defecto {DEFAULT_PRODUCT_CODES})")
    parser.add_argument("--product-ids", default="",
                        help="CSV de product.product; si se indica, reemplaza a --product-codes")
    parser.add_argument("--cashiers", type=int, default=3, help="Cajeros por tienda (3)")
    parser.add_argument("--orders", type=int, default=10, help="Ventas por cajero (10)")
    parser.add_argument("--lines", type=int, default=2, help="Líneas por venta (2)")
    parser.add_argument("--qty", type=float, default=1.0, help="Cantidad por línea (1)")
    parser.add_argument("--invoice", action=argparse.BooleanOptionalAction, default=True,
                        help="Ventas facturadas, como en producción (por defecto sí)")
    parser.add_argument("--partner-ids", "--partner-id", default=DEFAULT_PARTNER_IDS,
                        help="CSV de clientes; cada venta toma uno al azar. Un solo cliente "
                             "simula 'Consumidor final' (todas las tiendas le facturan a él)")
    parser.add_argument("--think", type=float, default=0.0,
                        help="Pausa media entre ventas de un cajero, en segundos (0 = estrés)")
    parser.add_argument("--pdf-after-commit", action="store_true",
                        help="EXPERIMENTO: generar el PDF de la factura después de confirmar "
                             "la venta, en otra transacción (etapa 5 variante B)")
    parser.add_argument("--wait", type=int, default=600,
                        help="Máximo de segundos esperando a que el cron vacíe la cola")
    args = parser.parse_args()
    try:
        args.product_ids = [int(x) for x in args.product_ids.split(",") if x.strip()]
    except ValueError:
        parser.error("--product-ids debe ser una lista de enteros separada por comas")
    args.product_codes = [c.strip() for c in args.product_codes.split(",") if c.strip()]
    args.sessions = [s.strip() for s in args.sessions.split(",") if s.strip()]
    try:
        args.partner_ids = [int(x) for x in args.partner_ids.split(",") if x.strip()]
    except ValueError:
        parser.error("--partner-ids debe ser una lista de enteros separada por comas")
    if min(args.cashiers, args.orders, args.lines) < 1 or args.qty <= 0:
        parser.error("--cashiers, --orders, --lines y --qty deben ser positivos")

    multiprocessing.set_start_method("spawn", force=True)
    print("=" * 70)
    print(" POS — PRUEBA DE CARGA DE VENTAS CON COLA DE INVENTARIO")
    print("=" * 70)
    try:
        state = prepare(args)
    except EnvironmentProblem as exc:
        print()
        print("⛔ ERROR DEL ENTORNO / DEL TEST — la prueba no se ejecutó:")
        print(exc)
        print()
        print(" RESULTADO FINAL: ENTORNO (no dice nada del módulo)")
        sys.exit(2)

    print()
    print("Vendiendo...")
    outcomes = run_stores(args, state)
    uuids = [u for o in outcomes if not o.get("aborted") for u in o["sent"]]
    print("Esperando a que el cron del servidor procese la cola...")
    lag, stalled = wait_for_queue(args, uuids) if uuids else (0.0, False)
    module_errors, env_errors, improvements = validate(args, state, outcomes, lag, stalled)

    print()
    print("=" * 70)
    for title, lines in (("⛔ ERRORES DEL ENTORNO:", env_errors),
                         ("❌ ERRORES DEL MÓDULO O DE DATOS:", module_errors),
                         ("⚠️  OPORTUNIDADES DE MEJORA:", improvements)):
        if lines:
            print()
            print(title)
            for line in lines:
                print(f"  - {line}")
    if not (env_errors or module_errors or improvements):
        print()
        print("✅ Todas las ventas entraron una sola vez, sus pickings quedaron validados, el "
              "stock físico cuadra y no quedaron locks pegados.")
    print()
    if module_errors:
        verdict, code = "FAIL — error del módulo o de datos", 1
    elif env_errors:
        verdict, code = "ENTORNO", 2
    elif improvements:
        verdict, code = "PASS con oportunidades de mejora", 0
    else:
        verdict, code = "PASS", 0
    print(f" RESULTADO FINAL: {verdict}")
    print("=" * 70)
    sys.exit(code)


if __name__ == "__main__":
    main()
