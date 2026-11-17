# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ClaraSyncLog(models.Model):
    _name = "clara.sync.log"
    _description = "Registro de sincronización con Clara"
    _order = "started_at desc, id desc"

    name = fields.Char("Nombre", default="New", required=True)
    sync_type = fields.Selection([("transactions", "Transacciones"), ("cards", "Tarjetas")], string="Qué se sincronizó", required=True)
    state = fields.Selection([("running", "En curso"), ("success", "Correcta"), ("partial", "Con errores"), ("failed", "Fallida")], string="Estado", default="running", required=True)
    started_at = fields.Datetime("Inicio", default=fields.Datetime.now)
    finished_at = fields.Datetime("Fin")
    duration = fields.Float("Duración (s)", compute="_compute_duration")
    records_fetched = fields.Integer("Leídos de Clara", default=0)
    records_created = fields.Integer("Creados", default=0)
    records_updated = fields.Integer("Actualizados", default=0)
    records_skipped = fields.Integer("Sin cambios", default=0)
    records_errored = fields.Integer("Con error", default=0)
    api_calls = fields.Integer("Llamadas a la API", default=0)
    error_message = fields.Text("Mensaje de error")
    triggered_by = fields.Selection([("cron", "Acción planificada"), ("manual", "Sincronizar ahora")], string="Origen", default="manual")

    @api.depends("started_at", "finished_at")
    def _compute_duration(self):
        for log in self:
            log.duration = (log.finished_at - log.started_at).total_seconds() if log.started_at and log.finished_at else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                sync_type = dict(self._fields["sync_type"].selection).get(vals.get("sync_type"), "Sync")
                vals["name"] = f"{sync_type} - {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return super().create(vals_list)
