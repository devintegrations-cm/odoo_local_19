# -*- coding: utf-8 -*-
import base64
import logging
import unicodedata

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Palabras vacías del español que se ignoran al construir el serial por
# defecto (artículos y preposiciones cortas que no aportan al identificador).
_SERIAL_STOPWORDS = {
    'de', 'del', 'la', 'las', 'el', 'los', 'en', 'y', 'a', 'para', 'con',
    'un', 'una', 'unos', 'unas',
}


class MaintenanceEquipment(models.Model):
    # Heredamos el modelo de equipos de mantenimiento y le añadimos
    # portal.mixin (access_url / access_token / get_portal_url) para poder
    # publicar la "hoja de vida" del equipo en el portal, junto con un QR.
    _name = 'maintenance.equipment'
    _inherit = ['maintenance.equipment', 'portal.mixin']

    asset_number = fields.Char(
        string="Número de Activo",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Consecutivo interno del activo, asignado automáticamente al crear el equipo.",
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string="Almacén/Tienda",
        tracking=True,
    )
    customer_id = fields.Many2one(
        'res.partner',
        string="Cliente",
        tracking=True,
    )
    qr_image = fields.Binary(
        string="Código QR",
        compute='_compute_qr_image',
        help="Código QR que enlaza a la hoja de vida del equipo en el portal.",
    )
    qr_filename = fields.Char(
        string="Nombre de archivo QR",
        compute='_compute_qr_filename',
        help="Nombre sugerido del archivo PNG al descargar el código QR.",
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        related='company_id.currency_id',
    )
    maintenance_total_cost = fields.Monetary(
        string="Costo total mantenimientos",
        compute='_compute_maintenance_total_cost',
        currency_field='company_currency_id',
        help="Suma del costo total de todas las solicitudes de mantenimiento del equipo.",
    )

    _asset_number_unique = models.Constraint(
        'unique(asset_number)',
        'Ya existe un equipo con este número de activo.',
    )

    # ------------------------------------------------------------------
    # Portal / QR
    # ------------------------------------------------------------------
    def _compute_access_url(self):
        super()._compute_access_url()
        for equipment in self:
            equipment.access_url = '/my/equipment/%s' % equipment.id

    def _get_qr_url(self):
        """URL absoluta (con token si existe) que se codifica en el QR."""
        self.ensure_one()
        url = '%s/my/equipment/%s' % (self.get_base_url(), self.id)
        if self.access_token:
            url += '?access_token=%s' % self.access_token
        return url

    @api.depends('access_token')
    def _compute_qr_image(self):
        # No se escribe en BD dentro de este compute: la imagen se genera al
        # vuelo a partir de la URL del portal.
        Report = self.env['ir.actions.report']
        for equipment in self:
            equipment.qr_image = False
            if not equipment.id:
                continue
            try:
                png = Report.barcode('QR', equipment._get_qr_url(), width=256, height=256)
                equipment.qr_image = base64.b64encode(png)
            except Exception as error:  # noqa: BLE001
                _logger.warning(
                    "No se pudo generar el QR para el equipo %s: %s", equipment.id, error)

    @api.depends('asset_number', 'name')
    def _compute_qr_filename(self):
        for equipment in self:
            base = equipment.asset_number or equipment.name or ('equipo_%s' % (equipment.id or 'nuevo'))
            # Normaliza para un nombre de archivo limpio (sin espacios ni tildes).
            normalized = unicodedata.normalize('NFKD', base)
            ascii_base = ''.join(char for char in normalized if not unicodedata.combining(char))
            safe = ''.join(char if char.isalnum() else '_' for char in ascii_base)
            equipment.qr_filename = 'QR_%s.png' % (safe or 'equipo')

    # ------------------------------------------------------------------
    # Costos
    # ------------------------------------------------------------------
    @api.depends('maintenance_ids.total_cost')
    def _compute_maintenance_total_cost(self):
        for equipment in self:
            equipment.maintenance_total_cost = sum(
                equipment.maintenance_ids.mapped('total_cost'))

    # ------------------------------------------------------------------
    # Código de tienda / serial por defecto
    # ------------------------------------------------------------------
    def _get_store_code(self):
        """Devuelve el código de tienda usado para construir el serial.

        TODO: Supuesto: código de tienda = stock.warehouse.code. Se centraliza
        aquí este criterio para poder cambiarlo fácilmente si la regla de
        negocio cambia (por ejemplo, un código de tienda propio del cliente).
        """
        self.ensure_one()
        return self.warehouse_id.code or ''

    def _compute_or_default_serial(self):
        """Genera un número de serie por defecto para el equipo.

        Regla por defecto (configurable a futuro vía el parámetro de sistema
        ``maintenance_management.serial_pattern``): 3 primeras letras de las
        2 primeras palabras "significativas" del nombre (mayúsculas, sin
        tildes) + código de tienda (``_get_store_code``) + fecha de registro
        en formato AAAAMMDD.

        Ejemplo: "Nevera de cocina" en la tienda ZNG2, registrada el
        2025-05-08 -> ``NEVCOCZNG220250508``.

        TODO: regla exacta por confirmar con el negocio; el patrón es
        configurable vía el parámetro de sistema
        ``maintenance_management.serial_pattern`` (actualmente solo
        informativo, la lógica activa está codificada aquí).
        """
        self.ensure_one()
        # TODO: leer y aplicar variantes de patrón desde
        # ir.config_parameter cuando se definan más de una regla.
        self.env['ir.config_parameter'].sudo().get_param(
            'maintenance_management.serial_pattern', default='default')

        name = self.name or ''
        normalized = unicodedata.normalize('NFKD', name)
        ascii_name = ''.join(char for char in normalized if not unicodedata.combining(char))

        words = [word for word in ascii_name.split() if word.lower() not in _SERIAL_STOPWORDS]
        if not words:
            words = ascii_name.split()

        prefix = ''.join(word.upper()[:3] for word in words[:2])
        store_code = self._get_store_code()
        reference_date = self.create_date or fields.Datetime.now()
        date_part = reference_date.strftime('%Y%m%d')
        return '%s%s%s' % (prefix, store_code, date_part)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        equipments = super().create(vals_list)
        for equipment in equipments:
            if not equipment.asset_number:
                equipment.asset_number = self.env['ir.sequence'].next_by_code(
                    'maintenance.management.asset') or _('Nuevo')
            equipment._portal_ensure_token()
            if not equipment.serial_no:
                equipment.serial_no = equipment._compute_or_default_serial()
        return equipments

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_print_qr_label(self):
        for equipment in self:
            equipment._portal_ensure_token()
        return self.env.ref(
            'maintenance_management.action_report_equipment_qr'
        ).report_action(self)

    def action_download_qr(self):
        """Descarga la imagen del código QR como archivo PNG.

        Asegura primero el token de portal (para que la URL del QR sea válida)
        y devuelve una URL a ``/web/content`` con ``download=true``, que sirve
        el campo binario computado ``qr_image`` como adjunto descargable.
        """
        self.ensure_one()
        self._portal_ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content?model=maintenance.equipment&id=%s'
                '&field=qr_image&filename_field=qr_filename'
                '&download=true&mimetype=image/png' % self.id
            ),
            'target': 'self',
        }

    def action_view_hoja_vida(self):
        """Abre la hoja de vida del equipo publicada en el portal."""
        self.ensure_one()
        self._portal_ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'url': self.get_portal_url(),
            'target': 'self',
        }

    def action_backfill_asset_data(self):
        """Asigna número de activo, token de portal (QR) y serial por defecto.

        Pensada para completar registros que aún no tienen estos datos: por
        ejemplo, equipos creados antes de instalar el módulo, o para asignar en
        lote la información generada. Se ejecuta desde una acción de servidor
        (menú "Acción"), no desde un compute, respetando la buena práctica de
        no escribir en BD dentro de computes de solo lectura.

        Es idempotente: solo rellena lo que falte, por lo que puede ejecutarse
        varias veces sin efectos colaterales.
        """
        for equipment in self:
            if not equipment.asset_number:
                equipment.asset_number = self.env['ir.sequence'].next_by_code(
                    'maintenance.management.asset') or _('Nuevo')
            # Asegura access_token para que funcione el QR / la hoja de vida.
            equipment._portal_ensure_token()
            if not equipment.serial_no:
                equipment.serial_no = equipment._compute_or_default_serial()
        return True

    def action_view_maintenance_costs(self):
        """Smart button: abre las solicitudes de mantenimiento del equipo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mantenimientos'),
            'res_model': 'maintenance.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.maintenance_ids.ids)],
            'context': {'default_equipment_id': self.id},
        }
