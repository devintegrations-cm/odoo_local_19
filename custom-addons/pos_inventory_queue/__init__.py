from . import models


def post_init_hook(env):
    """Instalación nueva sobre una base con POS existentes: numeración de venta
    a 'standard' (ver models/pos_config.py)."""
    env['pos.config'].with_context(active_test=False).search([])._pos_queue_standard_sequences()
