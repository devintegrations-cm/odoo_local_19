# -*- coding: utf-8 -*-
"""Reactiva las vistas que la plataforma de upgrade de Odoo desactiva (hallazgo STG19-VIEWS-0001).

La plataforma corre 17→19 SIN el código de col/ ni Jorels 19, marca sus vistas como inválidas y las desactiva; la
actualización local posterior recarga el XML pero no las reactiva. Visto en staging 41847186 (2026-11-13): quedaron
apagados el formulario de factura de Jorels, su reporte de factura, nómina, dispersión, Shopify, etc. Las 14 validaron
en 19 y se reactivaron a mano allí; esto lo hace solo en el upgrade de producción.

Corre en la fase ``end`` (odoo/modules/loading.py:501), cuando todos los módulos ya están cargados con su XML de 19.
Solo toca la lista fija de abajo (las encontradas y validadas en staging). Cada vista se valida antes de confirmarla;
la que no valida queda inactiva y se reporta en el log, sin detener el upgrade. Las personalizaciones de Studio no se
tocan: son decisión del usuario (STG19-STUDIO-0001). Idempotente.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

VISTAS = [
    "l10n_co_edi_jorels.view_account_journal_form_inherit_l10n_co_edi_jorels",
    "l10n_co_edi_jorels.product_template_form_view_inherit_l10n_co_edi_jorels",
    "l10n_co_edi_jorels.account_move_view_form_inherit_l10n_co_edi_jorels",
    "l10n_co_edi_jorels.res_partner_form_view_inherit_l10n_co_edi_jorels",
    "l10n_co_edi_jorels.report_invoice_document_custom",  # prioridad 17: views/report_invoice_priority.xml
    "l10n_co_hr_payroll_enterprise.hr_salary_rule_view_form_l10n_co_hr_payroll",
    "l10n_co_hr_payroll_enterprise.hr_payslip_view_form_l10n_co_hr_payroll",
    "l10n_co_hr_payroll_enterprise.hr_payslip_tree_l10n_co_payroll",
    "l10n_co_hr_payroll_enterprise.view_employee_form_l10n_co_hr_payroll",
    "account_payment_dispersion.account_payment_dispersion_inherit_view_account_payment_form",
    "shopify_order_webhook.sale_res_config_settings_view_form_shopify_config",
    "plant_request_board.view_plant_request_search",
    "plant_request_board.view_plant_consolidation_search",
    "purchase_cost_validator.purchase_order_form_cost_check",
]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False})
    reactivadas, invalidas = [], []
    for xmlid in VISTAS:
        vista = env.ref(xmlid, raise_if_not_found=False)
        if not vista or vista._name != "ir.ui.view" or vista.active:
            continue
        try:
            with cr.savepoint():
                vista.write({"active": True})
                vista._check_xml()
            reactivadas.append(xmlid)
        except Exception as e:  # noqa: BLE001 - una vista inválida no debe abortar el upgrade
            env.invalidate_all()
            invalidas.append(xmlid)
            _logger.warning("STG19-VIEWS-0001: %s sigue INACTIVA, no valida en 19: %s", xmlid, " ".join(str(e).split())[:300])
    if reactivadas:
        env.registry.clear_cache("templates")
    _logger.info("STG19-VIEWS-0001: %s vistas reactivadas %s; %s siguen inactivas %s",
                 len(reactivadas), reactivadas, len(invalidas), invalidas)
