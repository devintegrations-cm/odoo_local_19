#!/usr/bin/env python3
"""Prueba de carga de la cola de inventario del POS (pos_inventory_queue).

Qué simula
----------
N ventas ya registradas (``--pickings``) cuyos pickings esperan en la cola, y
D drenadores (``--drainers``) procesándola a la vez con el método real
``pos.inventory.queue._process_queue()``.

- ``--drainers 1`` es la operación normal: Odoo nunca corre el mismo cron dos
  veces en paralelo, así que en producción hay UN drenador (el cron).
- ``--drainers > 1`` simula la hora de cierre: el cron más los cierres de caja
  de varias tiendas, que también drenan la cola.

Ventas y drenadores son números independientes: 300 cajeros vendiendo no son
300 drenadores. Para probar muchas ventas concurrentes (el request del POS)
usar ``test_pos_invoice_concurrency.py``.

Cómo leer el resultado
----------------------
- ⛔ ERROR DEL ENTORNO / DEL TEST: el entorno no permite la prueba (faltan
  conexiones, sesión cerrada, poco stock, cola sucia). No dice nada del módulo.
- ❌ ERROR DEL MÓDULO: al terminar, algún picking no quedó validado, el stock
  físico no cuadra, falta una fecha o quedó un lock de stock pegado.
- ⚠️ OPORTUNIDAD DE MEJORA: todo terminó bien, pero hubo choques que el módulo
  resolvió reintentando, o hizo falta una pasada extra del cron.
- ✅ OK.

Códigos de salida: 0 = OK o solo mejoras, 1 = error del módulo, 2 = entorno.

Ejemplo
-------
docker compose -f stack.yml exec -T web python3 \\
    /mnt/extra-addons/custom-addons/pos_inventory_queue/tools/test_pos_inventory_concurrency.py \\
    --config /etc/odoo/odoo.conf --db odoo_col_19 --session "LIbertario/00042" \\
    --template-ids 403 --pickings 100 --drainers 20
"""

import argparse
import logging
import multiprocessing
import os
import sys
import threading
import time
import traceback

# Conexiones por drenador: la del drenador (cursor del cron) y la del cursor
# aislado donde se valida cada picking.
CONNECTIONS_PER_DRAINER = 2
# Proceso principal + margen para el servidor web y el cron del servidor.
CONNECTIONS_MARGIN = 5
# Pasadas extra de drenaje (como haría el cron) para los ítems que un
# drenador devolvió a 'pending' por contención.
CONVERGENCE_PASSES = 3

QUEUE_LOGGER = 'odoo.addons.pos_inventory_queue.models.inventory_queue'


class EnvironmentProblem(Exception):
    """El entorno no permite correr la prueba: no es un error del módulo."""


def _registry(config_path, db_name):
    import odoo.tools.config
    from odoo.modules.registry import Registry

    odoo.tools.config.parse_config(["-c", config_path, "-d", db_name])
    return Registry(db_name)


def _env(cr):
    from odoo import api, SUPERUSER_ID

    return api.Environment(cr, SUPERUSER_ID, {})


def _is_environment_error(exc):
    """'too many clients' o pool de Odoo agotado: límite del entorno."""
    from psycopg2.pool import PoolError

    text = str(exc)
    return isinstance(exc, PoolError) or (
        'too many clients' in text
        or 'too many connections' in text
        or 'remaining connection slots' in text
    )


# ---------------------------------------------------------------------------
# PASO 0: VERIFICACIÓN DEL ENTORNO
# ---------------------------------------------------------------------------

