# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Campo de Jorels (l10n_co_edi_jorels). Desde Odoo 18, fields_get calcula `groupable` y, para un
    # Many2many, arma un _read_group_groupby que llama ir.attachment._search sin límite: para un usuario
    # que no es superusuario trae todos los adjuntos y revisa el acceso uno por uno en Python, lo que
    # agota la memoria del worker al abrir cualquier vista de facturas. Saltar la revisión de acceso
    # en la búsqueda sobre el comodelo deja ese cálculo en SQL. Leer y adjuntar documentos no cambia.
    # Diagnóstico: auditoria/diagnostico_memoria_facturas/README.md
    ei_additional_documents = fields.Many2many(bypass_search_access=True)

    def _post(self, soft=True):
        """Extiende el posteo de facturas para crear un pago automático
        cuando hay líneas de recompensa (invoice_reward_line) y saldo
        residual pendiente.

        IMPORTANTE: para facturas generadas desde el POS NO se crea
        ningún pago automático, porque el POS ya maneja sus propios
        pagos y conciliaciones.
        """
        res = super(AccountMove, self)._post(soft)

        for move in self:
            # Solo facturas de cliente
            if move.move_type != 'out_invoice':
                continue

            # Si la factura viene de un POS order, NO tocar pagos ni conciliación
            # pos.order tiene Many2one account_move, así que buscamos por ahí
            is_pos_invoice = self.env['pos.order'].sudo().search_count([
                ('account_move', '=', move.id)
            ]) > 0
            if is_pos_invoice:
                _logger.debug(
                    "Skipping automatic reward payment for POS invoice %s", move.name
                )
                continue

            # ¿Tiene líneas de recompensa?
            reward_inv_line = move.invoice_line_ids.filtered('invoice_reward_line')
            if not reward_inv_line:
                continue

            # ¿Hay saldo pendiente?
            if not move.amount_residual:
                continue

            # Intentar reutilizar un pago existente ligado a la factura
            existing_payment = move.line_ids.mapped('payment_id').filtered(lambda p: p.state == 'posted')
            existing_payment = existing_payment[:1] if existing_payment else self.env['account.payment']

            if existing_payment:
                payment_method_line = existing_payment.payment_method_line_id
                journal = existing_payment.journal_id
            else:
                payment_method_line = False
                journal = move.journal_id

            if not journal:
                _logger.warning(
                    "No journal found to register reward payment for move %s",
                    move.name,
                )
                continue

            # Si no tenemos método de pago, tomar uno del diario según el sentido
            if not payment_method_line:
                if move.amount_residual >= 0:
                    payment_method_line = journal.inbound_payment_method_line_ids[:1]
                else:
                    payment_method_line = journal.outbound_payment_method_line_ids[:1]

            if not payment_method_line:
                _logger.warning(
                    "No payment method line configured on journal %s for move %s. "
                    "Skipping automatic reward payment.",
                    journal.display_name,
                    move.name,
                )
                continue

            # Usar el wizard estándar de pagos para evitar problemas de validación
            ctx = {
                'active_model': 'account.move',
                'active_ids': move.ids,
            }

            register_vals = {
                'journal_id': journal.id,
                'amount': abs(move.amount_residual),
                'payment_date': fields.Date.context_today(self),
                'payment_method_line_id': payment_method_line.id,
            }

            payment_register = self.env['account.payment.register'].with_context(ctx).create(register_vals)
            payment_register.action_create_payments()

            _logger.info(
                "Created automatic reward payment for move %s with journal %s and method line %s",
                move.name,
                journal.display_name,
                payment_method_line.display_name,
            )

        return res

    def action_post(self):
        """Dejamos action_post estándar, toda la lógica custom se maneja en _post."""
        return super(AccountMove, self).action_post()

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        res._update_reward_prices()
        return res

    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        self._update_reward_prices()
        return res

    def _update_reward_prices(self):
        for rec in self:
            for inv_line in rec.invoice_line_ids:
                if inv_line.invoice_reward_line and inv_line.price_unit != 0:
                    inv_line.invoice_reward_price = inv_line.price_unit
                    inv_line.product_id.reward_price = inv_line.price_unit
                    inv_line.price_unit = 0
                    rec._compute_amount()
                elif (not inv_line.invoice_reward_line) and (inv_line.invoice_reward_price or 0.0) != 0:
                    inv_line.price_unit = inv_line.invoice_reward_price or 0.0
                    inv_line.invoice_reward_price = 0
