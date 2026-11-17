# -*- coding: utf-8 -*-
#


import logging
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = "res.company"

    url_superfinancial_service = fields.Char(
        string='Url superfinancial service',
        default="https://www.superfinanciera.gov.co/SuperfinancieraWebServiceTRM/TCRMServicesWebService/TCRMServicesWebService?wsdl")

    body_superfinancial_request = fields.Text(
        string='Body superfinancial request',
        default="""
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:act="http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/">
            <soapenv:Header/>
            <soapenv:Body>
            <act:queryTCRM>
            </act:queryTCRM>
            </soapenv:Body>
            </soapenv:Envelope>
        """)

    def _get_currency_exchange_cop_to_usd(self):
        records = self.search([('url_superfinancial_service', '!=', False),
                              ('body_superfinancial_request', '!=', False), ('currency_id', '=', self.env.ref('base.COP').id)])
        for record in records:

            url = record.url_superfinancial_service
            xml_body = record.body_superfinancial_request

            headers = {
                'Content-Type': 'text/xml',
                'charset': 'utf-8',
            }

            response = requests.post(url, data=xml_body, headers=headers)

            if response:
                response_data = response.text
                root = ET.fromstring(response_data)
                value_element = root.find(".//value")
                value_element = float(value_element.text)
                validity_to_datetime = (datetime.now()).replace(
                    hour=0, minute=0, second=0)
                if value_element and validity_to_datetime:
                    curreny = self.env.ref('base.USD')
                    vals = {'rate': (1.0 / value_element), 'currency_id': curreny.id, 'name': validity_to_datetime, 'company_id': record.id}
                    self.env['res.currency.rate'].sudo().create(vals)
