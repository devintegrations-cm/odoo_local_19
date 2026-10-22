# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        Method = self.env['account.payment.method']
        for code in Method._get_colombian_dispersion_bank_codes():
            if self._is_payment_method_available(code):
                method = Method.search([
                    ('code', '=', code),
                    ('payment_type', '=', 'outbound'),
                ], limit=1)
                if method:
                    res |= method
        return res

    @api.depends('bank_id', 'bank_id.code', 'bank_id.bic')
    def _compute_outbound_payment_method_line_ids(self):
        super()._compute_outbound_payment_method_line_ids()

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        bank_journals = journals.filtered(lambda journal: journal.type == 'bank')
        bank_journals._cleanup_incompatible_dispersion_method_lines()
        bank_journals._ensure_dispersion_method_lines()
        bank_journals._assign_dispersion_outstanding_accounts()
        return journals

    def write(self, vals):
        res = super().write(vals)
        if any(field_name in vals for field_name in ('bank_id', 'bank_account_id', 'name')):
            self._cleanup_incompatible_dispersion_method_lines()
            self._ensure_dispersion_method_lines()
            self._assign_dispersion_outstanding_accounts()
        return res

    def _ensure_dispersion_method_lines(self):
        """Add the bank's dispersal methods on matching journals if they are missing."""
        Method = self.env['account.payment.method']
        mapping = Method._get_colombian_dispersion_bank_codes()
        if not mapping:
            return
        for journal in self.filtered(lambda rec: rec.type == 'bank'):
            existing_codes = set(journal.outbound_payment_method_line_ids.mapped('code'))
            for code in mapping:
                if code in existing_codes:
                    continue
                if not Method._journal_matches_dispersion_bank(journal, code):
                    continue
                method = Method.search([
                    ('code', '=', code),
                    ('payment_type', '=', 'outbound'),
                ], limit=1)
                if not method:
                    continue
                self.env['account.payment.method.line'].create({
                    'name': method.name,
                    'payment_method_id': method.id,
                    'journal_id': journal.id,
                })

    def _get_dispersion_method_lines(self):
        mapping = self.env['account.payment.method']._get_colombian_dispersion_bank_codes()
        if not mapping:
            return self.env['account.payment.method.line']
        return self.mapped('outbound_payment_method_line_ids').filtered(
            lambda line: line.payment_method_id.code in mapping
        )

    def _cleanup_incompatible_dispersion_method_lines(self):
        """Remove dispersal methods that do not belong to this journal's bank.

        Journals without bank identification are left untouched. Lines already
        used by payments are only unlinked from the journal (native unlink).
        """
        Method = self.env['account.payment.method']
        to_unlink = self.env['account.payment.method.line']
        for line in self._get_dispersion_method_lines():
            journal = line.journal_id
            bank = journal.bank_id
            if not bank or (not bank.code and not bank.bic):
                continue
            if not Method._journal_matches_dispersion_bank(journal, line.payment_method_id.code):
                to_unlink |= line
        to_unlink.unlink()

    def _assign_dispersion_outstanding_accounts(self):
        """Reuse the journal's manual outstanding account on dispersal lines."""
        for journal in self:
            manual_account = journal.outbound_payment_method_line_ids.filtered(
                lambda line: line.code == 'manual' and line.payment_account_id
            )[:1].payment_account_id
            if not manual_account:
                continue
            for line in journal._get_dispersion_method_lines():
                if not line.payment_account_id:
                    line.payment_account_id = manual_account
