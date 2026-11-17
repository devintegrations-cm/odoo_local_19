# -*- coding: utf-8 -*-
"""Reglas duras sobre el soporte de una operacion de inventario.

La IA de vision solo transcribio la foto. Lo que decide si el soporte respalda
la operacion se calcula aqui, con reglas deterministas, para que una diferencia
de inventario se pueda explicar sin depender de un modelo.

Las reglas leen **los campos del soporte**, no la respuesta de la IA: esos
campos son lo que la IA leyo mas lo que una persona corrigio o capturo a mano.
De la respuesta solo se usan la legibilidad, el motivo de un fallo y las notas
que dejo el modelo al leer.

Cada regla es una funcion ``_rule_xxx(ctx)`` que devuelve una lista de
``Finding``. ``run_rules`` las ejecuta todas: si una revienta, las demas
siguen corriendo. El almacen necesita ver todos los hallazgos de una vez.
"""

import logging

from odoo.tools import float_compare, float_is_zero

from . import vision_adapter

_logger = logging.getLogger(__name__)

LEVEL_OK = "ok"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"

# Por defecto no se tolera ninguna diferencia de cantidad: en inventario una
# unidad de mas o de menos es justo lo que hay que ver.
DEFAULT_TOLERANCE_PCT = 0.0
DEFAULT_TOLERANCE_ABS = 0.0

# Por debajo de esto la foto se considera poco legible y se avisa.
LEGIBILITY_THRESHOLD = 0.5
# Confianza minima para creerle a la IA que vio (o no vio) un trazo de firma.
SIGNATURE_CONFIDENCE_THRESHOLD = 0.6


class Finding:
    """Resultado de una regla."""

    __slots__ = ("level", "code", "message_es", "details")

    def __init__(self, level, code, message_es, details=None):
        self.level = level
        self.code = code
        self.message_es = message_es
        self.details = details or {}

    def to_dict(self):
        return {
            "level": self.level,
            "code": self.code,
            "message_es": self.message_es,
            "details": self.details,
        }

    def __repr__(self):
        return "<Finding %s %s>" % (self.level, self.code)


def verdict_from_findings(findings):
    """Traduce los hallazgos al estado del soporte."""
    levels = {f.level for f in findings}
    if LEVEL_ERROR in levels:
        return "rejected"
    if LEVEL_WARNING in levels:
        return "warning"
    return "approved"


# ---------------------------------------------------------------------------
# Ajustes y helpers
# ---------------------------------------------------------------------------

def _param(env, key, default=None):
    value = env["ir.config_parameter"].sudo().get_param(key)
    return value if value not in (None, False, "") else default


def _param_bool(env, key, default=True):
    """Los Boolean de Ajustes se guardan a mano como "True"/"False".

    Odoo borra el ``ir.config_parameter`` cuando un Boolean de Ajustes queda en
    False, y entonces "ausente" se confundiria con "activado".
    """
    raw = _param(env, key)
    if raw is None:
        return default
    return str(raw).lower() in ("true", "1")


def _param_float(env, key, default):
    try:
        return float(_param(env, key, default))
    except (TypeError, ValueError):
        return default


def party_check_enabled(env):
    return _param_bool(env, "sos.party_check", True)


def signature_check_enabled(env):
    return _param_bool(env, "sos.signature_check", True)


def auto_validate_enabled(env):
    return _param_bool(env, "sos.auto_validate", True)


def _company_nit(env, company):
    return vision_adapter.normalize_nit(
        _param(env, "sos.company_nit") or company.vat or ""
    )


class Tolerance:
    """Las dos tolerancias de cantidad, con el criterio mas permisivo."""

    def __init__(self, pct, abs_value, rounding):
        self.pct = pct
        self.abs_value = abs_value
        self.rounding = rounding

    @classmethod
    def from_env(cls, env):
        rounding = env["decimal.precision"].precision_get("Product Unit")
        return cls(
            pct=_param_float(env, "sos.qty_tolerance_pct", DEFAULT_TOLERANCE_PCT),
            abs_value=_param_float(env, "sos.qty_tolerance_abs", DEFAULT_TOLERANCE_ABS),
            rounding=10 ** -rounding if rounding else 0.01,
        )

    def within(self, difference, reference):
        """True si la diferencia cabe en el porcentaje O en el monto absoluto."""
        difference = abs(difference)
        if float_is_zero(difference, precision_rounding=self.rounding):
            return True
        if self.abs_value and difference <= self.abs_value:
            return True
        if self.pct and reference:
            return (difference / abs(reference)) * 100.0 <= self.pct
        return False


