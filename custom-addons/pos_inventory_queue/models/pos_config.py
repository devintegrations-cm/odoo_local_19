import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Secuencias del POS que se usan en cada venta y que Odoo 19 crea 'no_gap'
# (point_of_sale pos_config._create_sequences): una fila de ir_sequence por POS
# que la venta bloquea (FOR UPDATE NOWAIT) hasta el commit, así que los cajeros
# de una misma tienda se esperan entre sí y, con carga, el POS muestra
# "could not obtain lock on row in relation ir_sequence". Odoo 17 las creaba
# 'standard' (pos_config._config_sequence_implementation), sin bloqueo.
#   - order_seq_id: sequence_number de la orden (el POS lo manda en 0).
#   - order_line_seq_id: nombre de la línea (el POS no lo manda).
#   - order_backend_seq_id: referencia de órdenes sin pos_reference
#     (backend, autoservicio).
# device_seq_id no se toca: se usa al registrar un dispositivo, no al vender.
# Ninguna es numeración fiscal: la factura electrónica (Jorels) numera con
# account_move.name y la resolución DIAN.
STANDARD_SEQUENCE_FIELDS = (
    'order_seq_id',
    'order_line_seq_id',
    'order_backend_seq_id',
)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _create_sequences(self):
        super()._create_sequences()
        self._pos_queue_standard_sequences()

    def _pos_queue_standard_sequences(self):
        """Pasa a 'standard' las secuencias de venta de estos POS (paridad 17).

        Idempotente: solo toca las que no están en 'standard'. ir.sequence
        crea la secuencia de PostgreSQL con el número siguiente actual, así
        que la numeración continúa sin saltos. Devuelve las secuencias
        cambiadas.
        """
        sequences = self.env['ir.sequence']
        for field in STANDARD_SEQUENCE_FIELDS:
            sequences |= self.mapped(field)
        to_change = sequences.filtered(lambda s: s.implementation != 'standard')
        if to_change:
            to_change.sudo().write({'implementation': 'standard'})
            _logger.info(
                'POS Queue: %d secuencia(s) de POS pasadas a standard: %s',
                len(to_change), to_change.mapped('name'),
            )
        return to_change
