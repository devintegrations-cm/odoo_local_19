# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Valores considerados "verdaderos" al leer el parámetro de sistema
# maintenance_management.enforce_checklist como texto.
_TRUE_VALUES = ('1', 'true', 'yes')


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    reference = fields.Char(
        string="Referencia",
        readonly=True,
        copy=False,
        help="Consecutivo interno de la incidencia/solicitud, asignado automáticamente.",
    )
    equipment_condition = fields.Selection(
        [
            ('good', 'Bueno'),
            ('regular', 'Regular'),
            ('bad', 'Malo'),
        ],
        string="Condición del equipo",
        tracking=True,
    )
    action_taken = fields.Text(
        string="Observaciones / Acciones realizadas",
    )
    cost_line_ids = fields.One2many(
        'maintenance.request.cost.line', 'request_id',
        string="Líneas de costo",
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
    )
    total_cost = fields.Monetary(
        string="Costo total",
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id',
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Orden de compra",
    )
    checklist_line_ids = fields.One2many(
        'maintenance.checklist.line', 'request_id',
        string="Checklist",
    )
    maintenance_location_id = fields.Many2one(
        'stock.warehouse',
        string="Ubicación del mantenimiento",
    )

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('cost_line_ids.amount')
    def _compute_total_cost(self):
        for request in self:
            request.total_cost = sum(request.cost_line_ids.mapped('amount'))

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange('equipment_id')
    def _onchange_equipment_id(self):
        for request in self:
            equipment = request.equipment_id
            if not equipment:
                continue
            if not request.maintenance_location_id:
                request.maintenance_location_id = equipment.warehouse_id

            if not request.checklist_line_ids and equipment.category_id:
                template = self.env['maintenance.checklist.template'].search(
                    [('category_id', '=', equipment.category_id.id)], limit=1)
                if template:
                    request.checklist_line_ids = [
                        (0, 0, {
                            'name': line.name,
                            'sequence': line.sequence,
                        })
                        for line in template.line_ids
                    ]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for request in requests:
            if not request.reference:
                request.reference = self.env['ir.sequence'].next_by_code(
                    'maintenance.management.incident') or _('Nuevo')
        return requests

    def write(self, vals):
        # Validamos ANTES de llamar a super() para evaluar el estado actual
        # de las líneas de checklist frente al cambio de etapa solicitado.
        if 'stage_id' in vals and vals.get('stage_id'):
            new_stage = self.env['maintenance.stage'].browse(vals['stage_id'])
            if new_stage.done:
                param = self.env['ir.config_parameter'].sudo().get_param(
                    'maintenance_management.enforce_checklist', default='True')
                enforce_checklist = str(param).strip().lower() in _TRUE_VALUES
                if enforce_checklist:
                    for request in self:
                        pending_lines = request.checklist_line_ids.filtered(
                            lambda line: not line.is_done)
                        if pending_lines:
                            raise UserError(_(
                                "No puede marcar como Realizado: el checklist de la "
                                "solicitud \"%s\" tiene ítems pendientes."
                            ) % (request.name or request.reference or request.id))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_bring_costs_from_po(self):
        """Copia las líneas de la orden de compra asociada como líneas de costo.

        TODO: traído por botón, no automático; se aísla este método para
        poder automatizarlo más adelante (por ejemplo al confirmar la OC
        o mediante un cron).
        """
        for request in self:
            if not request.purchase_order_id:
                continue
            new_lines = [
                (0, 0, {
                    'name': line.name,
                    'amount': line.price_subtotal,
                    'product_id': line.product_id.id,
                    'quantity': line.product_qty,
                    'purchase_line_id': line.id,
                })
                for line in request.purchase_order_id.order_line
            ]
            if new_lines:
                request.cost_line_ids = new_lines
        return True