def _qty(value):
    return ("%.4f" % (value or 0.0)).rstrip("0").rstrip(".")


def expected_quantity(move):
    """Cantidad de la operacion contra la que se compara la remision.

    Si el movimiento ya se marco como hecho (o la operacion esta validada), lo
    que importa es lo que realmente entro: ``quantity``. Si todavia no, lo
    esperado es la demanda: ``product_uom_qty``. El hallazgo dice cual se uso,
    porque no es lo mismo discutir contra lo pedido que contra lo recibido.
    """
    if move.picking_id.state == "done" or move.picked:
        return move.quantity, "registrada"
    return move.product_uom_qty, "esperada"


def parties_for(picking):
    """Quien entrega y quien recibe, segun el tipo de operacion.

    Devuelve ``(sender, receiver)``; cada uno es un dict con ``nit``, ``name``
    y ``label``. En una recepcion entrega el proveedor y recibe la compania;
    en una entrega es al reves; en un movimiento interno la compania hace las
    dos puntas.
    """
    env = picking.env
    company = picking.company_id or env.company
    company_party = {
        "nit": _company_nit(env, company),
        "name": company.name,
        "label": "la compania",
    }
    partner = picking.partner_id.commercial_partner_id or picking.partner_id
    partner_party = {
        "nit": vision_adapter.normalize_nit(partner.vat or ""),
        "name": partner.name or "",
        "label": "el contacto de la operacion",
    }
    code = picking.picking_type_code
    if code == "incoming":
        return partner_party, company_party
    if code == "outgoing":
        return company_party, partner_party
    return company_party, company_party


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------

def _rule_manual_capture(ctx):
    """Sin lectura de la IA no hay nada que comparar: se pide captura manual."""
    parsed = ctx["parsed"]
    reason = parsed.get("error") or "no se obtuvo lectura del documento"
    if not ctx["no_data"]:
        if parsed.get("available"):
            return []
        return [Finding(
            LEVEL_OK, "MANUAL_CAPTURE",
            "Los datos del soporte se capturaron a mano (%s)." % reason,
            {"reason": reason},
        )]
    return [Finding(
        LEVEL_WARNING, "MANUAL_CAPTURE_REQUIRED",
        "No hay datos leidos del soporte (%s). Capture a mano las cantidades y "
        "las partes en la pestana correspondiente y vuelva a validar; mientras "
        "tanto las reglas de cantidades y firmas no corren." % reason,
        {"reason": reason},
    )]


def _rule_legibility(ctx):
    confidence = ctx["parsed"].get("confidence") or 0.0
    if not ctx["parsed"].get("available"):
        return []
    if confidence >= LEGIBILITY_THRESHOLD:
        return [Finding(LEVEL_OK, "LEGIBILITY",
                        "El documento se leyo con confianza %.0f%%." % (confidence * 100))]
    return [Finding(
        LEVEL_WARNING, "LOW_LEGIBILITY",
        "El soporte quedo poco legible (confianza %.0f%%). Verifique los datos "
        "leidos contra la foto antes de aceptarlo; si es posible, vuelva a "
        "tomarla con mejor luz y enfoque." % (confidence * 100),
        {"confidence": confidence},
    )]


def _rule_picking_state(ctx):
    picking = ctx["picking"]
    if picking.state == "cancel":
        return [Finding(
            LEVEL_ERROR, "PICKING_CANCELLED",
            "La operacion %s esta cancelada: un soporte no la respalda." % picking.name,
            {"state": picking.state},
        )]
    if picking.state == "draft":
        return [Finding(
            LEVEL_WARNING, "PICKING_DRAFT",
            "La operacion %s todavia esta en borrador; las cantidades se "
            "comparan contra la demanda y pueden cambiar." % picking.name,
            {"state": picking.state},
        )]
    return [Finding(LEVEL_OK, "PICKING_STATE",
                    "La operacion %s esta en estado %s." % (picking.name, picking.state))]


def _rule_sender_party(ctx):
    """La empresa que entrega en el documento es la que dice el sistema."""
    if not party_check_enabled(ctx["env"]):
        return []
    return _check_party(ctx, "sender", ctx["sender"], "quien entrega")


