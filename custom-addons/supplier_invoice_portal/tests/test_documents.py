# -*- coding: utf-8 -*-
"""Tests de los ajustes del comite (2026-09-23).

Varias ordenes en una factura, fletes que no estan en la orden, notas credito
y debito, cuenta de cobro de no obligados a facturar, requisitos para habilitar
un proveedor, contactos padre e hijo y cierre de radicacion de fin de mes.
"""

import base64
import io
import os
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.supplier_invoice_portal.controllers.portal import SupplierInvoicePortal
from odoo.addons.supplier_invoice_portal.models import res_partner
from odoo.addons.supplier_invoice_portal.services import cutoff, line_matcher, validation_rules

from .common import DUMMY_PDF, SprCase, read_fixture


@tagged("post_install", "-at_install")
class TestDocuments(SprCase):

    def _invoiced_request(self):
        """Factura SETP990000001 radicada, validada y con su factura publicada
        (una nota sobre un borrador queda con observacion, DECISIONS.md #57)."""
        order = self._standard_po()
        request = self._create_request(order)
        request.action_validate()
        request.action_create_bill()
        request.move_id.action_post()
        return order, request

    # ------------------------------------------------------------------
    # Varias ordenes en una factura
    # ------------------------------------------------------------------

    def test_one_invoice_for_several_orders(self):
        order_cafe = self._create_po([(self.product_cafe, 100, 12000.0)])
        order_bag = self._create_po([(self.product_bag, 50, 2000.0)])
        request = self._create_request(order_cafe | order_bag)
        request.action_validate()
        self.assertEqual(request.state, "approved", request.validation_summary)
        self.assertEqual(
            request.line_ids.po_line_id.order_id, order_cafe | order_bag,
            "Cada linea se empareja con la orden que la tiene.",
        )
        request.action_create_bill()
        move = request.move_id
        self.assertIn(order_cafe.name, move.invoice_origin)
        self.assertIn(order_bag.name, move.invoice_origin)
        self.assertEqual(order_cafe.invoice_status, "invoiced")
        self.assertEqual(order_bag.invoice_status, "invoiced")
        self.assertEqual(order_cafe.spr_request_count, 1)
        self.assertEqual(order_bag.spr_request_count, 1)

    def test_several_orders_pending_is_the_sum(self):
        # Una sola orden no alcanza para el total; las dos juntas si.
        order_cafe = self._create_po([(self.product_cafe, 100, 12000.0)])
        request = self._create_request(order_cafe)
        request.action_validate()
        self.assertIn("AMOUNT_TOTAL", self._codes(request, "error"))

    def test_open_orders_and_preview_files(self):
        # Boton de ordenes y vista previa del XML (DECISIONS.md #66).
        order_cafe = self._create_po([(self.product_cafe, 100, 12000.0)])
        order_bag = self._create_po([(self.product_bag, 50, 2000.0)])
        request = self._create_request(order_cafe | order_bag)
        self.assertEqual(request.purchase_count, 2)
        action = request.action_view_purchases()
        self.assertEqual(action["res_model"], "purchase.order")
        self.assertEqual(action["domain"], [("id", "in", (order_cafe | order_bag).ids)])

        # Pestana Orden de compra (DECISIONS.md #68).
        self.assertEqual(request.purchase_line_ids, (order_cafe | order_bag).order_line)
        self.assertAlmostEqual(request.purchase_amount_untaxed, 1300000.0, places=2)

        request.purchase_ids = order_cafe
        action = request.action_view_purchases()
        self.assertEqual(action["res_id"], order_cafe.id)
        self.assertEqual(action["view_mode"], "form")

        preview = request.spr_xml_preview()
        self.assertIn("<cbc:ID>SETP990000001</cbc:ID>", preview)
        self.assertGreater(preview.count("\n"), 20, "El XML sale con sangria.")
        request.xml_file = base64.b64encode(b"no es xml")
        self.assertIn("No se pudo leer el XML", request.spr_xml_preview())

        # El PDF queda en el chatter y es el adjunto principal (DECISIONS.md #67).
        main = request.message_main_attachment_id
        self.assertEqual(main.mimetype, "application/pdf")
        self.assertFalse(main.res_field)
        self.assertIn(main, request.message_ids.attachment_ids)
        request.write({"pdf_file": DUMMY_PDF, "pdf_filename": "corregida.pdf"})
        self.assertEqual(request.message_main_attachment_id.name, "corregida.pdf")

    # ------------------------------------------------------------------
    # Fletes
    # ------------------------------------------------------------------

    def test_freight_is_an_extra_charge_not_an_error(self):
        order = self._create_po([(self.product_cafe, 100, 12000.0)])
        request = self._create_request(order, xml_name="invoice_with_freight.xml")
        request.action_validate()

        charges = request.line_ids.filtered("is_extra_charge")
        self.assertEqual(
            sorted(charges.mapped("description")),
            ["Cargo adicional: Manejo y cargue", "Flete Medellin - Bogota"],
        )
        self.assertEqual(set(charges.mapped("match_method")), {line_matcher.MATCH_CHARGE})
        # Sin producto de flete en Ajustes queda observacion: la factura no se
        # puede crear.
        self.assertEqual(request.state, "warning", request.validation_summary)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "warning"))
        # El flete no cuenta contra lo pendiente de la orden ni como linea suelta.
        self.assertFalse(self._codes(request, "error"))
        self.assertNotIn("LINES_MATCHED", self._codes(request, "warning"))
        with self.assertRaises(UserError):
            request.action_create_bill()

        # Con el producto configurado, el flete ya no frena la aprobacion
        # (DECISIONS.md #64, port de la v17 #53).
        freight = self.env["product.product"].create({
            "name": "Flete de compras", "type": "service",
            "supplier_taxes_id": [(6, 0, self.tax_19.ids)],
        })
        self.env["ir.config_parameter"].sudo().set_param("spr.freight_product_id", freight.id)
        request.action_validate()
        self.assertEqual(request.state, "approved", request.validation_summary)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "ok"))
        charges = request.line_ids.filtered("is_extra_charge")
        self.assertEqual(len(charges), 2)
        self.assertTrue(all("Flete de compras" in note for note in charges.mapped("match_note")))
        request.action_create_bill()
        move = request.move_id
        freight_lines = move.invoice_line_ids.filtered(lambda l: l.product_id == freight)
        self.assertEqual(len(freight_lines), 2)
        # El flete entra a la orden: cada cargo queda con su linea (DECISIONS.md #43).
        self.assertEqual(len(freight_lines.purchase_line_id), 2)
        self.assertEqual(freight_lines.purchase_line_id.order_id, order)
        self.assertEqual(freight_lines.purchase_line_id.product_id, freight)
        self.assertFalse(freight_lines.tax_ids, "La factura no le cobra IVA al flete.")
        self.assertAlmostEqual(move.amount_total, 1528000.0, places=2)

    def _freight_request(self, max_pct=None):
        freight = self.env["product.product"].create({
            "name": "Flete de compras", "type": "service",
        })
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("spr.freight_product_id", freight.id)
        if max_pct is not None:
            params.set_param("spr.freight_max_pct", repr(max_pct))
        order = self._create_po([(self.product_cafe, 100, 12000.0)])
        request = self._create_request(order, xml_name="invoice_with_freight.xml")
        request.action_validate()
        return request

    def test_freight_under_the_cap_is_ok(self):
        # DECISIONS.md #73: 100.000 de cargos sobre 1.200.000 de mercancia es
        # el 8,33 %, bajo el tope por defecto (10 %).
        request = self._freight_request()
        self.assertIn("EXTRA_CHARGES", self._codes(request, "ok"))
        self.assertEqual(request.state, "approved", request.validation_summary)

    def test_freight_over_the_cap_is_a_warning(self):
        request = self._freight_request(max_pct=5.0)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "warning"))
        self.assertEqual(request.state, "warning")
        self.assertIn("supera el tope de 5,00 %", request.validation_summary)
        self.assertIn("8,33 %", request.validation_summary)

    def test_freight_cap_ignores_freight_vat(self):
        # Base contra base: 100.000 de flete sobre 1.200.000 es el 8,33 % aunque
        # con IVA del 19 % serian 119.000 (9,92 %). Con tope de 9 % pasa.
        request = self._freight_request(max_pct=9.0)
        request.line_ids.filtered("is_extra_charge").write({"tax_rate": 19.0})
        findings = validation_rules._rule_extra_charges({"request": request})
        self.assertEqual(findings[0].level, validation_rules.LEVEL_OK, findings[0].message_es)
        request.line_ids.filtered("is_extra_charge").write({"tax_rate": 0.0})
        self.env["ir.config_parameter"].sudo().set_param("spr.freight_max_pct", "8.0")
        findings = validation_rules._rule_extra_charges({"request": request})
        self.assertEqual(findings[0].level, validation_rules.LEVEL_WARNING)
        self.assertIn("antes de IVA", findings[0].message_es)

    def test_freight_cap_zero_means_no_cap(self):
        request = self._freight_request(max_pct=0.0)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "ok"))
        self.assertEqual(request.state, "approved", request.validation_summary)

    def test_freight_cap_setting_keeps_zero(self):
        # Con config_parameter, Odoo borraria el parametro en 0 y volveria el 10.
        settings = self.env["res.config.settings"].create({"spr_freight_max_pct": 0.0})
        settings.execute()
        self.assertEqual(
            self.env["ir.config_parameter"].sudo().get_param("spr.freight_max_pct"), "0.0")
        self.assertEqual(self.env["res.config.settings"].create({}).spr_freight_max_pct, 0.0)

    def test_bill_accounting_date_equals_invoice_date(self):
        # DECISIONS.md #70: la fecha contable es la de la factura, no la de hoy.
        order = self._standard_po()
        request = self._create_request(order)
        request.action_validate()
        self.assertTrue(request.invoice_date)
        request.action_create_bill()
        move = request.move_id
        self.assertEqual(move.date, request.invoice_date)
        self.assertEqual(move.invoice_date, request.invoice_date)

    def test_freight_bill_line_inherits_analytic_distribution(self):
        # DECISIONS.md #70: el flete hereda la analitica de la mercancia.
        plan = self.env["account.analytic.plan"].create({
            "name": "Costos compras",
        })
        analytic = self.env["account.analytic.account"].create({
            "name": "Costo cafe", "plan_id": plan.id, "company_id": self.company.id,
        })
        key = str(analytic.id)
        order = self._standard_po()
        order.order_line[0].analytic_distribution = {key: 100.0}
        freight = self.env["product.product"].create({
            "name": "Flete de compras", "type": "service",
        })
        self.env["ir.config_parameter"].sudo().set_param("spr.freight_product_id", freight.id)
        request = self._create_request(order, xml_name="invoice_with_freight.xml")
        request.action_validate()
        self.assertEqual(request.state, "approved", request.validation_summary)
        request.action_create_bill()
        freight_lines = request.move_id.invoice_line_ids.filtered(
            lambda l: l.product_id == freight)
        self.assertTrue(freight_lines, "hay lineas de flete en la factura")
        for line in freight_lines:
            self.assertEqual(
                (line.analytic_distribution or {}).get(key), 100.0,
                "la linea de flete lleva la analitica de la orden")

    def test_freight_matched_by_product_code(self):
        # Una linea con el codigo del producto de flete es flete, diga lo que diga.
        freight = self.env["product.product"].create({
            "name": "Flete de compras", "type": "service", "default_code": "EMP 500",
        })
        self.env["ir.config_parameter"].sudo().set_param("spr.freight_product_id", freight.id)
        order = self._create_po([(self.product_cafe, 100, 12000.0)])
        request = self._create_request(order)
        request.action_validate()
        line = request.line_ids.filtered(lambda l: l.product_code == "EMP-500")
        self.assertTrue(line.is_extra_charge)
        self.assertEqual(line.match_method, line_matcher.MATCH_CHARGE)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "ok"))

    def test_user_without_portal_groups_can_read_all_fields(self):
        """Regresion de produccion: el boton de cliente Leal del POS (odooleal) lee
        el contacto con searchRead y fields=[] (todos los campos). Los campos del
        portal se calculaban leyendo solicitudes de pago y daban AccessError
        (DECISIONS.md #63).

        En 19 un search_read de todos los campos tropieza tambien con campos
        del core (rtc_session_ids de discuss, pos.order...) que el cajero no
        lee; eso no es de este modulo. Lo que se prueba es que los ``spr_*``
        no aparecen en ``fields_get`` del cajero, asi que no se calculan."""
        order = self._standard_po()
        request = self._create_request(order)
        request.action_validate()
        request.action_create_bill()
        cashier = self.env["res.users"].create({
            "name": "Cajero POS", "login": "cajero_pos_spr",
            "company_id": self.company.id, "company_ids": [(6, 0, self.company.ids)],
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                  self.env.ref("purchase.group_purchase_user").id,
                                  self.env.ref("account.group_account_invoice").id])],
        })
        env = self.env(user=cashier)
        # Los campos del portal no existen para quien no es validador.
        partner_fields = env["res.partner"].browse(self.supplier.id).fields_get()
        self.assertNotIn("spr_request_count", partner_fields)
        self.assertNotIn("spr_doc_rut_id", partner_fields)
        order_fields = env["purchase.order"].browse(order.id).fields_get()
        self.assertNotIn("spr_request_count", order_fields)
        move_fields = env["account.move"].browse(request.move_id.id).fields_get()
        self.assertNotIn("spr_request_ids", move_fields)
        # Lo que el cajero si lee no toca las solicitudes de pago.
        partner = env["res.partner"].browse(self.supplier.id)
        values = partner.search_read(
            [("id", "=", self.supplier.id)], ["name", "vat", "portal_invoice_enabled"])[0]
        self.assertEqual(values["name"], self.supplier.name)
        env["purchase.order"].browse(order.id).read(["name", "amount_total"])
        env["account.move"].browse(request.move_id.id).read(["ref", "amount_total"])

    # ------------------------------------------------------------------
    # IVA como producto (mayor valor IVA)
    # ------------------------------------------------------------------

    def _enable_tax_as_product(self):
        exempt = self.env["account.tax"].create({
            "name": "IVA Compra Exento", "amount": 0.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
        })
        tax_product = self.env["product.product"].create({
            "name": "Mayor Valor Iva Compras", "default_code": "MAYVALIVACOM191",
            "type": "service",
        })
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("spr.tax_as_product", "True")
        params.set_param("spr.tax_product_id", tax_product.id)
        params.set_param("spr.exempt_tax_id", exempt.id)
        return tax_product, exempt

    def test_tax_as_product_adds_the_vat_line_to_order_and_bill(self):
        tax_product, exempt = self._enable_tax_as_product()
        order = self._standard_po()
        request = self._create_request(order)
        request.action_validate()
        # La orden al 0 % es la practica: no se reporta como diferencia de tasa.
        self.assertNotIn("TAX_RATE_MISMATCH", self._codes(request))
        self.assertNotIn("AMOUNT_TOTAL", self._codes(request, "error"))
        self.assertIn("TAX_AS_PRODUCT", self._codes(request, "warning"))

        request.action_create_bill()
        move = request.move_id
        self.assertEqual(move.invoice_line_ids.tax_ids, exempt)
        vat_line = move.invoice_line_ids.filtered(lambda l: l.product_id == tax_product)
        self.assertAlmostEqual(vat_line.price_unit, request.amount_tax, places=2)
        self.assertEqual(vat_line.purchase_line_id.order_id, order, "El IVA entra a la orden.")
        self.assertEqual(order.order_line.tax_ids, exempt, "La orden tambien queda al 0 %.")
        self.assertAlmostEqual(move.amount_total, request.amount_total, places=2)

    def test_tax_as_product_reuses_the_vat_line_of_the_order(self):
        tax_product, _exempt = self._enable_tax_as_product()
        order = self._create_po([
            (self.product_cafe, 100, 12000.0),
            (self.product_bag, 50, 2000.0),
            (tax_product, 1, 247000.0),
        ])
        request = self._create_request(order)
        request.action_validate()
        self.assertIn("TAX_AS_PRODUCT", self._codes(request, "ok"))
        self.assertEqual(request.state, "approved", request.validation_summary)
        request.action_create_bill()
        vat_po_lines = order.order_line.filtered(lambda l: l.product_id == tax_product)
        self.assertEqual(len(vat_po_lines), 1, "No se duplica la linea de IVA de la orden.")
        self.assertEqual(vat_po_lines.invoice_lines.move_id, request.move_id)

    def test_tax_as_product_without_settings_blocks_the_bill(self):
        self.env["ir.config_parameter"].sudo().set_param("spr.tax_as_product", "True")
        request = self._create_request(self._standard_po())
        request.action_validate()
        with self.assertRaises(UserError):
            request.action_create_bill()

    def test_manual_extra_charge_survives_revalidation(self):
        # El empaque no esta en la orden: el validador lo marca como cargo.
        order = self._create_po([(self.product_cafe, 100, 12000.0)])
        request = self._create_request(order)
        request.action_validate()
        bag_line = request.line_ids.filtered(lambda l: l.product_code == "EMP-500")
        self.assertFalse(bag_line.po_line_id)
        bag_line.write({"is_extra_charge": True, "match_method": "manual"})
        request.action_validate()
        bag_line = request.line_ids.filtered(lambda l: l.product_code == "EMP-500")
        self.assertTrue(bag_line.is_extra_charge)
        self.assertIn("EXTRA_CHARGES", self._codes(request, "warning"))

    def test_charge_keywords(self):
        self.assertTrue(line_matcher.is_charge_description("FLETE Bogota"))
        self.assertTrue(line_matcher.is_charge_description("Costo de envío"))
        self.assertTrue(line_matcher.is_charge_description("Servicio de transporte"))
        self.assertTrue(line_matcher.is_charge_description("Domicilios"))
        self.assertTrue(line_matcher.is_charge_description("Encomienda Servientrega"))
        self.assertTrue(line_matcher.is_charge_description("Courier"))
        self.assertFalse(line_matcher.is_charge_description("Empaque valvulado 500g"))
        self.assertFalse(line_matcher.is_charge_description("Reenvio de caja"))

    # ------------------------------------------------------------------
    # Notas credito y debito
    # ------------------------------------------------------------------

    def test_credit_note_finds_its_invoice_and_creates_a_refund(self):
        order, invoice_request = self._invoiced_request()
        note = self._create_request(
            None, xml_name="credit_note.xml", document_type="credit_note"
        )
        note.action_validate()
        self.assertEqual(note.origin_move_id, invoice_request.move_id,
                         "La nota se asocia por el CUFE de BillingReference.")
        self.assertEqual(note.purchase_ids, order)
        self.assertEqual(note.state, "approved", note.validation_summary)

        note.action_create_bill()
        refund = note.move_id
        self.assertEqual(refund.move_type, "in_refund")
        self.assertEqual(refund.reversed_entry_id, invoice_request.move_id)
        self.assertAlmostEqual(refund.amount_total, 142800.0, places=2)
        self.assertFalse(refund.invoice_line_ids.purchase_line_id,
                         "La nota no toca las cantidades facturadas de la orden.")
        self.assertEqual(order.order_line[0].qty_invoiced, 100)

    def test_credit_note_cannot_exceed_invoice_balance(self):
        self._invoiced_request()
        xml = read_fixture("credit_note.xml").replace(
            b'<cbc:PayableAmount currencyID="COP">142800.00',
            b'<cbc:PayableAmount currencyID="COP">1600000.00',
        )
        note = self._create_request(None, xml_bytes=xml, document_type="credit_note")
        note.action_validate()
        self.assertIn("NOTE_AMOUNT", self._codes(note, "error"))

    def test_credit_note_without_invoice_is_rejected(self):
        note = self._create_request(None, xml_name="credit_note.xml", document_type="credit_note")
        note.action_validate()
        self.assertEqual(note.state, "rejected")
        self.assertIn("NOTE_ORIGIN", self._codes(note, "error"))

    def test_debit_note_needs_acceptance(self):
        order, invoice_request = self._invoiced_request()
        note = self._create_request(None, xml_name="debit_note.xml", document_type="debit_note")
        note.action_validate()
        self.assertEqual(note.origin_move_id, invoice_request.move_id)
        self.assertEqual(note.state, "warning", note.validation_summary)
        self.assertIn("DEBIT_NOTE_ACCEPTANCE", self._codes(note, "warning"))
        with self.assertRaises(UserError):
            note.action_create_bill()

        note.action_accept_debit_note()
        self.assertEqual(note.note_accepted_by_id, self.env.user)
        self.assertEqual(note.state, "approved", note.validation_summary)
        note.action_create_bill()
        move = note.move_id
        self.assertEqual(move.move_type, "in_invoice")
        self.assertAlmostEqual(move.amount_total, 59500.0, places=2)
        self.assertFalse(move.invoice_line_ids.purchase_line_id)
        if "debit_origin_id" in move._fields:
            self.assertEqual(move.debit_origin_id, invoice_request.move_id)

    def test_xml_of_another_type_is_rejected(self):
        order = self._standard_po()
        request = self._create_request(order, xml_name="credit_note.xml")
        request.action_validate()
        self.assertIn("DOCUMENT_TYPE", self._codes(request, "error"))

    # ------------------------------------------------------------------
    # Cuenta de cobro (documento soporte)
    # ------------------------------------------------------------------

    def _support_setup(self):
        self.supplier.spr_support_document = True
        journal = self.env["account.journal"].create({
            "name": "Documento soporte", "code": "DSP", "type": "purchase",
            "company_id": self.company.id,
        })
        self.env["ir.config_parameter"].sudo().set_param("spr.support_journal_id", journal.id)
        return journal

    def _support_request(self, order, **extra):
        values = {
            "document_type": "support_doc",
            "partner_id": self.supplier.id,
            "purchase_ids": [(6, 0, order.ids)],
            "company_id": self.company.id,
            "currency_id": self.company.currency_id.id,
            "pdf_file": DUMMY_PDF,
            "pdf_filename": "cuenta_cobro.pdf",
            "invoice_ref": "CC-15",
            "invoice_date": "2026-03-15",
            "amount_total": 1547000.0,
        }
        values.update(extra)
        return self.env["supplier.payment.request"].create(values)

    def test_support_doc_lines_come_from_the_order(self):
        journal = self._support_setup()
        order = self._standard_po()
        request = self._support_request(order)
        self.assertEqual(request.journal_id, journal)
        request.action_validate()
        self.assertEqual(request.state, "approved", request.validation_summary)
        self.assertEqual(len(request.line_ids), 2)
        self.assertEqual(set(request.line_ids.mapped("match_method")), {"order"})
        self.assertEqual(request.amount_total, 1547000.0, "El total declarado no se pisa.")
        self.assertEqual(request.invoice_ref, "CC-15")

        request.action_create_bill()
        move = request.move_id
        self.assertEqual(move.journal_id, journal)
        self.assertFalse(move.cufe)
        self.assertEqual(set(move.invoice_line_ids.purchase_line_id), set(order.order_line))

    def test_support_doc_total_mismatch_and_duplicate(self):
        self._support_setup()
        order = self._standard_po()
        request = self._support_request(order, amount_total=1000000.0)
        request.action_validate()
        self.assertIn("AMOUNT_INCONSISTENT", self._codes(request, "warning"))

        again = self._support_request(order)
        again.action_validate()
        self.assertIn("INVOICE_REF_DUPLICATE", self._codes(again, "error"))

    def test_support_doc_needs_its_journal(self):
        order = self._standard_po()
        self.supplier.spr_support_document = True
        request = self._support_request(order)
        request.action_validate()
        with self.assertRaises(UserError):
            request.action_create_bill()

    # ------------------------------------------------------------------
    # Habilitar proveedores: NIT, contacto comercial
    # ------------------------------------------------------------------

    def test_enable_requires_nit(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "SIN NIT SAS", "is_company": True, "portal_invoice_enabled": True,
            })

    def test_duplicate_nit_does_not_block_enabling(self):
        # Otro tercero con el mismo NIT (sin DV y con puntos) ya no impide habilitar.
        self.env["res.partner"].create({
            "name": "Cafes del Sur (duplicado)", "is_company": True, "vat": "900.123.456",
        })
        self.supplier.portal_invoice_enabled = False
        self.supplier.portal_invoice_enabled = True
        self.assertTrue(self.supplier.portal_invoice_enabled)

    def test_child_contacts_are_not_duplicates_nor_enabled(self):
        child = self.env["res.partner"].create({
            "name": "Tesoreria Cafes del Sur", "parent_id": self.supplier.id,
        })
        self.assertEqual(child.vat, self.supplier.vat, "Odoo copia el NIT a los hijos.")
        self.supplier.write({"vat": "900123456-7", "portal_invoice_enabled": True})
        with self.assertRaises(ValidationError):
            child.portal_invoice_enabled = True

    def test_request_partner_is_the_commercial_one(self):
        child = self.env["res.partner"].create({
            "name": "Cuentas por pagar", "parent_id": self.supplier.id,
        })
        order = self._standard_po()
        request = self._create_request(order, partner_id=child.id)
        self.assertEqual(request.partner_id, self.supplier)

    def _instructions_composer(self):
        action = self.supplier.action_spr_send_instructions()
        self.assertEqual(action["res_model"], "mail.compose.message")
        return self.env["mail.compose.message"].browse(action["res_id"])

    @staticmethod
    def _guide_file_open(replacement):
        """file_open que solo cambia la guia: el reporte QWeb lee sus capturas
        con el mismo file_open y tiene que seguir funcionando."""
        real = res_partner.file_open

        def fake(path, *args, **kwargs):
            if path != res_partner.SPR_INSTRUCTIONS_PDF:
                return real(path, *args, **kwargs)
            if isinstance(replacement, type) and issubclass(replacement, Exception):
                raise replacement(path)
            return io.BytesIO(replacement)
        return fake

    def _instructions_guide(self, composer):
        name = os.path.basename(res_partner.SPR_INSTRUCTIONS_PDF)
        return composer.attachment_ids.filtered(lambda att: att.name == name)

    def test_instructions_email(self):
        composer = self._instructions_composer()
        template = self.env.ref("supplier_invoice_portal.mail_template_spr_instructions")
        self.assertEqual(composer.template_id, template)
        self.assertEqual(composer.model, "res.partner")
        self.assertEqual(composer._evaluate_res_ids(), self.supplier.ids)
        self.assertEqual(composer.composition_mode, "comment")
        self.assertEqual(composer.email_layout_xmlid, "mail.mail_notification_light")
        body = template._render_field("body_html", self.supplier.ids)[self.supplier.id]
        self.assertIn("/my/payment-requests", body)
        self.assertIn("12:00 m.", body)
        self.supplier.portal_invoice_enabled = False
        with self.assertRaises(UserError):
            self.supplier.action_spr_send_instructions()

    def test_instructions_qweb_report_renders(self):
        """El reporte QWeb del instructivo se genera con compania, corte e
        imagenes incrustadas (DECISIONS.md #69, port de la v17 #52)."""
        report = self.env.ref("supplier_invoice_portal.report_spr_instructions")
        # En modo test Odoo devuelve el HTML en vez de llamar a wkhtmltopdf.
        html = report._render_qweb_html(report.report_name, self.supplier.ids)[0].decode()
        self.assertIn("Portal de proveedores", html)
        self.assertIn("12:00 m.", html)
        self.assertEqual(html.count("data:image/png;base64,"), 9)
        self.assertIn("que le entregó la DIAN", html)

        # Al no obligado a facturar no se le pide el XML y se ofrece cuenta de cobro.
        self.supplier.spr_support_document = True
        html = report._render_qweb_html(report.report_name, self.supplier.ids)[0].decode()
        self.assertNotIn("que le entregó la DIAN", html)
        self.assertIn("Cuenta de cobro", html)

    def test_instructions_email_adjunta_reporte_y_guia(self):
        # DECISIONS.md #74: el asistente se abre con el instructivo QWeb y la
        # guia estatica. Con default_attachment_ids el reporte no llegaba.
        composer = self._instructions_composer()
        self.assertEqual(len(composer.attachment_ids), 2, "reporte + guia")
        guide = self._instructions_guide(composer)
        self.assertEqual(len(guide), 1)
        self.assertEqual(guide.type, "binary")
        self.assertTrue(base64.b64decode(guide.datas).startswith(b"%PDF"),
                        "la guia es un PDF real")
        self.assertEqual(guide.res_model, "mail.compose.message")
        self.assertEqual(guide.res_id, 0)
        report = composer.attachment_ids - guide
        self.assertTrue(report.name.startswith("Instructivo portal de proveedores"),
                        report.name)

    def test_instructions_email_reutiliza_la_guia(self):
        # Dos clics seguidos usan la misma fila: no se acumulan copias de
        # un PDF de mas de 1 MB en ir.attachment.
        name = os.path.basename(res_partner.SPR_INSTRUCTIONS_PDF)
        first = self._instructions_guide(self._instructions_composer())
        second = self._instructions_guide(self._instructions_composer())
        self.assertEqual(first, second, "los dos clics enlazan la misma attachment")
        attachments = self.env["ir.attachment"].search([
            ("res_model", "=", "mail.compose.message"),
            ("res_id", "=", 0),
            ("name", "=", name),
        ])
        self.assertEqual(len(attachments), 1)

    def test_instructions_email_actualiza_la_guia_si_cambia_en_disco(self):
        # Si se reemplaza el PDF del modulo, el proximo clic refresca el
        # adjunto (otro checksum) sin cambiar el id enlazado.
        first = self._instructions_guide(self._instructions_composer())
        nuevo = b"%PDF-1.4 guia actualizada en disco"
        with patch.object(res_partner, "file_open", self._guide_file_open(nuevo)):
            second = self._instructions_guide(self._instructions_composer())
        self.assertEqual(second, first, "se reutiliza la misma fila")
        self.assertEqual(base64.b64decode(first.datas), nuevo)

    def test_instructions_email_envio_lleva_los_dos_pdf(self):
        # El flujo completo: asistente -> action_send_mail -> el mensaje
        # publicado en la ficha del proveedor se lleva reporte y guia.
        composer = self._instructions_composer()
        composer.action_send_mail()
        message = self.env["mail.message"].search([
            ("model", "=", "res.partner"),
            ("res_id", "=", self.supplier.id),
        ], order="id desc", limit=1)
        self.assertTrue(message, "el instructivo publica el mensaje")
        self.assertEqual(len(message.attachment_ids), 2, "el mensaje lleva los dos PDF")
        name = os.path.basename(res_partner.SPR_INSTRUCTIONS_PDF)
        self.assertIn(name, message.attachment_ids.mapped("name"))

    def test_instructions_email_sin_guia_en_disco(self):
        # Sin el archivo no se rompe el envio: se abre solo con el reporte y
        # se loguea.
        with patch.object(res_partner, "file_open", self._guide_file_open(FileNotFoundError)):
            composer = self._instructions_composer()
        self.assertEqual(len(composer.attachment_ids), 1, "solo el reporte")
        self.assertFalse(self._instructions_guide(composer))


