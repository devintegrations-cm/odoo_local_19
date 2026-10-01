from odoo import _, api, models, fields
from odoo.tools.misc import format_datetime
from odoo.tools.misc import str2bool


class PosInventoryQueueConfig(models.TransientModel):
    _name = 'pos.inventory.queue.config'
    _description = 'POS Inventory Queue Configuration'

    pos_inventory_queue_enabled = fields.Boolean(
        string="POS Inventory Queue",
        default=True,
        help="Interruptor GLOBAL de la cola de inventario del POS.",
    )

    # Resumen en vivo de la cola (solo lectura, se calcula al abrir).
    health_pending = fields.Integer('Pendientes', compute='_compute_health')
    health_oldest_minutes = fields.Integer(
        'Pendiente más viejo (min)', compute='_compute_health',
        help='Minutos que lleva esperando el ítem Pending/Processing más viejo. '
             'Si supera el umbral del vigía '
             '(pos_inventory_queue.stall_alert_minutes, 15 por defecto) se avisa '
             'a los gestores de inventario.')
    health_done_last_hour = fields.Integer('Procesados en la última hora', compute='_compute_health')
    health_failed = fields.Integer('Fallidos (se reintentan)', compute='_compute_health')
    health_failed_permanent = fields.Integer('Fallidos permanentes', compute='_compute_health')
    health_invoices_without_pdf = fields.Integer(
        'Facturas del POS sin PDF (24 h)', compute='_compute_health')
    health_cron = fields.Char('Acción planificada de la cola', compute='_compute_health')

    @api.depends()
    def _compute_health(self):
        health = self.env['pos.inventory.queue']._get_queue_health()
        if health['cron_active']:
            lastcall = health['cron_lastcall']
            cron = _('Activa, última ejecución: %s',
                     format_datetime(self.env, lastcall) if lastcall else _('nunca'))
        else:
            cron = _('DESACTIVADA: la cola no se procesa')
        for wizard in self:
            wizard.health_pending = health['pending'] + health['processing']
            wizard.health_oldest_minutes = health['oldest_minutes']
            wizard.health_done_last_hour = health['done_last_hour']
            wizard.health_failed = health['failed']
            wizard.health_failed_permanent = health['failed_permanent']
            wizard.health_invoices_without_pdf = health['invoices_without_pdf']
            wizard.health_cron = cron

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'pos_inventory_queue_enabled' in fields_list:
            res['pos_inventory_queue_enabled'] = str2bool(
                self.env['ir.config_parameter'].sudo().get_param(
                    'pos_inventory_queue.enabled', default='True'),
                default=True,
            )
        return res

    def write(self, vals):
        res = super().write(vals)
        if 'pos_inventory_queue_enabled' in vals:
            ICP = self.env['ir.config_parameter'].sudo()
            value = 'True' if self.pos_inventory_queue_enabled else 'False'
            row = ICP.search(
                [('key', '=', 'pos_inventory_queue.enabled')], limit=1)
            if row:
                row.value = value
            else:
                ICP.set_param('pos_inventory_queue.enabled', value)
        return res

    def action_save(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        value = 'True' if self.pos_inventory_queue_enabled else 'False'
        row = ICP.search(
            [('key', '=', 'pos_inventory_queue.enabled')], limit=1)
        if row:
            row.value = value
        else:
            ICP.set_param('pos_inventory_queue.enabled', value)
        return {'type': 'ir.actions.act_window_close'}