def _rule_receiver_party(ctx):
    """La empresa que recibe en el documento es la que dice el sistema."""
    if not party_check_enabled(ctx["env"]):
        return []
    return _check_party(ctx, "receiver", ctx["receiver"], "quien recibe")


def _check_party(ctx, key, expected, label):
    support = ctx["support"]
    found_nit = vision_adapter.normalize_nit(support["%s_nit" % key])
    found_name = (support["%s_name" % key] or "").strip()
    findings = []

    if not expected["nit"]:
        findings.append(Finding(
            LEVEL_WARNING, "%s_NIT_UNKNOWN" % key.upper(),
            "No hay NIT registrado para %s (%s), asi que no se pudo comparar "
            "con el documento." % (label, expected["name"] or expected["label"]),
        ))
    elif not found_nit:
        findings.append(Finding(
            LEVEL_WARNING, "%s_NIT_MISSING" % key.upper(),
            "No se pudo leer el NIT de %s en el soporte. Verifiquelo a mano "
            "contra %s." % (label, expected["name"]),
        ))
    elif not vision_adapter.same_nit(found_nit, expected["nit"]):
        # En una tirilla de supermercado la cajera rara vez pide el NIT: sale
        # a nombre de la caja o con un NIT mal digitado. Se avisa, no se
        # rechaza. El NIT de quien vende si tiene que ser el del proveedor.
        pos_receiver = key == "receiver" and ctx["support"].document_type == "tiquete_pos"
        findings.append(Finding(
            LEVEL_WARNING if pos_receiver else LEVEL_ERROR, "%s_NIT" % key.upper(),
            "El NIT de %s en el soporte (%s) no es el de %s (%s).%s"
            % (label, found_nit, expected["name"], expected["nit"],
               " La tirilla no quedo a nombre de la compania." if pos_receiver else ""),
            {"found": found_nit, "expected": expected["nit"]},
        ))
    else:
        findings.append(Finding(
            LEVEL_OK, "%s_NIT" % key.upper(),
            "El NIT de %s coincide con %s." % (label, expected["name"]),
        ))

    # La razon social se compara suave: en las remisiones se abrevia mucho. Con
    # el NIT correcto se tolera casi todo ('OLIMPICA S.A.' por 'SUPERTIENDAS Y
    # DROGUERIAS OLIMPICA S.A.'); solo avisa si no comparte nada.
    nit_ok = bool(found_nit and expected["nit"]
                  and vision_adapter.same_nit(found_nit, expected["nit"]))
    name_threshold = 0.2 if nit_ok else 0.5
    if found_name and expected["name"]:
        from . import line_matcher
        similarity = line_matcher.similarity_company(found_name, expected["name"])
        if similarity < name_threshold:
            findings.append(Finding(
                LEVEL_WARNING, "%s_NAME" % key.upper(),
                "La razon social de %s en el soporte ('%s') no se parece a la "
                "registrada ('%s'). Puede ser una abreviatura; verifique."
                % (label, found_name, expected["name"]),
                {"found": found_name, "expected": expected["name"],
                 "similarity": round(similarity, 2)},
            ))
    elif expected["name"] and not found_name and not nit_ok:
        findings.append(Finding(
            LEVEL_WARNING, "%s_NAME_MISSING" % key.upper(),
            "No se pudo leer la razon social de %s en el soporte." % label,
        ))
    return findings


# Que se exige segun el tipo de documento. Los soportes reales de la compania
# son sobre todo facturas y tiquetes de caja, no remisiones: un tiquete de
# supermercado no trae ninguna firma, y en una factura el "recibido" es una
# anotacion a mano (orden de compra, nombre, fecha) en cualquier parte.
# Nivel si falta, por tipo de documento; un tipo ausente no lo exige. La firma
# de quien entrega no se exige en ninguno: en 14 soportes reales de staging
# ningun proveedor la puso, ni en la unica remision. Lo que respalda la
# entrega es la constancia de recibido.
SENDER_POLICY = {}
# Factura sin constancia de recibido: observacion (decision del usuario,
# 2026-10-07); la factura electronica ya prueba la venta, la anotacion es de
# control interno.
RECEIVER_POLICY = {"remision": LEVEL_ERROR, "factura": LEVEL_WARNING, "otro": LEVEL_ERROR,
                   "": LEVEL_ERROR}