class TestCutoff(BaseCase):
    """Funciones puras del cierre de fin de mes: sin base de datos."""

    def test_colombian_holidays_2026(self):
        holidays = cutoff.colombian_holidays(2026)
        self.assertEqual(len(holidays), 18)
        for day in (date(2026, 1, 12), date(2026, 4, 3), date(2026, 6, 29),
                    date(2026, 8, 17), date(2026, 11, 16)):
            self.assertIn(day, holidays)

    def test_last_business_day_skips_weekend_and_holiday(self):
        # 31 de octubre de 2026 es sabado.
        self.assertEqual(cutoff.last_business_day(2026, 10), date(2026, 10, 30))
        # 30 de junio de 2025 es lunes festivo (San Pedro y Sagrado Corazon).
        self.assertEqual(cutoff.last_business_day(2025, 6), date(2025, 6, 27))

    def test_radication_closed_from_noon_bogota(self):
        # 30 de septiembre de 2026, ultimo dia habil. Bogota es UTC-5.
        closed, moment, reopen = cutoff.radication_closed(datetime(2026, 9, 30, 16, 59))
        self.assertFalse(closed)
        self.assertEqual(moment, datetime(2026, 9, 30, 12, 0))
        self.assertEqual(reopen, date(2026, 10, 1))
        self.assertTrue(cutoff.radication_closed(datetime(2026, 9, 30, 17, 0))[0])
        # 1 de octubre, 00:30 en Bogota: abre de nuevo.
        self.assertFalse(cutoff.radication_closed(datetime(2026, 10, 1, 5, 30))[0])
        # Fin de semana despues del ultimo dia habil: sigue cerrado.
        self.assertTrue(cutoff.radication_closed(datetime(2026, 10, 31, 15, 0))[0])
        # Otra hora de corte.
        self.assertFalse(cutoff.radication_closed(datetime(2026, 9, 30, 17, 0), cutoff_hour=15.5)[0])

    def test_parse_amount(self):
        parse = SupplierInvoicePortal._spr_parse_amount
        self.assertEqual(parse("1.547.000"), 1547000.0)
        self.assertEqual(parse("$ 1.547.000,50"), 1547000.5)
        self.assertEqual(parse("1,547,000.50"), 1547000.5)
        self.assertEqual(parse("1500,5"), 1500.5)
        self.assertEqual(parse("1.500"), 1500.0)
        self.assertIsNone(parse("abc"))
