# -*- coding: utf-8 -*-
from odoo import api, models


class ClaraSyncMixin(models.AbstractModel):
    _name = "clara.sync.mixin"
    _description = "Clara Sync Engine Mixin"

    @api.model
    def _create_sync_log(self, sync_type, triggered_by):
        return self.env["clara.sync.log"].create({"sync_type": sync_type, "triggered_by": triggered_by, "state": "running"})

    @api.model
    def _get_api_service(self):
        from ..services.clara_api_service import ClaraAPIService
        return ClaraAPIService(self.env)
