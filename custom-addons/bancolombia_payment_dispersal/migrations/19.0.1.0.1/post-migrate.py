# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import api, SUPERUSER_ID
from odoo.tools import file_open

MODULE = 'bancolombia_payment_dispersal'
DATA_FILE = 'bancolombia_payment_dispersal/data/bancolombia_payment_dispersal_field_data.xml'
# Records whose code used res.partner.mobile, removed in Odoo 19
XMLIDS = ['bancolombia_payment_dispersal_field_beneficiary_mobile']


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    with file_open(DATA_FILE, 'rb') as f:
        tree = etree.parse(f)

    for xmlid in XMLIDS:
        record = env.ref(f'{MODULE}.{xmlid}', raise_if_not_found=False)
        # Only fix records that were not customized away from the mobile field
        if not record or 'partner_id.mobile' not in (record.value or ''):
            continue
        node = tree.find(f".//record[@id='{xmlid}']/field[@name='value']")
        if node is not None:
            record.value = node.text
