# -*- coding: utf-8 -*-
from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_data_fields(self, config):
        # En 17 estos campos los cargaba l10n_co_edi_jorels_pos (_loader_params_res_partner);
        # Jorels 19 ya no los carga. El PaymentScreen de este módulo exige que el cliente
        # los tenga antes de facturar. Llegan como id entero (o False): los modelos
        # relacionados de Jorels no se cargan en el POS, solo se valida su presencia.
        params = super()._load_pos_data_fields(config)
        for fname in (
            'l10n_latam_identification_type_id',
            'type_regime_id',
            'type_liability_id',
            'municipality_id',
        ):
            if fname not in params:
                params.append(fname)
        return params