DOCUMENT_LABELS = {
    "remision": "una remision", "factura": "una factura", "tiquete_pos": "un tiquete de caja",
}


def _rule_signatures(ctx):
    """Firma de quien entrega y constancia de recibido, segun el documento.

    Remision, otro o sin tipo: la constancia de recibido (error si falta).
    Factura: la constancia de recibido, como observacion si falta. Tiquete de
    caja: ninguna, es una compra en punto de venta. La firma de quien entrega
    se lee y se muestra, pero no se exige.
    """
    if not signature_check_enabled(ctx["env"]):
        return []
    support = ctx["support"]
    document_type = support.document_type or ""
    # La nota del modelo ("casilla vacia", "trazo tenue") acompana el mensaje.
    signatures = ctx["parsed"].get("signatures") or {}
    findings = []
    for key, label, policy in (("sender", "quien entrega", SENDER_POLICY),
                               ("receiver", "quien recibe", RECEIVER_POLICY)):
        missing_level = policy.get(document_type)
        if missing_level is None:
            findings.append(Finding(
                LEVEL_OK, "SIGNATURE_%s_NOT_REQUIRED" % key.upper(),
                "En %s no se exige firma de %s."
                % (DOCUMENT_LABELS.get(document_type, "este documento"), label),
            ))
            continue
        present = support["signature_%s_ok" % key]
        confidence = support["signature_%s_confidence" % key] or 0.0
        who = support["signature_%s_name" % key] or ""
        note = (signatures.get(key) or {}).get("note") or ""

        # Casilla marcada sin confianza de la IA: la marco una persona mirando
        # la foto (el formulario pone 1.0, pero una captura por importacion o
        # por codigo puede dejarla en 0). Esa confirmacion manda.
        if present and (confidence >= SIGNATURE_CONFIDENCE_THRESHOLD or not confidence):
            findings.append(Finding(
                LEVEL_OK, "SIGNATURE_%s" % key.upper(),
                "El soporte tiene la firma de %s%s."
                % (label, " (%s)" % who if who else ""),
                {"name": who, "confidence": confidence},
            ))
        elif present:
            findings.append(Finding(
                LEVEL_WARNING, "SIGNATURE_%s_UNCLEAR" % key.upper(),
                "Parece haber firma de %s, pero no se ve con claridad "
                "(confianza %.0f%%). Confirmela mirando la foto."
                % (label, confidence * 100),
                {"confidence": confidence, "note": note},
            ))
        else:
            if key == "receiver":
                message = ("El soporte no tiene constancia de recibido: ni firma, ni "
                           "nombre, fecha u orden de compra escritos a mano")
            else:
                message = "El soporte no tiene firma de %s" % label
            findings.append(Finding(
                missing_level, "SIGNATURE_%s_MISSING" % key.upper(),
                "%s%s." % (message, " (%s)" % note if note else ""),
                {"note": note},
            ))
    return findings


def _rule_lines_matched(ctx):
    support = ctx["support"]
    services = support.line_ids.filtered("is_service")
    goods = support.line_ids - services
    findings = []
    if services:
        findings.append(Finding(
            LEVEL_OK, "SERVICE_LINES",
            "No son mercancia y no se comparan: %s."
            % ", ".join(line.description[:40] or "(sin descripcion)" for line in services),
        ))
    if not goods:
        return [Finding(
            LEVEL_ERROR, "NO_LINES",
            "El soporte no tiene ninguna linea de mercancia: no se puede comparar "
            "contra la operacion. Capture las cantidades a mano o vuelva a leer el "
            "documento.",
        )]
    unmatched = goods.filtered(lambda line: not line.move_id)
    if not unmatched:
        return findings + [Finding(LEVEL_OK, "LINES_MATCHED",
                                   "Las %s lineas de mercancia se asociaron a la operacion."
                                   % len(goods))]
    return findings + [Finding(
        LEVEL_WARNING, "LINES_MATCHED",
        "%s de %s lineas del soporte no se pudieron asociar a un movimiento de "
        "la operacion: %s. Asocielas a mano en la pestana Lineas."
        % (len(unmatched), len(goods),
           ", ".join(line.description[:40] or "(sin descripcion)" for line in unmatched[:5])),
        {"unmatched": unmatched.mapped("description")},
    )]


