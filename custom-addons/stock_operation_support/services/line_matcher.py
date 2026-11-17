# -*- coding: utf-8 -*-
"""Emparejamiento de las lineas de la remision con los movimientos de la operacion.

Es determinista a proposito: la IA ya hizo lo suyo al leer la foto, y de ahi
en adelante lo que decide que linea es cual es codigo y descripcion, no otro
modelo. Asi el resultado es reproducible y explicable frente a una diferencia
de inventario.

Orden de preferencia:

1. Lo que el usuario emparejo a mano (``match_method = manual``) no se toca,
   ni siquiera al revalidar.
2. Por codigo: referencia interna, codigo de barras y codigo del proveedor.
3. Por descripcion normalizada: igualdad exacta y luego solapamiento de
   palabras por encima de un umbral.
4. Por IA, solo lo que quedo pendiente: lineas sin producto y lineas cuya
   unidad Odoo no sabe pasar a la del movimiento ("CAJA x 24" contra
   Unidades). La IA propone producto y factor; el factor se acepta solo si
   esta escrito en la linea o en un empaque registrado del producto.

Despues de emparejar, cada linea lleva su factor de unidad: cuantas unidades
del movimiento vale una unidad del papel. Las reglas comparan la cantidad
convertida.
"""

import difflib
import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)

# Debajo de esto no se empareja: queda para que lo revise una persona.
DESCRIPTION_THRESHOLD = 0.6

# Palabras que no distinguen nada en una remision colombiana.
STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "con", "sin", "para",
    "por", "un", "una", "unidad", "unidades", "und", "uds", "ref", "cod",
    # Sufijos de los nombres internos de la compania ("JUGO DE NARANJA
    # INSUMO", "REDUCCION ... SUB RECETA"): el proveedor nunca los escribe.
    "insumo", "sub", "receta", "subreceta",
}

# Formas societarias: no distinguen una empresa de otra y el documento las
# escribe de mil maneras. Se quitan de los dos lados antes de comparar
# razones sociales.
COMPANY_STOPWORDS = {
    "sas", "sa", "ltda", "ltd", "cia", "compania", "eu", "spa", "sac",
    "inc", "llc", "corp", "srl", "sociedad", "anonima", "limitada",
}


def normalize_code(value):
    """Codigo comparable: sin espacios, guiones ni puntos, en mayusculas."""
    return re.sub(r"[\s\-_.]", "", str(value or "")).upper()


