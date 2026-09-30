import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Numeración de venta del POS a 'standard' (paridad con Odoo 17).

    Odoo 19 crea las secuencias de órdenes y líneas del POS 'no_gap' y las
    bloquea durante toda la venta; en 17 eran 'standard'. Idempotente: vuelve a
    correr sin cambiar nada si ya están en 'standard'.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    configs = env['pos.config'].with_context(active_test=False).search([])
    changed = configs._pos_queue_standard_sequences()
    _logger.info(
        'pos_inventory_queue 19.0.1.2.0: %d POS revisados, %d secuencia(s) '
        'pasadas a standard', len(configs), len(changed),
    )