def _rule_quantities(ctx):
    """El corazon del modulo: lo que dice el papel contra lo que dice el sistema."""
    support = ctx["support"]
    tolerance = ctx["tolerance"]
    findings = []

    # Varias lineas de la remision pueden apuntar al mismo movimiento (entregas
    # partidas en el papel), asi que se suma antes de comparar. Se compara la
    # cantidad ya pasada a la unidad del movimiento; una linea cuya unidad no
    # se pudo convertir no se compara (la regla de unidades la reporta).
    by_move = {}
    for line in support.line_ids.filtered(
        lambda line: line.move_id and line.uom_status != "unknown"
    ):
        by_move.setdefault(line.move_id, 0.0)
        by_move[line.move_id] += line.quantity_converted

    for move, document_qty in by_move.items():
        system_qty, basis = expected_quantity(move)
        difference = document_qty - system_qty
        product = move.product_id.display_name

        unit = move.product_uom.name
        if tolerance.within(difference, system_qty):
            findings.append(Finding(
                LEVEL_OK, "QTY_MATCH",
                "%s: el soporte dice %s %s y la operacion %s %s."
                % (product, _qty(document_qty), unit, _qty(system_qty), unit),
                {"product": product, "document": document_qty, "system": system_qty},
            ))
        elif difference > 0:
            findings.append(Finding(
                LEVEL_ERROR, "QTY_OVER_OPERATION",
                "%s: el soporte respalda %s pero la operacion solo tiene %s "
                "(%s). Entraria mas mercancia de la registrada; revise antes "
                "de validar la operacion."
                % (product, _qty(document_qty), _qty(system_qty), basis),
                {"product": product, "document": document_qty,
                 "system": system_qty, "difference": difference, "basis": basis},
            ))
        else:
            findings.append(Finding(
                LEVEL_ERROR, "QTY_UNDER_OPERATION",
                "%s: el soporte respalda solo %s y la operacion tiene %s (%s). "
                "Faltan %s por respaldar."
                % (product, _qty(document_qty), _qty(system_qty), basis,
                   _qty(abs(difference))),
                {"product": product, "document": document_qty,
                 "system": system_qty, "difference": difference, "basis": basis},
            ))

    # Movimientos de la operacion que el soporte no menciona. Los que si
    # menciona pero en una unidad sin convertir no cuentan como faltantes.
    moves = support.picking_id.move_ids.filtered(lambda m: m.state != "cancel")
    missing = moves - support.line_ids.mapped("move_id")
    for move in missing:
        system_qty, basis = expected_quantity(move)
        if float_is_zero(system_qty, precision_rounding=tolerance.rounding):
            continue
        findings.append(Finding(
            LEVEL_WARNING, "QTY_MISSING_IN_DOCUMENT",
            "%s: la operacion tiene %s (%s) pero el soporte no lo menciona."
            % (move.product_id.display_name, _qty(system_qty), basis),
            {"product": move.product_id.display_name, "system": system_qty, "basis": basis},
        ))
    return findings


def _rule_units(ctx):
    """Lineas en otra unidad: como se convirtieron y si hay que revisarlas."""
    findings = []
    for line in ctx["support"].line_ids.filtered("move_id"):
        product = line.move_id.product_id.display_name
        if line.uom_status == "unknown":
            findings.append(Finding(
                LEVEL_WARNING, "UOM_UNKNOWN",
                "%s: el soporte dice %s %s y no se sabe cuanto es en %s, asi que "
                "no se comparo. Ponga el factor de unidad a mano en la linea."
                % (product, _qty(line.quantity), line.unit, line.move_id.product_uom.name),
                {"product": product, "unit": line.unit},
            ))
        elif line.uom_status == "ai_unverified":
            findings.append(Finding(
                LEVEL_WARNING, "UOM_CONVERSION_UNVERIFIED",
                "%s: %s Mientras no se confirme, el soporte no se aprueba."
                % (product, line.uom_note),
                {"product": product, "factor": line.uom_factor},
            ))
        elif line.uom_status in ("converted", "ai", "manual"):
            findings.append(Finding(
                LEVEL_OK, "UOM_CONVERTED",
                "%s: %s %s = %s %s. %s"
                % (product, _qty(line.quantity), line.unit, _qty(line.quantity_converted),
                   line.move_id.product_uom.name, line.uom_note or ""),
                {"product": product, "factor": line.uom_factor, "status": line.uom_status},
            ))
        if line.match_method == "ai":
            findings.append(Finding(
                LEVEL_OK, "LINE_MATCHED_BY_AI",
                "'%s' se asocio a %s. %s" % (line.description, product, line.match_note or ""),
            ))
    return findings


