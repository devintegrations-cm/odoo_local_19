# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartnerBank(models.Model):
    """
    Extension of res.partner.bank for Colombian bank accounts.

    Adds Colombian-specific fields like account type (Ahorros/Corriente)
    which are required for payment dispersal files.
    """
    _inherit = 'res.partner.bank'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    co_account_type = fields.Selection(
        selection=[
            ('savings_account', 'Cuenta de Ahorros'),
            ('current_account', 'Cuenta Corriente'),
        ],
        string='Tipo de Cuenta (Colombia)',
        help='Tipo de cuenta bancaria para archivos de dispersión colombianos'
    )

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------

    @api.constrains('acc_number')
    def _check_acc_number_colombia(self):
        """
        Validate Colombian bank account numbers.

        Colombian account numbers typically have 10-16 digits.
        """
        for bank_account in self:
            # Only validate Colombian banks
            if (bank_account.bank_id and
                bank_account.bank_id.country and
                bank_account.bank_id.country.code == 'CO' and
                bank_account.acc_number):

                # sanitized_acc_number (campo nativo de Odoo) quita espacios,
                # guiones y cualquier carácter no alfanumérico, incluidos
                # espacios invisibles como el NBSP (\xa0) que terminaron 38
                # cuentas reales: con replace(' ','') esas cuentas no se
                # volvían a guardar.
                acc_clean = bank_account.sanitized_acc_number or ''

                # Check if it's numeric
                if not acc_clean.isdigit():
                    raise ValidationError(_(
                        "Los números de cuenta bancaria colombianos deben contener solo dígitos. "
                        "Cuenta: %s",
                        bank_account.acc_number,
                    ))

                # Check length (typical range 10-16 digits). En el log nunca
                # el número completo: es un dato sensible.
                if not (10 <= len(acc_clean) <= 16):
                    _logger.warning(
                        "Bank account ...%s has unusual length %d (expected 10-16 digits)",
                        acc_clean[-4:],
                        len(acc_clean)
                    )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def get_account_type_display(self):
        """
        Get human-readable account type.

        Returns:
            str: Display name of account type
        """
        self.ensure_one()

        if not self.co_account_type:
            return ''

        types = dict(self._fields['co_account_type'].selection)
        return types.get(self.co_account_type, '')