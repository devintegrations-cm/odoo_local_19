import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

# Prefijos del resumen de las actividades del vigía: también sirven para no
# repetir una alerta que ya está abierta.
STALL_SUMMARY = 'POS Inventory Queue: la cola no avanza'
INVOICE_SUMMARY = 'POS Inventory Queue: facturas del POS sin PDF'

QUEUE_MENU_PATH = 'Punto de Venta › Órdenes › Cola de Inventario'


class PosInventoryQueue(models.Model):
    """Vigía de la cola: detecta lo que hoy nadie ve.

    - La cola deja de avanzar (ítems en Pending/Processing más viejos que el
      umbral): despierta el cron de la cola y avisa a los gestores de
      inventario sobre el picking más viejo.
    - Facturas del POS sin PDF (el PDF se genera tras confirmar la venta y,
      si falla, queda para el cron de envío de Odoo): las encola en ese cron
      y, si siguen sin PDF al doble del umbral, avisa a los gestores de
      contabilidad sobre la factura más vieja.

    Los Failed Permanent ya tienen su alerta (_notify_permanent_failure).
    Si TODO el sistema de crons de Odoo está caído, el vigía tampoco corre:
    esa red la dan el cierre de caja (bloquea con pendientes) y el monitoreo
    del servidor.
    """

    _inherit = 'pos.inventory.queue'

    # -------------------------------------------------------------------------
    # NÚMEROS EN VIVO
    # -------------------------------------------------------------------------

    @api.model
    def _stall_alert_minutes(self):
        """Umbral en minutos (parámetro pos_inventory_queue.stall_alert_minutes,
        15 por defecto)."""
        value = self.env['ir.config_parameter'].sudo().get_param(
            'pos_inventory_queue.stall_alert_minutes', default='15')
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 15

    @api.model
    def _pos_invoices_without_pdf(self, older_than_minutes):
        """Facturas del POS publicadas en las últimas 24 h, más viejas que el
        umbral y sin PDF (sin adjunto invoice_pdf_report_file).

        La ventana de 24 h evita revisar el histórico en cada pasada.
        """
        self.env.cr.execute(
            """
                SELECT m.id
                  FROM account_move m
                 WHERE m.state = 'posted'
                   AND m.move_type IN ('out_invoice', 'out_refund')
                   AND m.create_date >= (now() AT TIME ZONE 'UTC') - interval '24 hours'
                   AND m.create_date <= (now() AT TIME ZONE 'UTC') - %s * interval '1 minute'
                   AND EXISTS (SELECT 1 FROM pos_order o WHERE o.account_move = m.id)
                   AND NOT EXISTS (
                        SELECT 1 FROM ir_attachment a
                         WHERE a.res_model = 'account.move'
                           AND a.res_id = m.id
                           AND a.res_field = 'invoice_pdf_report_file'
                   )
              ORDER BY m.create_date, m.id
            """,
            (older_than_minutes,),
        )
        return self.env['account.move'].sudo().browse(
            [row[0] for row in self.env.cr.fetchall()])

    @api.model
    def _get_queue_health(self):
        """Resumen de la cola para el vigía y la ventana de configuración."""
        Queue = self.sudo()
        now = fields.Datetime.now()
        waiting_domain = [('state', 'in', ('pending', 'processing'))]
        oldest = Queue.search(waiting_domain, order='create_date asc, id asc', limit=1)
        cron = self.env.ref(
            'pos_inventory_queue.ir_cron_process_pending_pos_inventory_queue',
            raise_if_not_found=False,
        )
        return {
            'pending': Queue.search_count([('state', '=', 'pending')]),
            'processing': Queue.search_count([('state', '=', 'processing')]),
            'oldest_item': oldest,
            'oldest_minutes': int((now - oldest.create_date).total_seconds() // 60) if oldest else 0,
            'done_last_hour': Queue.search_count([
                ('state', '=', 'done'),
                ('done_date', '>=', now - timedelta(hours=1)),
            ]),
            'failed': Queue.search_count([('state', '=', 'failed')]),
            'failed_permanent': Queue.search_count([('state', '=', 'failed_permanent')]),
            'invoices_without_pdf': len(self._pos_invoices_without_pdf(0)),
            'cron_active': bool(cron and cron.sudo().active),
            'cron_lastcall': cron.sudo().lastcall if cron else False,
        }

    # -------------------------------------------------------------------------
    # VIGÍA (ACCIÓN PLANIFICADA CADA 5 MINUTOS)
    # -------------------------------------------------------------------------

    @api.model
    def _cron_check_queue_health(self):
        """Revisa la cola y las facturas del POS; arregla lo que puede y avisa.

        Best-effort: un error del vigía se registra y no se propaga.
        """
        threshold = self._stall_alert_minutes()
        try:
            self._close_resolved_watch_activities()
        except Exception:
            _logger.exception('POS Queue: el vigía no pudo cerrar sus avisos resueltos')
        try:
            self._check_stalled_queue(threshold)
        except Exception:
            _logger.exception('POS Queue: el vigía no pudo revisar la cola')
        try:
            self._check_invoices_without_pdf(threshold)
        except Exception:
            _logger.exception('POS Queue: el vigía no pudo revisar las facturas')

    @api.model
    def _check_stalled_queue(self, threshold):
        health = self._get_queue_health()
        oldest = health['oldest_item']
        if not oldest or health['oldest_minutes'] < threshold:
            return False
        # Primero intenta destrabar solo, como el botón "Procesar ahora".
        self._trigger_processing()
        picking = oldest.picking_id
        if not picking:
            return False
        if health['cron_active']:
            lastcall = health['cron_lastcall']
            cron_state = _('activa; última ejecución: %s',
                           format_datetime(self.env, lastcall) if lastcall else _('nunca'))
        else:
            cron_state = _('DESACTIVADA')
        note = _(
            'La cola de inventario del POS no avanza: %(count)s ítem(s) esperando y el más '
            'viejo (%(item)s, picking %(picking)s) lleva %(minutes)s minutos sin procesarse '
            '(umbral: %(threshold)s min).\n'
            'Acción planificada "POS Inventory Queue: Process pending items": %(cron)s.\n'
            'Revisar en %(path)s y en Ajustes › Técnico › Acciones planificadas.',
            count=health['pending'] + health['processing'],
            item=oldest.name,
            picking=picking.name,
            minutes=health['oldest_minutes'],
            threshold=threshold,
            cron=cron_state,
            path=QUEUE_MENU_PATH,
        )
        _logger.warning('POS Queue: vigía, cola atascada: %s', note.replace('\n', ' '))
        return self._create_watch_activity(
            picking,
            'stock.group_stock_manager',
            '%s (%s)' % (STALL_SUMMARY, picking.name),
            note,
        )

    @api.model
    def _check_invoices_without_pdf(self, threshold):
        # 1. Encolar en el cron nativo de envío las que no tienen PDF y
        #    tampoco están ya en ese cron (p. ej. si el proceso murió entre
        #    confirmar la venta y generar el PDF).
        invoices = self._pos_invoices_without_pdf(threshold)
        to_enqueue = invoices.filtered(lambda m: not m.sending_data)
        for invoice in to_enqueue:
            invoice.sending_data = {
                'author_user_id': invoice.create_uid.id or self.env.user.id,
                'author_partner_id': (invoice.create_uid or self.env.user).partner_id.id,
            }
        if invoices:
            send_cron = self.env.ref('account.ir_cron_account_move_send', raise_if_not_found=False)
            if send_cron:
                send_cron.sudo()._trigger()
        # 2. Avisar solo si al doble del umbral siguen sin PDF: el cron de
        #    envío no las pudo completar.
        stuck = self._pos_invoices_without_pdf(threshold * 2)
        if not stuck:
            return False
        oldest = stuck[0]
        note = _(
            '%(count)s factura(s) del POS llevan más de %(minutes)s minutos sin PDF. La más '
            'vieja es %(invoice)s. Revisar que la acción planificada "Send invoices '
            'automatically" esté activa y el historial de la factura.',
            count=len(stuck),
            minutes=threshold * 2,
            invoice=oldest.name,
        )
        _logger.warning('POS Queue: vigía, facturas sin PDF: %s', note)
        return self._create_watch_activity(
            oldest,
            'account.group_account_manager',
            '%s (%s)' % (INVOICE_SUMMARY, oldest.name),
            note,
        )

    @api.model
    def _close_resolved_watch_activities(self):
        """Cierra los avisos del vigía cuyo problema ya se resolvió solo: el
        picking ya no tiene ítems esperando en la cola, o la factura ya tiene
        su PDF. Evita avisos abiertos sobre problemas que ya no existen."""
        Activity = self.env['mail.activity'].sudo()
        resolved = Activity
        for activity in Activity.search([
            ('res_model', '=', 'stock.picking'),
            ('summary', '=like', STALL_SUMMARY + '%'),
            ('active', '=', True),
        ]):
            waiting = self.sudo().search_count([
                ('picking_id', '=', activity.res_id),
                ('state', 'in', ('pending', 'processing')),
            ])
            if not waiting:
                resolved |= activity
        invoice_activities = Activity.search([
            ('res_model', '=', 'account.move'),
            ('summary', '=like', INVOICE_SUMMARY + '%'),
            ('active', '=', True),
        ])
        if invoice_activities:
            self.env.cr.execute(
                """
                    SELECT DISTINCT res_id FROM ir_attachment
                     WHERE res_model = 'account.move'
                       AND res_field = 'invoice_pdf_report_file'
                       AND res_id = ANY(%s)
                """,
                (invoice_activities.mapped('res_id'),),
            )
            with_pdf = {row[0] for row in self.env.cr.fetchall()}
            resolved |= invoice_activities.filtered(lambda a: a.res_id in with_pdf)
        if resolved:
            resolved.action_feedback(
                feedback=_('Resuelto automáticamente: el vigía verificó que ya no hace falta.'))
        return resolved

    @api.model
    def _create_watch_activity(self, record, group_xmlid, summary, note):
        """Actividad To Do automática para los usuarios internos del grupo en
        la compañía del registro. No repite: si un usuario ya tiene una
        actividad abierta con este mismo resumen en el registro, no se crea
        otra."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if not activity_type or not group:
            return False
        company = record.company_id or self.env.company
        users = self.env['res.users'].sudo().search([
            ('all_group_ids', 'in', group.id),
            ('company_ids', 'in', company.id),
            ('share', '=', False),
            ('active', '=', True),
        ])
        Activity = self.env['mail.activity'].sudo()
        already = Activity.search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('summary', '=', summary),
            ('active', '=', True),
        ]).mapped('user_id')
        users -= already
        if not users:
            return False
        return Activity.create([{
            'res_model_id': self.env['ir.model']._get_id(record._name),
            'res_id': record.id,
            'user_id': user.id,
            'activity_type_id': activity_type.id,
            'automated': True,
            'summary': summary,
            'note': note,
        } for user in users])
