# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_customer_id = fields.Many2one('res.partner', string='Default Customer')

    def get_limited_partners_loading(self, offset=0):
        """Garantiza que el cliente por defecto viaje al POS.

        `res.partner._load_pos_data_domain` (point_of_sale/models/res_partner.py:59)
        carga solo los partners que devuelve este metodo, y son los N mas usados.
        Si el cliente por defecto no entra en esa lista, el store relacional no
        puede resolverlo y el pedido nuevo quedaria sin cliente.

        Mismo patron que l10n_es_pos, l10n_ar_pos y l10n_pe_pos: la lista son
        tuplas de un elemento porque viene de `env.execute_query`.
        """
        partner_ids = super().get_limited_partners_loading(offset)
        for config in self:
            partner = config.pos_customer_id
            if partner and (partner.id,) not in partner_ids:
                partner_ids.append((partner.id,))
        return partner_ids


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # El nombre se mantiene igual que en la version 17 a proposito.
    # `point_of_sale/models/res_config_settings.py:170` toma todo campo que
    # empiece con `pos_`, le corta ese prefijo y lo escribe en
    # `pos_config_id.<resto>`: aca eso apunta a `pos.config.customer_id`, que no
    # existe, asi que al guardar los ajustes aparece un WARNING
    #   "The value of 'pos_customer_id' is not properly saved..."
    # El aviso es enganoso: el valor SI se guarda, por la via del campo related
    # (verificado en cr19_pdc). Renombrar el campo para acallarlo no es trivial:
    # `default_*`, `group_*` y `module_*` estan reservados por
    # `res.config.settings._get_classified_fields`, y cualquier otro nombre con
    # prefijo `pos_` reproduce el mismo aviso. La alternativa real es renombrar
    # `pos.config.pos_customer_id` -> `pos.config.customer_id`, que exige script
    # de migracion de columna. Queda anotado, no se toca en esta migracion.
    pos_customer_id = fields.Many2one(
        'res.partner',
        string='Default Customer',
        related='pos_config_id.pos_customer_id',
        readonly=False,
    )
