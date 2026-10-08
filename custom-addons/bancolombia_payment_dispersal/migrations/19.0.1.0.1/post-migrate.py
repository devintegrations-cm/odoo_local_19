import logging
import re

_logger = logging.getLogger(__name__)

TABLE = 'bancolombia_payment_dispersal_field'
BACKUP = 'bk_bancolombia_dispersal_field_value_17'

# (patrón, reemplazo). Solo fragmentos que en 19 fallan o cambian de sentido;
# el resto de la fórmula, editada a mano o no, queda igual.
REPLACEMENTS = [
    # account.payment ya no hereda de account.move: `ref` pasó a `memo`.
    (re.compile(r'\bobject\.ref\b'), 'object.memo'),
    # En 19 un pago en borrador no tiene número (name False); en 17 era '/'.
    # Solo la línea que termina en object.name (fórmula del XML)...
    (re.compile(r"\breference = object\.name[ \t]*$", re.MULTILINE), "reference = object.name or '/'"),
    # ...y cualquier object.name.split(...) (fórmulas personalizadas en prod).
    (re.compile(r'\bobject\.name\.split\('), "(object.name or '/').split("),
    # res.partner.mobile no existe en 19: queda solo phone.
    (re.compile(r'\b((?:\w+\.)*\w+)\.mobile or \1\.phone\b'), r'\1.phone'),
]
LEFTOVER = re.compile(r'\bobject\.ref\b|\.mobile\b')


def migrate(cr, version):
    """Corrige las fórmulas de las columnas del archivo Bancolombia para Odoo 19.

    Los registros vienen con noupdate=1, así que el -u no los reescribe desde el
    XML. Recorre todas las filas (cualquier compañía, activas o archivadas),
    guarda el valor original en una tabla de respaldo y es idempotente.
    Revertir: UPDATE bancolombia_payment_dispersal_field f SET value = b.value
    FROM bk_bancolombia_dispersal_field_value_17 b WHERE b.id = f.id;
    """
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", (TABLE,))
    if not cr.fetchone()[0]:
        return
    cr.execute(f"SELECT id, value FROM {TABLE} WHERE value IS NOT NULL")
    changed = 0
    for rec_id, value in cr.fetchall():
        new = value
        for pattern, repl in REPLACEMENTS:
            new = pattern.sub(repl, new)
        if LEFTOVER.search(new):
            _logger.warning(
                "%s id=%s: la fórmula sigue usando 'object.ref' o '.mobile'; "
                "revisarla a mano", TABLE, rec_id,
            )
        if new == value:
            continue
        cr.execute(
            f"CREATE TABLE IF NOT EXISTS {BACKUP} ("
            "id integer PRIMARY KEY, value text, "
            "saved_at timestamp DEFAULT (now() at time zone 'UTC'))"
        )
        cr.execute(
            f"INSERT INTO {BACKUP} (id, value) VALUES (%s, %s) "
            "ON CONFLICT (id) DO NOTHING", (rec_id, value),
        )
        cr.execute(f"UPDATE {TABLE} SET value = %s WHERE id = %s", (new, rec_id))
        changed += 1
    _logger.info(
        'bancolombia_payment_dispersal 19.0.1.0.1: %d fórmula(s) corregida(s)',
        changed,
    )
