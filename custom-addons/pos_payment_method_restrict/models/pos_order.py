from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    restriction_data = fields.Json(
        string='Datos de restricción',
        copy=False,
        help='Valores capturados en el popup al seleccionar el método de pago.',
    )
    restriction_id = fields.Many2one(
        comodel_name='pos.payment.customer.restriction',
        string='Restricción aplicada',
        ondelete='set null',
        copy=False,
        help='Restricción de pago que generó el popup de datos en esta orden.',
    )
    restriction_data_display = fields.Text(
        string='Datos del popup',
        compute='_compute_restriction_data_display',
        help='Valores ingresados en el popup, con las etiquetas definidas en la restricción.',
    )
    is_hotel_order = fields.Boolean(
        string='Orden hotel',
        compute='_compute_hotel_fields',
        store=True,
    )
    hotel_guest = fields.Char(
        string='Huésped',
        compute='_compute_hotel_fields',
        store=True,
    )
    hotel_room = fields.Char(
        string='Habitación',
        compute='_compute_hotel_fields',
        store=True,
    )
    hotel_data_summary = fields.Text(
        string='Datos adicionales',
        compute='_compute_hotel_fields',
        store=True,
    )

    @api.depends('restriction_data', 'restriction_id')
    def _compute_hotel_fields(self):
        for order in self:
            data = order.restriction_data or {}
            order.is_hotel_order = bool(order.restriction_id)
            order.hotel_guest = (
                data.get('hotel_guest') or data.get('huesped')
                or data.get('guest') or data.get('nombre_huesped') or ''
            )
            order.hotel_room = (
                data.get('hotel_room') or data.get('habitacion')
                or data.get('room') or data.get('numero_habitacion') or ''
            )
            parts = []
            for key, val in data.items():
                if val is not None and val != '':
                    parts.append('{}: {}'.format(
                        key.replace('_', ' ').capitalize(), val))
            order.hotel_data_summary = '\n'.join(parts)

    @api.depends('restriction_data', 'restriction_id')
    def _compute_restriction_data_display(self):
        for order in self:
            data = order.restriction_data or {}
            if not data:
                order.restriction_data_display = ''
                continue

            # Mapa de clave→etiqueta desde la configuración de la restricción
            label_map = {}
            if order.restriction_id:
                label_map = {
                    f.field_key: f.name
                    for f in order.restriction_id.restriction_field_ids
                }

            parts = []
            for key, val in data.items():
                if val is not None and val != '':
                    label = label_map.get(key, key.replace('_', ' ').capitalize())
                    parts.append('{}: {}'.format(label, val))
            order.restriction_data_display = '\n'.join(parts)

    # -------------------------------------------------------------------------
    # Detección de duplicados (llamada desde el POS via ORM)
    # -------------------------------------------------------------------------

    @api.model
    def check_restriction_duplicate(self, restriction_id, restriction_data):
        """Busca órdenes de hoy con la misma restricción y al menos un valor coincidente.

        Retorna lista de dicts {'name', 'time'} por cada posible duplicado.
        """
        if not restriction_data or not restriction_id:
            return []

        today = date.today()
        tomorrow = today + timedelta(days=1)

        today_orders = self.search([
            ('restriction_id', '=', restriction_id),
            ('date_order', '>=', '{} 00:00:00'.format(today)),
            ('date_order', '<', '{} 00:00:00'.format(tomorrow)),
        ])

        duplicates = []
        for order in today_orders:
            existing = order.restriction_data or {}
            for key, val in restriction_data.items():
                if not val:
                    continue
                if existing.get(key) and str(existing[key]).strip().lower() == str(val).strip().lower():
                    duplicates.append({
                        'name': order.name,
                        'time': order.date_order.strftime('%H:%M') if order.date_order else '',
                    })
                    break

        return duplicates

    # -------------------------------------------------------------------------
    # Entrega de inventario
    # -------------------------------------------------------------------------

    def _should_create_picking_real_time(self):
        """Fuerza picking real-time cuando la restricción del cliente lo exige."""
        if super()._should_create_picking_real_time():
            return True
        if not self.partner_id:
            return False
        config = self.session_id.config_id
        if not config.payment_restrict_enabled:
            return False
        return bool(config.payment_customer_restriction_ids.filtered(
            lambda r: self.partner_id in r.partner_ids and r.create_delivery
        ))

    # -------------------------------------------------------------------------
    # Factura agrupada — lógica compartida
    # -------------------------------------------------------------------------

    def _action_grouped_invoice_common(self, ei=False):
        """
        Agrupa las órdenes seleccionadas por cliente y crea una sola factura
        por grupo.

        :param ei: Si True, usa el diario de factura electrónica (DIAN).
        """
        orders_ok = self.filtered(
            lambda o: o.state == 'paid' and not o.account_move and o.partner_id
        )
        if not orders_ok:
            raise UserError(_(
                'No hay órdenes válidas para facturar.\n'
                'Las órdenes deben estar en estado "Pagado", '
                'sin factura previa y con cliente asignado.'
            ))

        # Agrupar por partner_id
        partner_groups = {}
        for order in orders_ok:
            pid = order.partner_id.id
            if pid not in partner_groups:
                partner_groups[pid] = self.env['pos.order']
            partner_groups[pid] += order

        created_moves = self.env['account.move']

        for partner_id, orders in partner_groups.items():
            base = orders[0]

            # Preparar vals base (partner, journal, fecha, etc.)
            move_vals = base._prepare_invoice_vals()

            # El tipo de documento sigue el signo del neto de todo el grupo
            # (misma semántica que pos.order._prepare_invoice_vals del core).
            amount_total = sum(orders.mapped('amount_total'))
            if base.currency_id.is_zero(amount_total):
                move_type = 'out_refund' if all(o.is_refund for o in orders) else 'out_invoice'
            else:
                move_type = 'out_invoice' if amount_total > 0.0 else 'out_refund'
            move_vals['move_type'] = move_type

            # Reemplazar líneas con las de todos los pedidos del grupo
            all_lines = []
            for order in orders:
                all_lines.extend(order._prepare_invoice_lines(move_type))
            move_vals['invoice_line_ids'] = all_lines

            # Referencia agrupada
            order_names = ', '.join(orders.mapped('name'))
            move_vals['ref'] = order_names
            move_vals['invoice_origin'] = order_names

            # Factura electrónica: cambiar al diario DIAN
            if ei:
                ei_journal = base.session_id.config_id.electronic_invoice_journal_id
                if not ei_journal:
                    raise UserError(_(
                        'El punto de venta "%s" no tiene configurado el '
                        'diario de factura electrónica.',
                        base.session_id.config_id.name,
                    ))
                move_vals['journal_id'] = ei_journal.id

            # Marcar las órdenes como facturables antes de crear
            orders.write({'to_invoice': True})

            # Crear y publicar la factura
            new_move = base._create_invoice(move_vals)
            orders.write({'account_move': new_move.id, 'state': 'invoiced'})
            new_move.sudo().with_company(base.company_id).with_context(
                skip_invoice_sync=True
            )._post()

            # Odoo 19 eliminó `_apply_invoice_payments`; el flujo actual (el
            # mismo del core `_generate_pos_order_invoice`) separa la creación
            # de los asientos de pago, la conciliación con la factura y la
            # reversión de los asientos de sesiones cerradas.
            all_payment_moves = self.env['account.move']
            payment_moves_from_closed_sessions = {}
            for order in orders:
                is_closed = order.session_id.state == 'closed'
                order_payments = order._get_payments()
                payment_moves = order_payments._create_payment_moves(is_closed)
                all_payment_moves |= payment_moves
                if is_closed:
                    payment_moves_from_closed_sessions[order] = payment_moves

            base._reconcile_invoice_payments(new_move, all_payment_moves)

            for order, payment_moves in payment_moves_from_closed_sessions.items():
                order._create_misc_reversal_move(payment_moves)

            created_moves += new_move

        if not created_moves:
            return {}

        return {
            'name': _('Facturas creadas'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_moves.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }

    # -------------------------------------------------------------------------
    # Acciones públicas (llamadas desde ir.actions.server)
    # -------------------------------------------------------------------------

    def action_pos_grouped_invoice(self):
        """Acción de servidor: factura agrupada normal."""
        return self._action_grouped_invoice_common(ei=False)

    def action_pos_grouped_ei_invoice(self):
        """Acción de servidor: factura agrupada electrónica (DIAN)."""
        return self._action_grouped_invoice_common(ei=True)
