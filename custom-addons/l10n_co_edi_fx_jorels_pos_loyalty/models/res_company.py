# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # JORELS-SEC-0001: Jorels (l10n_co_edi_jorels/models/config/res_company.py:72 y :96) define los tokens de
    # Edipo y Nimbus sin `groups`, y base da lectura de res.company a los usuarios portal: un proveedor del portal
    # podía leer el token por RPC y emitir documentos a nombre de la compañía. Jorels no se parchea; se redefine
    # el campo aquí (este módulo depende de l10n_co_edi_jorels).
    #
    # Por qué base.group_user y no base.group_system: en Odoo 19 la lectura en Python también revisa `groups`
    # (odoo/orm/fields.py:1643-1652, Field.__get__ sin sudo), y Jorels lee el token sin sudo con el usuario que
    # publica o valida la factura (account_move.py:1559-1561, 1736, 1816; res_partner.py:286; resolution.py:139;
    # nómina edi.py:313), igual que supplier_invoice_portal (account_move.py:207). Con group_system un contador
    # que no es administrador dejaría de enviar a la DIAN: con ei_always_validate (activo en producción) el error
    # se traga y la factura queda publicada sin CUFE. El POS publica con sudo y no se ve afectado.
    # El campo related de res.config.settings hereda estos groups (odoo/orm/fields.py:777).
    api_key = fields.Char(groups='base.group_user')
    nimbus_api_key = fields.Char(groups='base.group_user')
