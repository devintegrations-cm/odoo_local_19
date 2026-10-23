# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from ast import literal_eval

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountBatchPayment(models.Model):
    """
    Extension of account.batch.payment for Colombian bank payment dispersal.

    This model provides the base infrastructure for generating payment dispersal
    files for Colombian banks. It registers Colombian payment methods and provides
    common validation logic.
    """
    _inherit = 'account.batch.payment'

    # -------------------------------------------------------------------------
    # HOOKS FOR FILE GENERATION
    # -------------------------------------------------------------------------

    def _get_methods_generating_files(self):
        """
        Register Colombian payment methods that generate export files.

        This method is a hook that tells Odoo which payment methods should show
        the "Export File" button instead of the "Print" button.

        Returns:
            list: Payment method codes that generate files
        """
        rslt = super()._get_methods_generating_files()

        # Register Colombian bank dispersal methods
        # These will be added by specific bank modules:
        # - bancolombia_dispersion (added by bancolombia_payment_dispersal module)
        # - banco_occidente_dispersion (added by banco_de_occidente_payment_dispersal module)

        return rslt

    def _generate_export_file(self):
        """
        Main hook for export file generation.

        This method is called when the user clicks "Export File" on a batch payment.
        It should be overridden by bank-specific modules to generate their files.

        Returns:
            dict: Dictionary with keys:
                - file (bytes): Base64-encoded file content
                - filename (str): Name of the file
                - warning (str, optional): Warning message to display

            Or False if no file could be generated
        """
        self.ensure_one()

        # This will be overridden by bank-specific modules
        # Example: bancolombia_payment_dispersal will check for payment_method_code == 'bancolombia_dispersion'

        return super()._generate_export_file()

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------

    def check_payments_for_errors(self):
        """
        Validate payments for Colombian-specific requirements.

        This method is called before generating the export file to check for
        blocking errors that prevent file generation.

        Returns:
            list: List of error dictionaries with keys:
                - title (str): Error title
                - records (recordset): Affected payment records
                - help (str, optional): Help text for resolving the error
        """
        rslt = super().check_payments_for_errors()

        # Only validate for Colombian dispersal methods
        if not self._is_colombian_dispersal_method():
            return rslt

        # Common validations for all Colombian banks
        rslt.extend(self._validate_colombian_requirements())

        return rslt

    def check_payments_for_warnings(self):
        """
        Check for non-blocking warnings in payments.

        These are issues that won't prevent file generation but should be
        brought to the user's attention.

        Returns:
            list: List of warning dictionaries (same structure as errors)
        """
        rslt = super().check_payments_for_warnings()

        if not self._is_colombian_dispersal_method():
            return rslt

        # Check for high amounts
        high_amount_payments = self.payment_ids.filtered(lambda p: p.amount > 50000000)
        if high_amount_payments:
            rslt.append({
                'title': _("Pagos con Montos Altos"),
                'records': high_amount_payments,
                'help': _("Algunos pagos exceden $50,000,000 COP. Por favor verifique los montos antes de procesar."),
            })

        # Check for payments without email
        no_email_payments = self.payment_ids.filtered(lambda p: not p.partner_id.email)
        if no_email_payments:
            rslt.append({
                'title': _("Contactos sin Correo Electrónico"),
                'records': no_email_payments,
                'help': _("Algunos beneficiarios no tienen direcciones de correo electrónico configuradas."),
            })

        return rslt

    def _validate_colombian_requirements(self):
        """
        Validate common Colombian requirements for all banks.

        Returns:
            list: List of error dictionaries
        """
        errors = []

        # Get valid payment states
        valid_states = self._valid_payment_states()

        # 1. Validate bank accounts
        no_bank_account = self.payment_ids.filtered(
            lambda p: p.state in valid_states and not p.partner_bank_id
        )

        if no_bank_account:
            errors.append({
                'title': _("Pagos sin Cuenta Bancaria"),
                'records': no_bank_account,
                'help': _("Configure la cuenta bancaria del beneficiario en el formulario del contacto."),
            })

        # 2. Validate VAT/ID numbers
        # El NIT de un contacto ligado a una empresas está en la empresa
        # comercial (commercial_partner_id), no en el contacto de entrega.
        no_vat = self.payment_ids.filtered(
            lambda p: p.state in valid_states and not p.partner_id.commercial_partner_id.vat
        )
        if no_vat:
            errors.append({
                'title': _("Beneficiarios sin NIT/Identificación"),
                'records': no_vat,
                'help': _("Configure el número de NIT o Cédula para los beneficiarios."),
            })

        # 3. Validate account types
        invalid_account_type = self.payment_ids.filtered(
            lambda p: p.state in valid_states and p.partner_bank_id and not p.partner_bank_id.co_account_type
        )
        if invalid_account_type:
            errors.append({
                'title': _("Cuentas Bancarias sin Tipo"),
                'records': invalid_account_type,
                'help': _("Seleccione el tipo de cuenta (Ahorros/Corriente) en la configuración de la cuenta bancaria."),
            })

        # 4. Validate bank dispersal codes (used in the flat files).
        # Una cuenta sin banco tampoco puede salir en el archivo: el código de
        # dispersión se toma del banco y el banco del archivo lo rechazaría
        # (no Odoo). Se valida igual que el resto.
        no_bank_code = self.payment_ids.filtered(
            lambda p: (
                p.state in valid_states and
                p.partner_bank_id and
                (not p.partner_bank_id.bank_id or not p.partner_bank_id.bank_id.dispersal_code)
            )
        )
        if no_bank_code:
            errors.append({
                'title': _("Cuentas sin Banco o sin Código de Dispersión"),
                'records': no_bank_code,
                'help': _("Asocie el banco a la cuenta bancaria del beneficiario y verifique "
                          "que el banco tenga código de dispersión en los datos maestros."),
            })

        return errors

    @api.depends('batch_type', 'journal_id', 'payment_method_id', 'payment_ids')
    def _compute_payment_ids_domain(self):
        super()._compute_payment_ids_domain()
        for batch in self:
            extra_domain = batch._get_dispersion_payment_domain()
            if extra_domain and batch.payment_ids_domain:
                batch.payment_ids_domain = str(literal_eval(batch.payment_ids_domain) + extra_domain)

    def _get_dispersion_payment_domain(self):
        """Restrict payments that can be added to this batch to the same service type."""
        self.ensure_one()
        return []

    @api.constrains('payment_ids', 'payment_method_id')
    def _check_dispersion_batch_grouping(self):
        for batch in self:
            keys = {
                payment._get_dispersion_batch_grouping_key()
                for payment in batch.payment_ids
            }
            if len(keys) > 1:
                raise ValidationError(_(
                    "Un lote de dispersión solo puede incluir pagos del mismo tipo de servicio."
                ))

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _is_colombian_dispersal_method(self):
        """
        Check if current payment method is a Colombian dispersal method.

        Returns:
            bool: True if it's a Colombian dispersal method
        """
        self.ensure_one()

        return self.payment_method_code in self.env['account.payment.method']._get_colombian_dispersion_bank_codes()