def _rule_document_reference(ctx):
    remission_ref = ctx["support"].remission_ref
    if not remission_ref:
        return [Finding(
            LEVEL_WARNING, "REMISSION_REF_MISSING",
            "El soporte no tiene numero de remision: no se leyo ni se capturo.",
        )]
    return [Finding(LEVEL_OK, "REMISSION_REF", "Remision %s." % remission_ref)]


def _rule_duplicate_support(ctx):
    """El mismo numero de remision no deberia respaldar dos operaciones.

    La remision es de quien entrega: dos proveedores pueden tener cada uno su
    "REM-001". Si los dos soportes traen NIT de quien entrega y no es el mismo,
    no son la misma remision. Otro soporte de la misma operacion (la foto que
    se volvio a subir) tampoco cuenta.
    """
    support = ctx["support"]
    if not support.remission_ref:
        return []
    candidates = support.search([
        ("id", "!=", support.id),
        ("picking_id", "!=", support.picking_id.id),
        ("remission_ref", "=", support.remission_ref),
        ("state", "in", ("approved", "warning")),
    ], limit=20)
    duplicates = candidates.filtered(
        lambda other: not (support.sender_nit and other.sender_nit)
        or vision_adapter.same_nit(support.sender_nit, other.sender_nit)
    )[:5]
    if not duplicates:
        return [Finding(LEVEL_OK, "REMISSION_UNIQUE",
                        "La remision %s no esta en otro soporte." % support.remission_ref)]
    return [Finding(
        LEVEL_ERROR, "REMISSION_DUPLICATE",
        "La remision %s ya respalda %s. Un mismo comprobante no puede "
        "respaldar dos operaciones."
        % (support.remission_ref,
           ", ".join("%s (%s)" % (d.name, d.picking_id.name) for d in duplicates)),
        {"duplicates": duplicates.mapped("name")},
    )]


# Reglas que corren siempre, incluso sin lectura del documento.
ALWAYS_RULES = (
    _rule_manual_capture,
    _rule_picking_state,
    _rule_legibility,
)

# Reglas que solo tienen sentido con datos leidos o capturados.
DATA_RULES = (
    _rule_sender_party,
    _rule_receiver_party,
    _rule_signatures,
    _rule_lines_matched,
    _rule_units,
    _rule_quantities,
    _rule_document_reference,
    _rule_duplicate_support,
)


def run_rules(support, parsed):
    """Ejecuta todas las reglas sobre un soporte ya extraido.

    :param support: recordset ``stock.operation.support`` (uno solo)
    :param parsed: dict normalizado del adaptador de vision
    :return: lista de ``Finding``
    """
    support.ensure_one()
    parsed = parsed or {}
    tolerance = Tolerance.from_env(support.env)
    # "Sin datos" es no tener ni lineas ni partes: ni leidas ni capturadas.
    no_data = not support.line_ids and not (support.sender_nit or support.receiver_nit)
    sender, receiver = parties_for(support.picking_id)

    ctx = {
        "support": support,
        "picking": support.picking_id,
        "parsed": parsed,
        "env": support.env,
        "tolerance": tolerance,
        "no_data": no_data,
        "sender": sender,
        "receiver": receiver,
    }

    findings = []
    rules = ALWAYS_RULES if no_data else ALWAYS_RULES + DATA_RULES
    for rule in rules:
        try:
            findings.extend(rule(ctx))
        except Exception:  # noqa: BLE001 - una regla rota no debe ocultar las demas
            _logger.exception("[SOS] %s: la regla %s fallo", support.name, rule.__name__)
            findings.append(Finding(
                LEVEL_ERROR, "RULE_CRASHED",
                "La regla %s fallo al ejecutarse; revise el log."
                % rule.__name__.replace("_rule_", "").upper(),
            ))

    # Lo que anoto la IA al leer (cantidad tachada, dato ilegible) tambien se
    # muestra: son observaciones del documento, no de las reglas. Si no hubo
    # lectura, el motivo ya quedo en MANUAL_CAPTURE.
    for warning in (parsed.get("raw_warnings") or []) if parsed.get("available") else []:
        findings.append(Finding(LEVEL_WARNING, "DOCUMENT_WARNING", str(warning)))
    return findings
