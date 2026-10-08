# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import logging
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _, exceptions
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class BancolombiaPaymentDispersalField(models.Model):

    _name = 'bancolombia.payment_dispersal_field'
    _inherit = "account.payment_dispersal_field"
    _order = "sequence asc"
    _description = 'Configuration of the fields to be displayed in the excel file for payments in bancolombia'