def normalize_text(value):
    """Texto comparable: sin tildes, sin signos, en minusculas."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^0-9a-zA-Z\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _singular(word):
    """'palitos' -> 'palito', 'insumos' -> 'insumo'. Basta para remisiones."""
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(value):
    words = (_singular(word) for word in normalize_text(value).split())
    return {word for word in words if word not in STOPWORDS}


def _similarity(left, right):
    """Solapamiento de palabras (Jaccard). 1.0 es identico, 0.0 nada en comun."""
    left_tokens, right_tokens = _tokens(left), _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    common = left_tokens & right_tokens
    return len(common) / float(len(left_tokens | right_tokens))


def _name_contained(description, name):
    """0.9 si todas las palabras del nombre del producto estan en la descripcion.

    La remision suele decir mas que el producto: 'Te Chai Dorado bolsa' para
    el producto 'CHAI DORADO'. El Jaccard castiga esas palabras de sobra (da
    0.5) aunque el nombre completo este ahi. Se exigen dos palabras o mas para
    que un nombre corto como 'CAFE' no case con cualquier cosa, y se deja en
    0.9 para que una descripcion identica siga ganando.
    """
    name_tokens = _tokens(name)
    if len(name_tokens) < 2:
        return 0.0
    return 0.9 if name_tokens <= _tokens(description) else 0.0


def similarity_company(left, right):
    """Parecido entre dos razones sociales, ignorando la forma societaria.

    'CAFES DEL SUR S.A.S.' y 'CAFES DEL SUR SAS' son la misma empresa. Al
    normalizar, los puntos de 'S.A.S.' dejan 's a s' suelto, asi que ademas de
    las formas societarias se descartan los tokens de una sola letra: si no,
    dos escrituras de la misma empresa se parecen menos que dos empresas
    distintas.
    """
    def tokens(value):
        return {
            word for word in normalize_text(value).split()
            if len(word) > 1 and word not in STOPWORDS and word not in COMPANY_STOPWORDS
        }

    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    # Jaccard con tolerancia a errores de digitacion: dos palabras cuentan como
    # la misma si se parecen al 80 % ('coffe' y 'coffee', 'roaster' y
    # 'roasters'). Asi 'LIBERTARIO COFFE ROASTER' es la misma empresa.
    matched = sum(
        1 for word in left_tokens
        if any(difflib.SequenceMatcher(None, word, other).ratio() >= 0.8
               for other in right_tokens)
    )
    return matched / float(len(left_tokens) + len(right_tokens) - matched)


# Como se escriben las unidades en las remisiones -> xmlid de la unidad en
# Odoo. La "libra" no esta a proposito: en Colombia suele ser de 500 g y la
# lb de Odoo es de 453,6 g; eso lo decide una persona.
UNIT_ALIASES = {
    "uom.product_uom_unit": {"und", "un", "u", "unid", "unidad", "unidades", "uds", "ud",
                             "units", "unit", "ea", "pza", "pieza", "piezas"},
    "uom.product_uom_dozen": {"docena", "docenas", "doc", "dz", "dozens"},
    "uom.product_uom_kgm": {"kg", "kgs", "kgr", "k", "kilo", "kilos", "kilogramo",
                            "kilogramos"},
    "uom.product_uom_gram": {"g", "gr", "grs", "gramo", "gramos"},
    "uom.product_uom_ton": {"t", "ton", "tonelada", "toneladas"},
    "uom.product_uom_litre": {"l", "lt", "lts", "litro", "litros"},
}

# Lo que una IA puede proponer y se acepta sin mas si esta respaldado.
AI_MIN_CONFIDENCE = 0.6


def resolve_uom(env, unit_text):
    """La unidad de Odoo que corresponde al texto del papel, o una vacia."""
    text = normalize_text(unit_text)
    if not text:
        return env["uom.uom"]
    # Unidades propias de la compania ("Bolsa 500 g"): por nombre exacto.
    for uom in env["uom.uom"].search([]):
        if normalize_text(uom.name) == text:
            return uom
    # "Unidades X 80 Gr": la unidad es la primera palabra; lo demas es el
    # contenido, que no cambia como se cuenta.
    for candidate in (text, text.split()[0]):
        for xmlid, aliases in UNIT_ALIASES.items():
            if candidate in aliases:
                return env.ref(xmlid, raise_if_not_found=False) or env["uom.uom"]
    return env["uom.uom"]


def same_family(uom, other):
    """Las dos unidades se pueden convertir entre si.

    En 17 era ``uom.category_id == other.category_id``. En 19 no hay
    categorias: las unidades forman arboles por ``relative_uom_id`` y dos
    unidades son convertibles si comparten raiz (``_has_common_reference``).
    Hay que comprobarlo antes de convertir: ``_compute_quantity`` de 19 ya no
    falla entre familias distintas, multiplica igual (kg contra Unidades).
    """
    if not uom or not other:
        return False
    return uom == other or uom._has_common_reference(other)


def deterministic_factor(line, move):
    """``(factor, status, note)`` sin IA, o ``None`` si Odoo no sabe convertir."""
    move_uom = move.product_uom
    if not normalize_text(line.unit):
        # Sin unidad solo se puede asumir la misma si se cuenta en unidades:
        # "2 Baguette" contra una recepcion en gramos no son 2 g. En 17 era la
        # categoria "Unidad"; en 19, el arbol cuya raiz es uom.product_uom_unit.
        units = line.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if same_family(move_uom, units):
            return 1.0, "same", "Sin unidad en el soporte: se asume %s." % move_uom.name
        return None
    uom = resolve_uom(line.env, line.unit)
    if not same_family(uom, move_uom):
        return None
    if uom == move_uom:
        return 1.0, "same", ""
    factor = uom._compute_quantity(1.0, move_uom, round=False)
    return factor, "converted", "%s a %s (x %s)." % (uom.name, move_uom.name, _number(factor))


def _number(value):
    return ("%.6f" % value).rstrip("0").rstrip(".")


def _parse_number(raw):
    """'24' -> 24.0, '1,5' -> 1.5, '12.000' -> 12000.0 (punto de miles)."""
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


NUMBER = r"(\d+(?:[.,]\d+)*)"
# "x 24", "por 24", "c/24", "de 24": el contenido del empaque.
CONTENT_MARKER = re.compile(r"(?:\bx|\bpor|c/|\bde)\s*" + NUMBER, re.IGNORECASE)
# "25 kg", "500 g": un numero con su unidad.
NUMBER_WITH_UNIT = re.compile(NUMBER + r"\s*([a-zA-Z]+)")


def document_factors(line, move):
    """Factores que el texto de la linea respalda, en unidades del movimiento.

    Solo cuenta un numero que marca contenido ("caja x 24") o que va con una
    unidad de la misma categoria que el movimiento ("bulto 25 kg" contra g =
    25000). Un numero suelto no respalda nada: en "vaso 9 oz" contado en
    Unidades, el 9 no es cuantos vasos trae la caja.
    """
    text = "%s %s" % (line.description or "", line.unit or "")
    factors = [_parse_number(raw) for raw in CONTENT_MARKER.findall(text)]
    for raw, unit_text in NUMBER_WITH_UNIT.findall(text):
        uom = resolve_uom(line.env, unit_text)
        if same_family(uom, move.product_uom):
            factors.append(_parse_number(raw) * uom._compute_quantity(
                1.0, move.product_uom, round=False))
    return [factor for factor in factors if factor > 0]


def _packagings(product):
    """Empaques registrados del producto.

    En 19 ``product.packaging`` desaparecio: un empaque es una unidad de
    medida mas (``product.template.uom_ids``, "Packagings"), con su contenido
    en ``relative_factor`` sobre ``relative_uom_id``. Solo cuentan los de la
    misma familia que la unidad del producto, que es lo que en 17 expresaba
    ``packaging.qty`` (cantidad en la unidad del producto).
    """
    return product.uom_ids.filtered(lambda uom: same_family(uom, product.uom_id))


def packaging_factors(move):
    """Contenido de cada empaque registrado del producto, en unidades del movimiento."""
    return [
        packaging._compute_quantity(1.0, move.product_uom, round=False)
        for packaging in _packagings(move.product_id)
        if same_family(packaging, move.product_uom) and packaging.factor
    ]


def factor_is_backed(factor, line, move):
    """El factor que propuso la IA esta escrito en la linea o en un empaque.

    Lo demas puede ser correcto, pero no hay como comprobarlo sin una persona.
    """
    if factor <= 0:
        return False
    candidates = document_factors(line, move) + packaging_factors(move)
    return any(abs(factor - candidate) <= 1e-6 * max(1.0, abs(factor)) for candidate in candidates)


def move_codes(move):
    """Todos los codigos con los que se puede reconocer el producto del movimiento."""
    product = move.product_id
    codes = {product.default_code, product.barcode}
    # El codigo con el que el proveedor llama al producto en su remision.
    for seller in product.seller_ids:
        codes.add(seller.product_code)
    return {normalize_code(code) for code in codes if code}


def match_lines(support, adapter=None):
    """Empareja las lineas del soporte con los movimientos de la operacion.

    Escribe ``move_id``, ``match_method``, ``match_confidence`` y
    ``match_note`` en cada linea, y despues su factor de unidad. Lo que hizo
    una persona (``manual``) o la IA en una lectura anterior (``ai``) no se
    vuelve a calcular: la IA corre otra vez solo con "Volver a leer la foto".
    Devuelve un resumen para el log.
    """
    support.ensure_one()
    moves = support.picking_id.move_ids.filtered(lambda m: m.state != "cancel")
    # Los servicios (envio, domicilio) no son mercancia: ni se emparejan.
    goods = support.line_ids.filtered(lambda line: not line.is_service)
    (support.line_ids - goods).filtered("move_id").write({
        "move_id": False, "match_method": "none", "match_note": "Servicio: no es mercancia.",
    })
    fixed = goods.filtered(lambda line: line.match_method in ("manual", "ai"))
    pending = goods - fixed

    # Un movimiento ya usado por un emparejamiento fijo no se vuelve a ofrecer.
    taken = set(fixed.filtered("move_id").mapped("move_id").ids)

    by_code = 0
    by_description = 0
    for line in pending:
        available = moves.filtered(lambda m: m.id not in taken)
        if not available:
            line.write({
                "move_id": False, "match_method": "none",
                "match_confidence": 0.0,
                "match_note": "No quedan movimientos disponibles en la operacion.",
            })
            continue

        move, method, confidence, note = _best_match(line, available)
        if move:
            taken.add(move.id)
            if method == "code":
                by_code += 1
            else:
                by_description += 1
        line.write({
            "move_id": move.id if move else False,
            "match_method": method,
            "match_confidence": confidence,
            "match_note": note,
        })

    by_ai = _apply_units(support, moves, adapter)
    unmatched = len(pending) - by_code - by_description - by_ai
    _logger.info(
        "[SOS] %s: %s lineas, %s fijas, %s por codigo, %s por descripcion, %s por IA, "
        "%s sin emparejar", support.name, len(support.line_ids), len(fixed),
        by_code, by_description, by_ai, unmatched,
    )
    return {"code": by_code, "description": by_description, "ai": by_ai,
            "unmatched": unmatched}


def _apply_units(support, moves, adapter):
    """Pone el factor de unidad de cada linea; lo que Odoo no sabe, a la IA.

    Devuelve cuantas lineas emparejo la IA.
    """
    to_ai = support.env["stock.operation.support.line"]
    for line in support.line_ids.filtered(lambda l: not l.is_service):
        if line.uom_status == "manual" or line.match_method == "ai":
            continue
        if not line.move_id:
            to_ai |= line
            continue
        result = deterministic_factor(line, line.move_id)
        if result:
            factor, status, note = result
            line.write({"uom_factor": factor, "uom_status": status, "uom_note": note})
        else:
            to_ai |= line

    proposals = None
    if to_ai and adapter is not None:
        taken = set(support.line_ids.filtered(lambda l: l.move_id and l not in to_ai)
                    .mapped("move_id").ids)
        offered = moves.filtered(lambda m: m.id not in taken) | to_ai.mapped("move_id")
        proposals = adapter.match_units(
            [{"index": line.id, "code": line.code or "", "description": line.description or "",
              "quantity": line.quantity, "unit": line.unit or ""} for line in to_ai],
            [_move_for_ai(move) for move in offered],
        )
    by_index = {p["index"]: p for p in proposals or []}

    by_ai = 0
    for line in to_ai:
        proposal = by_index.get(line.id)
        if not proposal:
            if line.move_id:
                line.write({
                    "uom_factor": 1.0, "uom_status": "unknown",
                    "uom_note": _unknown_note(line, line.move_id),
                })
            continue
        move = moves.filtered(lambda m: m.id == proposal["move_id"])
        if not move:
            continue
        values = {}
        if not line.move_id:
            if proposal["confidence"] < AI_MIN_CONFIDENCE:
                line.match_note = "La IA sugiere '%s' (%.0f%%), por debajo del minimo." % (
                    move.product_id.name, proposal["confidence"] * 100)
                continue
            values.update({
                "move_id": move.id, "match_method": "ai",
                "match_confidence": proposal["confidence"],
                "match_note": "Emparejado por IA: %s" % (proposal["evidence"] or move.product_id.name),
            })
            by_ai += 1
        elif line.move_id != move:
            # La IA no cambia lo que ya se emparejo por codigo o descripcion.
            move = line.move_id
        deterministic = deterministic_factor(line, move)
        if deterministic:
            factor, status, note = deterministic
        elif factor_is_backed(proposal["factor"], line, move):
            factor, status = proposal["factor"], "ai"
            note = "IA: %s (x %s)." % (proposal["evidence"], _number(factor))
        else:
            factor = proposal["factor"] or 1.0
            status = "ai_unverified" if proposal["factor"] else "unknown"
            note = ("La IA propone x %s ('%s') pero no esta escrito en la linea ni en "
                    "un empaque del producto. Verifiquelo." % (_number(factor), proposal["evidence"])
                    if proposal["factor"] else _unknown_note(line, move))
        values.update({"uom_factor": factor, "uom_status": status, "uom_note": note})
        line.write(values)
    return by_ai


def _unknown_note(line, move):
    if not normalize_text(line.unit):
        return ("El soporte no dice la unidad y la operacion cuenta en %s. Ponga el "
                "factor a mano." % move.product_uom.name)
    return "No se sabe pasar '%s' a %s. Ponga el factor a mano." % (
        line.unit, move.product_uom.name)


def _move_for_ai(move):
    """Lo que la IA necesita de un movimiento. Sin cantidades, a proposito."""
    product = move.product_id
    return {
        "move_id": move.id,
        "code": product.default_code or "",
        "product": product.name,
        "uom": move.product_uom.name,
        # En 19 no existe uom_po_id: la unidad de compra es la del proveedor
        # (product.supplierinfo.product_uom_id). En 17 uom_po_id caia en la
        # unidad del producto si no se configuraba, igual que aqui.
        "purchase_uom": (product.seller_ids[:1].product_uom_id or product.uom_id).name,
        "packagings": [
            {"name": packaging.name,
             "contains": packaging._compute_quantity(1.0, product.uom_id, round=False),
             "uom": product.uom_id.name}
            for packaging in _packagings(product)
        ],
    }


def _best_match(line, moves):
    """Devuelve ``(move, method, confidence, note)`` para una linea."""
    line_code = normalize_code(line.code)
    if line_code:
        for move in moves:
            if line_code in move_codes(move):
                return move, "code", 1.0, "Codigo '%s' del producto." % line.code

    best_move, best_score = None, 0.0
    for move in moves:
        score = max(
            _similarity(line.description, move.product_id.name),
            _similarity(line.description, move.description_picking or ""),
            _name_contained(line.description, move.product_id.name),
        )
        if score > best_score:
            best_move, best_score = move, score

    if best_move and best_score >= DESCRIPTION_THRESHOLD:
        return (
            best_move, "description", round(best_score, 2),
            "Descripcion parecida a '%s' (%.0f%%)." % (best_move.product_id.name, best_score * 100),
        )
    if best_move:
        return (
            None, "none", round(best_score, 2),
            "Lo mas parecido es '%s' (%.0f%%), por debajo del minimo. Empareje a mano."
            % (best_move.product_id.name, best_score * 100),
        )
    return None, "none", 0.0, "No se parece a ningun producto de la operacion."
