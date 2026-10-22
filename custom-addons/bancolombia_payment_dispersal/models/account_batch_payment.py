# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class AccountBatchPayment(models.Model):
    """
    Bancolombia-specific implementation for payment dispersal file generation.

    Generates Excel files with Bancolombia's required format for payment dispersals.
    """
    _inherit = 'account.batch.payment'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    bancolombia_payment_type = fields.Selection(
        selection=[
            ('220', 'Proveedores (220)'),
            ('225', 'Nómina (225)'),
        ],
        string='Tipo de Dispersión (Bancolombia)',
        compute='_compute_bancolombia_payment_type',
        store=True,
        readonly=True,
        help='Se toma del tipo de dispersión de los pagos del lote (220 proveedores / 225 nómina).'
    )

    @api.depends('payment_ids.bancolombia_payment_type', 'payment_method_code')
    def _compute_bancolombia_payment_type(self):
        for batch in self:
            if batch.payment_method_code != 'bancolombia_dispersion':
                batch.bancolombia_payment_type = False
                continue
            types = [ptype for ptype in batch.payment_ids.mapped('bancolombia_payment_type') if ptype]
            batch.bancolombia_payment_type = types[0] if types else False

    def _get_dispersion_payment_domain(self):
        domain = super()._get_dispersion_payment_domain()
        if self.payment_method_code == 'bancolombia_dispersion' and self.payment_ids:
            domain.append((
                'bancolombia_payment_type',
                '=',
                self.payment_ids[0].bancolombia_payment_type,
            ))
        return domain

    # -------------------------------------------------------------------------
    # HOOKS
    # -------------------------------------------------------------------------

    def _get_methods_generating_files(self):
        """Register Bancolombia method as file generator"""
        rslt = super()._get_methods_generating_files()
        rslt.append('bancolombia_dispersion')
        return rslt

    def _generate_export_file(self):
        """Generate Bancolombia Excel export file"""
        self.ensure_one()

        if self.payment_method_code == 'bancolombia_dispersion':
            return self._generate_bancolombia_file()

        return super()._generate_export_file()

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------

    def check_payments_for_errors(self):
        """Validate Bancolombia-specific requirements"""
        rslt = super().check_payments_for_errors()

        if self.payment_method_code != 'bancolombia_dispersion':
            return rslt

        # Get valid payment states
        valid_states = self._valid_payment_states()

        # Validate transaction type
        no_transaction_type = self.payment_ids.filtered(
            lambda p: p.state in valid_states and not p.bancolombia_type_of_transaction
        )
        if no_transaction_type:
            rslt.append({
                'title': _("Falta Tipo de Transacción"),
                'records': no_transaction_type,
                'help': _("Seleccione el tipo de transacción Bancolombia para cada pago."),
            })

        # Validate bank account for non-cash transactions
        cash_types = ['25', '36', '40']  # Cash payment types
        need_bank_account = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.bancolombia_type_of_transaction not in cash_types and
                not p.partner_bank_id
            )
        )
        if need_bank_account:
            rslt.append({
                'title': _("Falta Cuenta Bancaria"),
                'records': need_bank_account,
                'help': _("La cuenta bancaria es requerida para tipos de transacción no-efectivo."),
            })

        # Validate bank code for non-cash transactions
        need_bank_code = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.bancolombia_type_of_transaction not in cash_types and
                p.partner_bank_id and
                (not p.partner_bank_id.bank_id or not p.partner_bank_id.bank_id.dispersal_code)
            )
        )
        if need_bank_code:
            rslt.append({
                'title': _("Falta Código de Banco"),
                'records': need_bank_code,
                'help': _("Configure el código de dispersión del banco del beneficiario en los datos maestros del banco."),
            })

        # Validate document type for cash transactions (25, 36)
        cash_transaction_types = ['25', '36']
        need_doc_type = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.bancolombia_type_of_transaction in cash_transaction_types and
                not p.partner_id.l10n_latam_identification_type_id
            )
        )
        if need_doc_type:
            rslt.append({
                'title': _("Falta Tipo de Documento del Beneficiario"),
                'records': need_doc_type,
                'help': _("El tipo de documento es obligatorio para transacciones de pago en efectivo (25) y cheque de gerencia (36)."),
            })

        # Validate authorized document for transaction type 36 (Manager's Check)
        need_authorized_doc = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.bancolombia_type_of_transaction == '36' and
                not p.memo
            )
        )
        if need_authorized_doc:
            rslt.append({
                'title': _("Falta Documento del Autorizado"),
                'records': need_authorized_doc,
                'help': _("El documento del autorizado es obligatorio para el tipo de transacción 'Pago con Cheque de Gerencia' (36). Configure la referencia del pago."),
            })

        # Validate beneficiary mobile for transaction type 25 (Cash Payment)
        # Only if company is affiliated to correspondent banking
        invalid_mobile = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.bancolombia_type_of_transaction == '25' and
                p.partner_id.phone
            )
        )
        # Check if mobile is valid (10 digits starting with 3)
        for payment in invalid_mobile:
            mobile = payment.partner_id.phone
            if mobile:
                mobile_clean = ''.join(filter(str.isdigit, mobile))
                if len(mobile_clean) != 10 or not mobile_clean.startswith('3'):
                    rslt.append({
                        'title': _("Celular del Beneficiario Inválido"),
                        'records': payment,
                        'help': _("El celular debe tener exactamente 10 dígitos y comenzar con 3 para pagos en efectivo (tipo 25)."),
                    })

        return rslt

    # -------------------------------------------------------------------------
    # FILE GENERATION
    # -------------------------------------------------------------------------

    def _generate_bancolombia_file(self):
        """
        Generate Bancolombia Excel file.

        The Excel file should be uploaded to Bancolombia's converter:
        https://www.satbancolombia.com/Conversores#!/pab

        The converter will generate the TXT file in the correct format.

        Returns:
            dict: File information dictionary with Excel file
        """
        self.ensure_one()

        # Determine payment type (220 or 225) - now computed automatically
        payment_type = self.bancolombia_payment_type or '220'

        # Generate Excel content
        excel_content = self._build_bancolombia_excel(payment_type)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        excel_filename = f'BANCOLOMBIA_{payment_type}_{self.journal_id.code}_{timestamp}.xlsx'

        return {
            'file': base64.encodebytes(excel_content),
            'filename': excel_filename,
            'warning': _(
                '✅ Archivo Excel generado: %s\n\n'
                '📋 PASOS PARA GENERAR EL ARCHIVO TXT:\n'
                '1. Descargue el archivo Excel adjunto\n'
                '2. Vaya al conversor de Bancolombia:\n'
                '   https://www.satbancolombia.com/Conversores#!/pab\n'
                '3. Suba el archivo Excel\n'
                '4. El conversor generará automáticamente el archivo TXT\n'
                '5. Descargue el TXT y súbalo al portal de Bancolombia\n\n'
                '💡 El conversor de Bancolombia asegura el formato correcto del TXT.',
                excel_filename,
            ),
        }

    def _build_bancolombia_excel(self, payment_type='220'):
        """
        Build Excel file content for Bancolombia.

        Args:
            payment_type (str): '220' for normal or '225' for payroll

        Returns:
            bytes: Excel file content
        """
        self.ensure_one()

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Dispersal'

        # Get field configuration
        field_configs = self.env['bancolombia.payment_dispersal_field'].search(
            [], order='sequence asc'
        )

        if not field_configs:
            raise UserError(_(
                "No field configuration found for Bancolombia dispersal. "
                "Please contact your system administrator."
            ))

        # Build header section (rows 1-2)
        self._build_bancolombia_header(ws, payment_type)

        # Build column headers (row 4)
        self._build_bancolombia_column_headers(ws, field_configs)

        # Build data rows (row 5+)
        self._build_bancolombia_data_rows(ws, field_configs)

        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return output.getvalue()

    def _build_bancolombia_header(self, worksheet, payment_type):
        """
        Build header section (rows 1-2) of Bancolombia Excel file.

        Header contains:
        - NIT Pagador
        - Tipo de Pago (220/225)
        - Aplicación (I)
        - Secuencia de Envío
        - Nro Cuenta a Debitar
        - Tipo de Cuenta a Debitar
        - Descripción del Pago
        """
        # Get source bank account
        source_account = self.journal_id.bank_account_id

        if not source_account:
            raise UserError(_(
                "The journal '%s' must have a bank account configured.",
                self.journal_id.name,
            ))

        # Row 1: Labels
        worksheet['A1'] = 'NIT PAGADOR'
        worksheet['B1'] = 'TIPO DE PAGO'
        worksheet['C1'] = 'APLICACIÓN'
        worksheet['D1'] = 'SECUENCIA DE ENVIÓ'
        worksheet['E1'] = 'NRO CUENTA A DEBITAR'
        worksheet['F1'] = 'TIPO DE CUENTA A DEBITAR'
        worksheet['G1'] = 'DESCRIPCIÓN DEL PAGO'

        # Row 2: Values
        # NIT Pagador (máximo 15 dígitos, sin dígito de verificación)
        if self.company_id.vat:
            nit = self.company_id.vat
            # Remove non-numeric characters
            nit = ''.join(filter(str.isdigit, nit))
            # Remove last character if it's the check digit (typically the last digit)
            # NIT format: 9 digits + 1 check digit = 10 total
            # But manual says max 15 digits, so we keep all but ensure max 15
            if len(nit) > 15:
                nit = nit[:15]
            # For standard NIT (10 digits), remove check digit (last digit)
            elif len(nit) == 10:
                nit = nit[:-1]
            worksheet['A2'] = nit
        else:
            worksheet['A2'] = ''

        worksheet['B2'] = payment_type
        worksheet['C2'] = 'I'  # Application type (I: Inmediata, M: Medio día, N: Noche)
        # Secuencia de envío: obligatorio, 2 caracteres alfanuméricos
        # Default to '01' if not configured
        worksheet['D2'] = '01'  # Can be configured later if needed
        # Número de cuenta a debitar (máximo 11 dígitos)
        acc_number = ''.join(filter(str.isdigit, source_account.acc_number or ''))
        if len(acc_number) > 11:
            acc_number = acc_number[:11]
        worksheet['E2'] = acc_number

        # Tipo de Cuenta a Debitar (S: Ahorros, D: Corriente)
        account_type_map = {
            'savings_account': 'S',
            'current_account': 'D',
        }
        account_type = account_type_map.get(source_account.co_account_type, 'D')
        worksheet['F2'] = account_type

        # Descripción del Pago (máximo 10 caracteres)
        # Generar referencia basada en fecha si no hay nombre
        if self.name:
            description = self.name[:10]  # Truncar a 10 caracteres
        else:
            # Formato: DDMMYY (6 dígitos) + secuencia (4 dígitos si hay ID)
            date_part = datetime.now().strftime('%d%m%y')
            if self.id:
                seq_part = str(self.id).zfill(4)[-4:]  # Últimos 4 dígitos del ID
                description = f'{date_part}{seq_part}'
            else:
                description = date_part
        worksheet['G2'] = description

    def _build_bancolombia_column_headers(self, worksheet, field_configs):
        """
        Build column header row (row 4).

        Args:
            worksheet: openpyxl worksheet
            field_configs: recordset of field configurations
        """
        for idx, field_config in enumerate(field_configs, start=1):
            col_letter = get_column_letter(idx)
            worksheet[f'{col_letter}4'] = field_config.name

    def _build_bancolombia_data_rows(self, worksheet, field_configs):
        """
        Build data rows (starting from row 5).

        Args:
            worksheet: openpyxl worksheet
            field_configs: recordset of field configurations
        """
        # Prepare evaluation context
        eval_context = self._get_bancolombia_eval_context()

        errors = []

        # Process each payment
        for row_idx, payment in enumerate(self.payment_ids.sorted(key=lambda r: r.id), start=5):
            # Update context with current payment
            eval_context['object'] = payment

            # Evaluate each field
            for col_idx, field_config in enumerate(field_configs, start=1):
                col_letter = get_column_letter(col_idx)
                try:
                    # Execute field value code
                    eval_context['result'] = ''
                    safe_eval(field_config.value, eval_context, mode='exec')
                    worksheet[f'{col_letter}{row_idx}'] = eval_context.get('result', '')
                except Exception as e:
                    _logger.error(
                        "Error evaluating field '%s' for payment %s: %s",
                        field_config.name, payment.name, e,
                    )
                    errors.append(f"- {field_config.name} / {payment.name}: {e}")

        if errors:
            raise UserError(_(
                "Errors evaluating the Bancolombia dispersal fields:\n%s",
                '\n'.join(errors),
            ))

    def _get_bancolombia_eval_context(self):
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
    # NOTE: TXT generation removed - use Bancolombia's official converter
    # -------------------------------------------------------------------------
    # The TXT file is generated by Bancolombia's official converter at:
    # https://www.satbancolombia.com/Conversores#!/pab
    #
    # This ensures the TXT format is always correct and up-to-date with
    # Bancolombia's specifications.
    # -------------------------------------------------------------------------
