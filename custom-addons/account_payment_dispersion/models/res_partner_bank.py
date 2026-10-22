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

                # Remove spaces and dashes
                acc_clean = bank_account.acc_number.replace(' ', '').replace('-', '')

                # Check if it's numeric
                if not acc_clean.isdigit():
                    raise ValidationError(_(
                        "Los números de cuenta bancaria colombianos deben contener solo dígitos. "
                        "Cuenta: %s",
                        bank_account.acc_number,
                    ))

                # Check length (typical range 10-16 digits)
                if not (10 <= len(acc_clean) <= 16):
                    _logger.warning(
                        "Bank account %s has unusual length %d (expected 10-16 digits)",
                        bank_account.acc_number,
                        len(acc_clean)
                    )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def get_account_type_code(self, bank_code='generic'):
        """
        Get the account type code for a specific bank format.

        Args:
            bank_code (str): Bank code (e.g., 'bancolombia', 'banco_occidente')

        Returns:
            str: Account type code for the specified bank
        """
        self.ensure_one()

        if not self.co_account_type:
            return ''

        # Mapping for different banks
        mappings = {
            'bancolombia': {
                'savings_account': 'S',
                'current_account': 'D',  # "D" for "Depósito"
            },
            'banco_occidente': {
                'savings_account': 'A',
                'current_account': 'C',
            },
            'generic': {
                'savings_account': 'S',
                'current_account': 'C',
            },
        }

        bank_mapping = mappings.get(bank_code, mappings['generic'])
        return bank_mapping.get(self.co_account_type, '')

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