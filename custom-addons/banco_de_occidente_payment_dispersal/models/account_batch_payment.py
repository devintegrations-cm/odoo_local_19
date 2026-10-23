# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from datetime import datetime

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Campo de la cuenta destino en la configuración del archivo. Sus valores son
# identificadores (números de cuenta): un corte silencioso haría que el banco
# recibiera OTRA cuenta en una línea bien formada, así que el desborde es
# error, no truncado (los xmlids son estables: la configuración es noupdate).
TARGET_ACCOUNT_FIELD_XMLID = (
    'banco_de_occidente_payment_dispersal.'
    'bancodeoccidente_payment_dispersal_field_target_financial_institution'
)

# Ancho de línea del formato del banco: el mismo que genera el código de la
# v17 (199 posiciones). La comparación contra un archivo histórico real se
# hace en STG (golden file).
LINE_WIDTH = 199


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
            str: TXT file content con LF y terminando en LF después del pie
            (mismo formato que el generador de la v17: cada línea terminaba
            en LF)
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

        # Campo de cuenta destino: se resuelve una sola vez (no por pago).
        target_account_field = self.env.ref(
            TARGET_ACCOUNT_FIELD_XMLID, raise_if_not_found=False
        )

        # Calculate totals
        total_records = len(payments)
        total_amount = sum(payments.mapped('amount'))

        # Build header
        header = self._build_occidente_header(total_records, total_amount)
        lines.append(header)

        # Build detail lines
        errors = []
        for idx, payment in enumerate(payments, start=1):
            detail = self._build_occidente_detail(
                payment, idx, field_configs, errors, target_account_field,
            )
            lines.append(detail)

        if errors:
            raise UserError(_(
                "Errors evaluating the Banco de Occidente dispersal fields:\n%s",
                '\n'.join(errors),
            ))

        # Build footer
        footer = self._build_occidente_footer(total_records, total_amount)
        lines.append(footer)

        # Paridad con la v17: LF, no CRLF. La v17 escribía cada línea con
        # '\n', así que el archivo terminaba en LF también después del pie:
        # hay portales bancarios que rechazan el archivo o pierden la última
        # línea si falta ese byte final.
        return '\n'.join(lines) + '\n'

    def _build_occidente_header(self, num_records, total_amount):
        """
        Build header record (type 1).

        Format (199 chars total, como la v17):
        - Position 1: Record type ('1')
        - Position 2-5: Sequence (4 digits, zero-filled)
        - Position 6-13: Date (YYYYMMDD)
        - Position 14-17: Number of records (4 digits)
        - Position 18-35: Total value (18 digits, zero-filled, no decimals)
        - Position 36-51: Source account (16 digits, zero-filled)
        - Position 52-199: Zeros (148 chars)

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

        # Source account (16 digits). Como en la v17: zfill sin limpiar y sin
        # cortar — una cuenta más larga genera error explícito en vez de una
        # línea alargada que el banco rechazaría sin explicación.
        acc_number = source_account.acc_number or ''
        if len(acc_number) > 16:
            raise UserError(_(
                "The source account number '%(account)s' of journal '%(journal)s' "
                "exceeds 16 characters and cannot be included in the dispersal "
                "file.",
                account=acc_number, journal=self.journal_id.name,
            ))
        parts.append(str(acc_number).zfill(16))

        # Zeros (148 chars to complete 199)
        parts.append(self._fill_left_zero('', 148))

        return ''.join(parts)

    def _build_occidente_detail(self, payment, row_number, field_configs, errors,
                                target_account_field):
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
            target_account_field: registro de la cuenta destino (resuelto
                una vez en _build_banco_occidente_txt); None si no existe

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

            max_length = field_config.max_length or len(result_str)
            # O4: los campos identificadores NO se cortan en silencio. Un
            # número de cuenta o un documento truncado entregaría OTRO dato en
            # una línea bien formada (el banco lo pagaría sin rechazar nada);
            # en la v17 el valor alargaba la línea y el archivo se caía entero.
            # El desborde es error y sale con todos los demás en el UserError.
            is_identifier = (
                field_config.fill_with_zeros
                or (target_account_field and field_config == target_account_field)
            )
            if is_identifier and len(result_str) > max_length:
                errors.append(_(
                    "- %(field)s / %(payment)s: the value '%(value)s' has "
                    "%(actual)d characters but the field allows %(max)d; "
                    "identifier fields are not truncated to avoid altering "
                    "the data",
                    field=field_config.name, payment=payment.name,
                    value=result_str, actual=len(result_str), max=max_length,
                ))

            # Apply formatting (spaces by default to keep positions fixed)
            if field_config.fill_with_zeros:
                parts.append(self._fill_left_zero(result_str, max_length))
            else:
                parts.append(self._fill_right_space(result_str, max_length))

        line = ''.join(parts)
        # El formato del banco es fijo: 5 posiciones fijas + las configuradas
        # = 199 (mismo ancho que el generador de la v17; la comparación con un
        # archivo histórico real se hace en STG). El control cuenta CARACTERES,
        # igual que la v17: un acento agrega bytes al codificar en UTF-8 pero
        # no posiciones, y los archivos con tildes fueron aceptados.
        # Si la configuración produce otro ancho, falla explícito antes de
        # entregar un archivo que el banco rechazaría.
        if len(line) != LINE_WIDTH:
            errors.append(_(
                "- %(payment)s: the detail line has %(actual)d positions and "
                "the bank format requires %(expected)d",
                payment=payment.name, actual=len(line), expected=LINE_WIDTH,
            ))
        return line

    def _build_occidente_footer(self, num_records, total_amount):
        """
        Build footer record (type 3).

        Format (199 chars total, como la v17):
        - Position 1: Record type ('3')
        - Position 2-5: Code '9999'
        - Position 6-9: Number of records (4 digits)
        - Position 10-27: Total value (18 digits)
        - Position 28-199: Zeros (172 chars)

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

        # Zeros (172 chars to complete 199)
        parts.append(self._fill_left_zero('', 172))

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