def check_environment(env, args, products, source_location):
    problems = []

    session = env["pos.session"].search([("name", "=", args.session)], limit=1)
    if not session:
        problems.append(f"No existe la sesión {args.session}")
    elif session.state != "opened":
        problems.append(
            f"La sesión {args.session} no está abierta (estado: {session.state})")

    stuck = env["pos.inventory.queue"].search_count(
        [("state", "in", ["pending", "processing"])])
    if stuck:
        problems.append(
            f"Hay {stuck} ítem(s) pending/processing en la cola de pruebas o "
            "ventas anteriores. Esperá a que el cron los procese (los "
            "'processing' se reclaman a los 5 min) o revisalos antes de medir.")

    per_product = _split_pickings(args.pickings, products)
    for product, count in per_product.items():
        free = product.with_context(location=source_location.id).free_qty
        if free < count:
            problems.append(
                f"Stock libre insuficiente de {product.display_name}: "
                f"libre={free}, necesario={count}")

    env.cr.execute("SHOW max_connections")
    max_connections = int(env.cr.fetchone()[0])
    env.cr.execute("SHOW superuser_reserved_connections")
    reserved = int(env.cr.fetchone()[0])
    env.cr.execute("SELECT count(*) FROM pg_stat_activity")
    in_use = env.cr.fetchone()[0]
    available = max_connections - reserved - in_use
    needed = args.drainers * CONNECTIONS_PER_DRAINER + CONNECTIONS_MARGIN
    print(f"Conexiones PostgreSQL : max={max_connections}, reservadas={reserved}, "
          f"en uso={in_use}, libres={available}, necesarias={needed}")
    if needed > available:
        max_drainers = max(0, (available - CONNECTIONS_MARGIN) // CONNECTIONS_PER_DRAINER)
        problems.append(
            f"{args.drainers} drenadores necesitan ~{needed} conexiones y hay "
            f"{available} libres. Bajá a --drainers {max_drainers} o subí "
            "max_connections de PostgreSQL. (En producción los drenadores son "
            "el cron + los cierres de caja simultáneos, no uno por cajero.)")

    if problems:
        raise EnvironmentProblem("\n".join(f"  - {p}" for p in problems))
    return session


def _split_pickings(total, products):
    """Reparte las ventas entre los productos, en ronda."""
    counts = {product: 0 for product in products}
    for index in range(total):
        counts[products[index % len(products)]] += 1
    return counts


# ---------------------------------------------------------------------------
# PASO 1: CREAR LAS VENTAS (PICKINGS EN COLA, SIN VALIDAR)
# ---------------------------------------------------------------------------

def prepare(args):
    registry = _registry(args.config, args.db)
    with registry.cursor() as cr:
        env = _env(cr)
        templates = env["product.template"].browse(args.template_ids).exists()
        missing = set(args.template_ids) - set(templates.ids)
        if missing:
            raise EnvironmentProblem(f"  - No existen los product.template {sorted(missing)}")
        products = [t.product_variant_id for t in templates]
        not_storable = [p.display_name for p in products if not p.is_storable]
        if not_storable:
            raise EnvironmentProblem(
                f"  - Productos sin control de inventario: {not_storable}")

        session = env["pos.session"].search([("name", "=", args.session)], limit=1)
        picking_type = session.config_id.picking_type_id if session else None
        if not picking_type or not picking_type.default_location_src_id:
            raise EnvironmentProblem(
                "  - La sesión no existe o su tipo de operación no tiene ubicación origen")
        source = picking_type.default_location_src_id
        destination = picking_type.default_location_dest_id
        if not destination:
            raise EnvironmentProblem("  - El tipo de operación no tiene ubicación destino")

        check_environment(env, args, products, source)

        # Stock FÍSICO (a mano) y no disponible: un picking reservado baja el
        # disponible sin mover inventario y escondería pickings sin validar.
        initial_on_hand = {
            p.id: p.with_context(location=source.id).qty_available for p in products}

        picking_ids = []
        for index in range(args.pickings):
            product = products[index % len(products)]
            picking = env["stock.picking"].create({
                "partner_id": session.config_id.company_id.partner_id.id,
                "picking_type_id": picking_type.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "origin": f"QUEUE-LOAD-{session.name}-{index + 1}",
                "pos_session_id": session.id,
            })
            env["stock.move"].create({
                "product_id": product.id,
                "product_uom_qty": 1.0,
                "product_uom": product.uom_id.id,
                "picking_id": picking.id,
                "picking_type_id": picking_type.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "company_id": session.config_id.company_id.id,
            })
            picking.action_confirm()
            picking.move_ids.picked = True  # el POS entrega los moves 'picked'
            env["pos.inventory.queue"].create({"picking_id": picking.id})
            picking_ids.append(picking.id)
        cr.commit()

        print(f"Sesión                : {session.name} (ID {session.id})")
        print(f"Ubicación origen      : {source.display_name}")
        for product in products:
            print(f"Producto              : {product.display_name} (ID {product.id}) "
                  f"stock a mano={initial_on_hand[product.id]}")
        print(f"Ventas en cola        : {len(picking_ids)} pickings sin validar")
        return {
            "picking_ids": picking_ids,
            "product_ids": [p.id for p in products],
            "source_id": source.id,
            "initial_on_hand": initial_on_hand,
        }


# ---------------------------------------------------------------------------
# PASO 2: DRENADORES CONCURRENTES
# ---------------------------------------------------------------------------

class _CountingHandler(logging.Handler):
    """Cuenta los choques que el módulo resolvió reintentando."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.transient = 0
        self.yielded = 0

    def emit(self, record):
        message = record.getMessage()
        if 'contention transient conflict' in message:
            self.transient += 1
        elif 'cede a pending' in message or 'revertido a pending' in message:
            self.yielded += 1


def drainer(config_path, db_name, drainer_id, barrier, results):
    outcome = {"id": drainer_id, "status": "ok", "error": None,
               "statuses": {}, "transient": 0, "yielded": 0, "elapsed": 0.0}
    try:
        registry = _registry(config_path, db_name)
        handler = _CountingHandler()
        logging.getLogger(QUEUE_LOGGER).addHandler(handler)

        with registry.cursor() as cr:
            Queue = _env(cr)["pos.inventory.queue"]
            # Contar el resultado de cada ítem que procesa este drenador.
            QueueClass = type(Queue)
            original = QueueClass._process_item_in_new_cursor

            def counted(self, item_id):
                status = original(self, item_id)
                outcome["statuses"][status] = outcome["statuses"].get(status, 0) + 1
                return status

            QueueClass._process_item_in_new_cursor = counted

            barrier.wait()
            start = time.monotonic()
            Queue._process_queue(time_budget=0)
            cr.commit()
            outcome["elapsed"] = time.monotonic() - start

        outcome["transient"] = handler.transient
        outcome["yielded"] = handler.yielded
    except threading.BrokenBarrierError:
        outcome["status"] = "entorno"
        outcome["error"] = "abortado: otro drenador no pudo arrancar"
    except Exception as exc:
        outcome["status"] = "entorno" if _is_environment_error(exc) else "modulo"
        outcome["error"] = f"{type(exc).__name__}: {exc}"
        outcome["traceback"] = traceback.format_exc()
        try:
            barrier.abort()  # que el resto no espere para siempre
        except Exception:
            pass
    results.put(outcome)


def run_drainers(args):
    barrier = multiprocessing.Barrier(args.drainers)
    results = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=drainer, args=(args.config, args.db, i, barrier, results))
        for i in range(1, args.drainers + 1)
    ]
    start = time.monotonic()
    for process in processes:
        process.start()
    outcomes = [results.get() for _ in processes]
    for process in processes:
        process.join()
    return outcomes, time.monotonic() - start


def converge(args):
    """Pasadas extra de drenaje, como haría el cron, para los ítems que un
    drenador devolvió a 'pending' por contención o falta de conexión."""
    registry = _registry(args.config, args.db)
    passes = 0
    with registry.cursor() as cr:
        env = _env(cr)
        Queue = env["pos.inventory.queue"]
        for _ in range(CONVERGENCE_PASSES):
            pending = Queue.search_count([
                ("picking_id", "in", args.state["picking_ids"]),
                ("state", "=", "pending"),
            ])
            if not pending:
                break
            passes += 1
            Queue._process_queue(time_budget=0)
            cr.commit()
            env.invalidate_all()
    return passes


# ---------------------------------------------------------------------------
# PASO 3: VALIDACIÓN
# ---------------------------------------------------------------------------

def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def validate(args, outcomes, drain_seconds, extra_passes):
    state = args.state
    module_errors, env_errors, improvements = [], [], []

    for outcome in outcomes:
        if outcome["status"] == "entorno":
            env_errors.append(f"Drenador {outcome['id']}: {outcome['error']}")
        elif outcome["status"] == "modulo":
            module_errors.append(f"Drenador {outcome['id']} terminó con excepción: "
                                 f"{outcome['error']}")

    registry = _registry(args.config, args.db)
    with registry.cursor() as cr:
        env = _env(cr)
        items = env["pos.inventory.queue"].search(
            [("picking_id", "in", state["picking_ids"])], order="id")
        pickings = env["stock.picking"].browse(state["picking_ids"])

        if len(items) != len(state["picking_ids"]):
            module_errors.append(
                f"Se esperaban {len(state['picking_ids'])} ítems de cola y hay {len(items)}")

        not_done_pickings = pickings.filtered(lambda p: p.state != "done")
        if not_done_pickings:
            module_errors.append(
                f"{len(not_done_pickings)} picking(s) sin validar: "
                f"{', '.join(not_done_pickings[:10].mapped('name'))}")

        by_state = {}
        for item in items:
            by_state[item.state] = by_state.get(item.state, 0) + 1
            if item.state != "done":
                continue
            if not item.start_date or not item.done_date:
                module_errors.append(f"{item.name}: Done sin start_date/done_date")
        not_done = {k: v for k, v in by_state.items() if k != "done"}
        if not_done:
            module_errors.append(f"Ítems de cola sin 'done': {not_done}")

        source = env["stock.location"].browse(state["source_id"])
        per_product = {}
        for picking in pickings:
            for move in picking.move_ids:
                per_product[move.product_id.id] = per_product.get(move.product_id.id, 0) + 1
        for product in env["product.product"].browse(state["product_ids"]):
            on_hand = product.with_context(location=source.id).qty_available
            expected = state["initial_on_hand"][product.id] - per_product.get(product.id, 0)
            print(f"Stock a mano {product.display_name}: inicial="
                  f"{state['initial_on_hand'][product.id]} final={on_hand} esperado={expected}")
            if abs(on_hand - expected) > 1e-6:
                module_errors.append(
                    f"Stock físico descuadrado en {product.display_name}: "
                    f"final={on_hand}, esperado={expected}")

        # Locks de stock de SESIÓN pegados en alguna conexión (fuga).
        cr.execute("""
            SELECT count(*) FROM pg_locks l
              JOIN pg_stat_activity a ON a.pid = l.pid
             WHERE l.locktype = 'advisory' AND a.datname = current_database()
        """)
        leaked = cr.fetchone()[0]
        if leaked:
            module_errors.append(f"{leaked} lock(s) advisory siguen tomados tras el drenaje")

        latencies = [
            (i.done_date - i.start_date).total_seconds()
            for i in items if i.start_date and i.done_date
        ]

    transient = sum(o["transient"] for o in outcomes)
    yielded = sum(o["yielded"] for o in outcomes)
    statuses = {}
    for outcome in outcomes:
        for key, value in outcome["statuses"].items():
            statuses[key] = statuses.get(key, 0) + value

    print()
    print("=" * 70)
    print(" MÉTRICAS")
    print("=" * 70)
    print(f"Drenadores            : {args.drainers}")
    print(f"Ventas (pickings)     : {len(state['picking_ids'])}")
    print(f"Tiempo de drenaje     : {drain_seconds:.2f}s "
          f"({len(state['picking_ids']) / drain_seconds:.1f} pickings/s, incluye arranque "
          "de procesos)" if drain_seconds else "")
    print(f"Resultados por ítem   : {statuses}")
    print(f"Choques resueltos     : {transient} reintento(s) dentro del ítem, "
          f"{yielded} ítem(s) devueltos a pending")
    print(f"Pasadas extra (cron)  : {extra_passes}")
    print(f"Duración por ítem     : p50={_percentile(latencies, .5):.2f}s "
          f"p95={_percentile(latencies, .95):.2f}s max={max(latencies or [0]):.2f}s")
    print("(Nota: el cron del servidor también drena si coincide con la prueba.)")

    if transient or yielded:
        improvements.append(
            f"Hubo {transient} choque(s) resueltos con reintento y {yielded} ítem(s) "
            "devueltos a pending: con más drenadores sobre los mismos productos el "
            "módulo espera turnos; terminó bien, pero es tiempo perdido.")
    if extra_passes:
        improvements.append(
            f"Hicieron falta {extra_passes} pasada(s) extra para terminar: en producción "
            "eso es esperar al siguiente ciclo del cron (hasta 1 minuto).")

    return module_errors, env_errors, improvements


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def _print_list(title, lines):
    print()
    print(title)
    for line in lines:
        print(f"  - {line}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--template-ids", default=None,
                        help="CSV de product.template; las ventas se reparten entre ellos")
    parser.add_argument("--template-id", type=int, default=None,
                        help="Un solo product.template (compatibilidad)")
    parser.add_argument("--pickings", type=int, default=None,
                        help="Ventas en cola (por defecto 100)")
    parser.add_argument("--drainers", type=int, default=None,
                        help="Drenadores concurrentes (1 = cron normal; por defecto 1)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Obsoleto: alias de --drainers")
    args = parser.parse_args()

    if args.workers is not None:
        print("Aviso: --workers es obsoleto; se usa como --drainers. Antes también "
              "fijaba el número de ventas; ahora las ventas van en --pickings.")
        args.drainers = args.drainers or args.workers
    args.drainers = args.drainers or 1
    args.pickings = args.pickings or 100

    ids = args.template_ids or (str(args.template_id) if args.template_id else "")
    try:
        args.template_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        parser.error("--template-ids debe ser una lista de enteros separada por comas")
    if not args.template_ids:
        parser.error("indicá --template-ids (o --template-id)")
    if args.drainers < 1 or args.pickings < 1:
        parser.error("--drainers y --pickings deben ser >= 1")

    multiprocessing.set_start_method("spawn", force=True)

    print("=" * 70)
    print(" POS INVENTORY QUEUE — PRUEBA DE CARGA")
    print("=" * 70)
    print(f"BD {args.db} · sesión {args.session} · productos {args.template_ids} · "
          f"{args.pickings} ventas · {args.drainers} drenador(es)")
    print()

    try:
        args.state = prepare(args)
    except EnvironmentProblem as exc:
        print()
        print("⛔ ERROR DEL ENTORNO / DEL TEST — la prueba no se ejecutó:")
        print(exc)
        print()
        print(" RESULTADO FINAL: ENTORNO (no dice nada del módulo)")
        sys.exit(2)

    print()
    print(f"Lanzando {args.drainers} drenador(es)...")
    outcomes, drain_seconds = run_drainers(args)
    extra_passes = converge(args)
    module_errors, env_errors, improvements = validate(
        args, outcomes, drain_seconds, extra_passes)

    print()
    print("=" * 70)
    if env_errors:
        _print_list("⛔ ERRORES DEL ENTORNO (límites de la máquina, no del módulo):",
                    env_errors[:10] + ([f"... y {len(env_errors) - 10} más"]
                                       if len(env_errors) > 10 else []))
    if module_errors:
        _print_list("❌ ERRORES DEL MÓDULO:", module_errors[:30])
        for outcome in outcomes:
            if outcome["status"] == "modulo":
                print(outcome.get("traceback", ""))
    if improvements:
        _print_list("⚠️  OPORTUNIDADES DE MEJORA:", improvements)
    if not (env_errors or module_errors or improvements):
        print()
        print("✅ Todas las ventas quedaron validadas, el stock físico cuadra, cada "
              "ítem tiene sus fechas y no quedaron locks pegados.")

    print()
    if module_errors:
        verdict, code = "FAIL — error del módulo", 1
    elif env_errors:
        verdict, code = "ENTORNO — el módulo terminó bien, pero el entorno falló durante la prueba", 2
    elif improvements:
        verdict, code = "PASS con oportunidades de mejora", 0
    else:
        verdict, code = "PASS", 0
    print(f" RESULTADO FINAL: {verdict}")
    print("=" * 70)
    sys.exit(code)


if __name__ == "__main__":
    main()
