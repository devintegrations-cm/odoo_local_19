# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import base64
import io
#from openpyxl import Workbook
from datetime import date, datetime, timedelta, time

from odoo import api, fields, models, _, Command
from odoo.tools.safe_eval import safe_eval
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):

    _inherit = 'account.payment'

    type = fields.Selection(related="journal_id.type", string="Type")
    type_of_account = fields.Selection(related = "partner_bank_id.type_of_account", string='Type of account')