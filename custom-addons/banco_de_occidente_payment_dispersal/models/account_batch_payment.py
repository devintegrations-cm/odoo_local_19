# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from datetime import datetime

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class AccountBatchPayment(models.Model):
    """
    Banco de Occidente-specific implementation for payment dispersal file generation.

    Generates TXT files with fixed-width format according to Banco de Occidente
    specifications.
    """
    _inherit = 'account.batch.payment'

    # -------------------------------------------------------------------------
    # HOOKS
    # -------------------------------------------------------------------------

    def _get_methods_generating_files(self):
        """Register Banco de Occidente method as file generator"""
        rslt = super()._get_methods_generating_files()
        rslt.append('banco_occidente_dispersion')
        return rslt

    def _generate_export_file(self):
        """Generate Banco de Occidente TXT export file"""
        self.ensure_one()

        if self.payment_method_code == 'banco_occidente_dispersion':
            return self._generate_banco_occidente_file()

        return super()._generate_export_file()

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------

    def check_payments_for_errors(self):
        """Validate Banco de Occidente-specific requirements"""
        rslt = super().check_payments_for_errors()

        if self.payment_method_code != 'banco_occidente_dispersion':
            return rslt

        # Get valid payment states
        valid_states = self._valid_payment_states()

        # Validate payment form
        no_payment_form = self.payment_ids.filtered(
            lambda p: p.state in valid_states and not p.bancodeoccidente_form_of_payment
        )
        if no_payment_form:
            rslt.append({
                'title': _("Missing Payment Form"),
                'records': no_payment_form,
                'help': _("Select the payment form (cheque, credit, cash) for each payment."),
            })

        # Validate account type
        no_account_type = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.partner_bank_id and
                not p.partner_bank_id.co_account_type
            )
        )
        if no_account_type:
            rslt.append({
                'title': _("Missing Account Type"),
                'records': no_account_type,
                'help': _("Configure the account type (Ahorros/Corriente) for beneficiary accounts."),
            })

        return rslt

    # -------------------------------------------------------------------------
    # FILE GENERATION
    # -------------------------------------------------------------------------

    def _generate_banco_occidente_file(self):
        """
        Generate Banco de Occidente TXT file.

        Returns:
            dict: File information dictionary
        """
        self.ensure_one()

        # Generate TXT content
        file_content = self._build_banco_occidente_txt()

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'BANCO_OCCIDENTE_{self.journal_id.code}_{timestamp}.txt'

        return {
            'file': base64.encodebytes(file_content.encode('utf-8')),
            'filename': filename,
        }

    def _build_banco_occidente_txt(self):
        """
        Build TXT file content for Banco de Occidente.

        File structure (fixed-width):
        - Line 1: Header (type 1)
        - Lines 2-N: Details (type 2) - one per payment
        - Last line: Footer (type 3)

        Returns:
            str: TXT file content with CRLF line endings
        """
        self.ensure_one()

        lines = []

        # Get field configuration
        field_configs = self.env['bancodeoccidente.payment_dispersal_field'].search(
            [], order='sequence asc'
        )

        if not field_configs:
            raise UserError(_(
                "No field configuration found for Banco de Occidente dispersal. "
                "Please contact your system administrator."
            ))

        payments = self.payment_ids.sorted(key=lambda r: r.id)

        # Calculate totals
        total_records = len(payments)
        total_amount = sum(payments.mapped('amount'))

        # Build header
        header = self._build_occidente_header(total_records, total_amount)
        lines.append(header)

        # Build detail lines
        errors = []
        for idx, payment in enumerate(payments, start=1):
            detail = self._build_occidente_detail(payment, idx, field_configs, errors)
            lines.append(detail)

        if errors:
            raise UserError(_(
                "Errors evaluating the Banco de Occidente dispersal fields:\n%s",
                '\n'.join(errors),
            ))

        # Build footer
        footer = self._build_occidente_footer(total_records, total_amount)
        lines.append(footer)

        # Join with CRLF (Windows line endings as per bank spec)
        return '\r\n'.join(lines)

    def _build_occidente_header(self, num_records, total_amount):
        """
        Build header record (type 1).

        Format (200 chars total):
        - Position 1: Record type ('1')
        - Position 2-5: Sequence (4 digits, zero-filled)
        - Position 6-13: Date (YYYYMMDD)
        - Position 14-17: Number of records (4 digits)
        - Position 18-35: Total value (18 digits, zero-filled, no decimals)
        - Position 36-51: Source account (16 digits, zero-filled)
        - Position 52-200: Spaces (149 chars)

        Args:
            num_records (int): Number of detail records
            total_amount (float): Total amount to disperse

        Returns:
            str: Header line
        """
        self.ensure_one()

        # Get source account
        source_account = self.journal_id.bank_account_id
        if not source_account:
            raise UserError(_(
                "The journal '%s' must have a bank account configured.",
                self.journal_id.name,
            ))

        parts = []

        # Record type
        parts.append('1')

        # Sequence (4 digits, currently 0000)
        parts.append(self._fill_left_zero('', 4))

        # Date (YYYYMMDD)
        parts.append(datetime.now().strftime('%Y%m%d'))

        # Number of records (4 digits)
        parts.append(self._fill_left_zero(num_records, 4))

        # Total value (18 digits, amount * 100 to remove decimals)
        amount_int = int(round(total_amount * 100))
        parts.append(self._fill_left_zero(amount_int, 18))

        # Source account (16 digits)
        acc_number = ''.join(filter(str.isdigit, source_account.acc_number or ''))
        parts.append(self._fill_left_zero(acc_number, 16))

        # Spaces (149 chars to complete 200)
        parts.append(self._fill_right_space('', 149))

        return ''.join(parts)

    def _build_occidente_detail(self, payment, row_number, field_configs, errors):
        """
        Build detail record (type 2).

        Format:
        - Position 1: Record type ('2')
        - Position 2-5: Row number (4 digits, zero-filled)
        - Positions 6+: Configured fields (variable positions)

        Args:
            payment (account.payment): Payment record
            row_number (int): Sequential row number
            field_configs (recordset): Field configuration records
            errors (list): Accumulator for field evaluation errors

        Returns:
            str: Detail line
        """
        parts = []

        # Record type
        parts.append('2')

        # Row number (4 digits)
        parts.append(self._fill_left_zero(row_number, 4))

        # Prepare evaluation context
        eval_context = self._get_occidente_eval_context()
        eval_context['object'] = payment

        # Process each configured field
        for field_config in field_configs:
            try:
                # Execute field value code
                eval_context['result'] = ''
                safe_eval(field_config.value, eval_context, mode='exec')
                result = eval_context.get('result')
            except Exception as e:
                _logger.error(
                    "Error evaluating field '%s' for payment %s: %s",
                    field_config.name, payment.name, e,
                )
                errors.append(f"- {field_config.name} / {payment.name}: {e}")
                result = None

            if isinstance(result, float):
                # Remove decimals for amounts
                result = int(round(result * 100))
            result_str = '' if result is None or result is False else str(result)

            # Apply formatting (spaces by default to keep positions fixed)
            max_length = field_config.max_length or len(result_str)
            if field_config.fill_with_zeros:
                parts.append(self._fill_left_zero(result_str, max_length))
            else:
                parts.append(self._fill_right_space(result_str, max_length))

        # TODO: validar con manual del banco. The default configuration sums
        # 199 positions (5 fixed + 194 configured); pad to the 200 of the spec.
        return ''.join(parts).ljust(200)

    def _build_occidente_footer(self, num_records, total_amount):
        """
        Build footer record (type 3).

        Format (200 chars total):
        - Position 1: Record type ('3')
        - Position 2-5: Code '9999'
        - Position 6-9: Number of records (4 digits)
        - Position 10-27: Total value (18 digits)
        - Position 28-200: Spaces (173 chars)

        Args:
            num_records (int): Number of detail records
            total_amount (float): Total amount dispersed

        Returns:
            str: Footer line
        """
        parts = []

        # Record type
        parts.append('3')

        # Code
        parts.append('9999')

        # Number of records (4 digits)
        parts.append(self._fill_left_zero(num_records, 4))

        # Total value (18 digits)
        amount_int = int(round(total_amount * 100))
        parts.append(self._fill_left_zero(amount_int, 18))

        # Spaces (173 chars to complete 200)
        parts.append(self._fill_right_space('', 173))

        return ''.join(parts)

    def _get_occidente_eval_context(self):
        """
        Get evaluation context for safe_eval.

        Returns:
            dict: Context dictionary
        """
        from datetime import date, datetime, timedelta, time

        return {
            'env': self.env,
            'date': date,
            'datetime': datetime,
            'timedelta': timedelta,
            'time': time,
            # 'object' will be set per payment
        }

    # -------------------------------------------------------------------------
    # FORMATTING HELPERS
    # -------------------------------------------------------------------------

    def _fill_left_zero(self, value, length):
        """
        Fill with zeros on the left to reach specified length.

        Args:
            value: Value to format (will be converted to string)
            length (int): Desired length

        Returns:
            str: Zero-filled string

        Example:
            _fill_left_zero(123, 6) -> '000123'
        """
        return str(value).zfill(length)[-length:]

    def _fill_right_space(self, value, length):
        """
        Fill with spaces on the right to reach specified length.

        Args:
            value: Value to format (will be converted to string)
            length (int): Desired length

        Returns:
            str: Space-filled string

        Example:
            _fill_right_space('ABC', 6) -> 'ABC   '
        """
        return str(value).ljust(length)[:length]

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_generate_banco_occidente(self):
        """Action: Generate Banco de Occidente dispersal file"""
        return self.validate_batch()
