# -*- coding: utf-8 -*-
"""Revision de las solicitudes en el backend (DECISIONS.md #49) y ajustes de 19.

- Una actividad por validador, incluidos los que llegan al grupo por herencia
  (en 19 ``res.groups.user_ids`` solo trae los explicitos).
- Sin duplicados al revalidar.
- "Tomar revision" y la toma automatica al trabajar la solicitud.
- Crear la factura, rechazar o cancelar cierran las actividades de revision.
- Analitica en las notas (DECISIONS.md #52) y precision de la cantidad.
"""

from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.supplier_invoice_portal.services import validation_rules

from .common import SprCase


@tagged("post_install", "-at_install")
class TestReview(SprCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")

        def make_user(login, name, group_xmlid):
            return cls.env["res.users"].create({
                "name": name,
                "login": login,
                "email": "%s@example.com" % login,
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
                "group_ids": [(6, 0, [group_user.id, cls.env.ref(group_xmlid).id])],
            })

        # Solo Responsable: es validador porque Responsable implica Validador.
        cls.manager = make_user("spr_manager", "Responsable SPR",
                                "supplier_invoice_portal.group_spr_manager")
        # Solo Compras: administrador, que implica Responsable (security.xml).
        cls.buyer = make_user("spr_buyer", "Jefe de compras",
                              "purchase.group_purchase_manager")

    def _open_review(self, request):
        return request._review_activities()

    def _count(self, request, user):
        return len(self._open_review(request).filtered(lambda act: act.user_id == user))

    def _validated(self, order=None):
        request = self._create_request(order or self._standard_po())
        request.action_validate()
        self.assertEqual(request.state, "approved", request.validation_summary)
        return request

    # ------------------------------------------------------------------
    # Actividades
    # ------------------------------------------------------------------

    def test_one_activity_per_validator_including_inherited(self):
        request = self._validated()
        users = self._open_review(request).user_id
        for user in (self.validator, self.manager, self.buyer):
            self.assertIn(user, users)
            self.assertEqual(self._count(request, user), 1)
        # El admin y el superusuario estan en el grupo por los datos del
        # modulo: con otros validadores, no reciben la actividad.
        self.assertNotIn(self.env.ref("base.user_admin"), users)
        self.assertNotIn(self.env.ref("base.user_root"), users)
        self.assertFalse(users.filtered("share"))
        # Las actividades no dejan a los validadores de seguidores (M1).
        self.assertFalse(request._follower_partners() & users.partner_id)

    def test_validator_of_another_company_gets_no_activity(self):
        other_company = self.env["res.company"].create({"name": "Otra compania SPR"})
        outsider = self.env["res.users"].create({
            "name": "Validador de otra compania",
            "login": "spr_outsider",
            "company_id": other_company.id,
            "company_ids": [(6, 0, other_company.ids)],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("supplier_invoice_portal.group_spr_validator").id,
            ])],
        })
        request = self._validated()
        self.assertNotIn(outsider, self._open_review(request).user_id)
        self.assertIn(self.validator, self._open_review(request).user_id)

    def test_revalidation_does_not_duplicate(self):
        request = self._validated()
        before = self._open_review(request)
        # Como el portal (sin usuario interno que la tome): mismo reparto.
        request.sudo().action_validate()
        request._run_pipeline()
        request._notify_validators()
        self.assertEqual(self._open_review(request), before)

    # ------------------------------------------------------------------
    # Tomar revision
    # ------------------------------------------------------------------

    def test_take_review_closes_the_others(self):
        request = self._validated()
        # La base de tests apaga el tracking (DISABLED_MAIL_CONTEXT) y lo
        # descarta para lo creado en la transaccion hasta el precommit: se
        # vacia el precommit y se prende el tracking para probarlo.
        self.env.flush_all()
        self.env.cr.flush()
        request = request.with_context(tracking_disable=False, mail_notrack=False)
        request.with_user(self.validator).action_take_review()
        self.assertEqual(request.reviewer_id, self.validator)
        self.assertEqual(self._open_review(request).user_id, self.validator)
        self.assertEqual(self._count(request, self.validator), 1)
        # Un solo mensaje interno, ningun "Actividad hecha" por cada validador.
        self.env.invalidate_all()
        notes = request.message_ids.filtered(
            lambda message: "Revision tomada por Validadora" in (message.body or ""))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(request.message_ids.filtered("mail_activity_type_id"))
        # Solo el revisor sigue la solicitud entre los validadores.
        followers = request._follower_partners()
        self.assertIn(self.validator.partner_id, followers)
        self.assertFalse(followers & (self.manager | self.buyer).partner_id)

        # Otro la toma encima: no se bloquea y queda trazado (un precommit por
        # cambio, como en dos peticiones distintas).
        self.env.flush_all()
        self.env.cr.flush()
        request.with_user(self.manager).action_take_review()
        self.assertEqual(request.reviewer_id, self.manager)
        self.assertEqual(self._open_review(request).user_id, self.manager)
        followers = request._follower_partners()
        self.assertIn(self.manager.partner_id, followers)
        self.assertNotIn(self.validator.partner_id, followers)
        self.env.flush_all()
        self.env.cr.flush()  # corre el precommit: crea los valores de tracking
        self.env.invalidate_all()
        tracked = request.sudo().message_ids.tracking_value_ids.filtered(
            lambda value: value.field_id.name == "reviewer_id")
        self.assertEqual(len(tracked), 2)

        # Revalidar con revisor asignado no reparte actividades otra vez.
        request.sudo().action_validate()
        self.assertEqual(self._open_review(request).user_id, self.manager)

    def test_revalidation_by_a_user_takes_the_review(self):
        request = self._validated()
        request.with_user(self.buyer).action_validate()
        self.assertEqual(request.reviewer_id, self.buyer)
        self.assertEqual(self._open_review(request).user_id, self.buyer)

    def test_manual_match_takes_the_review(self):
        other = self.env["product.product"].create({
            "name": "Bolsa generica",
            "type": "consu",
            "purchase_method": "purchase",
            "supplier_taxes_id": [(6, 0, self.tax_19.ids)],
        })
        order = self._create_po([(self.product_cafe, 100, 12000.0), (other, 50, 2000.0)])
        request = self._create_request(order)
        request.action_validate()
        self.assertEqual(request.state, "warning")
        self.assertFalse(request.reviewer_id)
        with Form(request.with_user(self.buyer)) as form:
            with form.line_ids.edit(1) as line_form:
                line_form.po_line_id = order.order_line[1]
        self.assertEqual(request.reviewer_id, self.buyer)

    def test_order_line_change_takes_the_review(self):
        """B1: basta cambiar la linea de la orden (sin match_method)."""
        request = self._validated()
        line = request.line_ids[:1]
        line.with_user(self.buyer).write({"po_line_id": line.po_line_id.id})
        self.assertEqual(request.reviewer_id, self.buyer)

    def test_automatic_matching_does_not_take_the_review(self):
        request = self._validated()  # validado por un usuario interno, en borrador
        self.assertFalse(request.reviewer_id)

    def test_revalidation_rejected_closes_activities(self):
        """B6: una revalidacion rechazada no deja nada por revisar."""
        request = self._validated()
        self.assertTrue(self._open_review(request))
        self.supplier.vat = "800999888-1"
        request.sudo().action_validate()
        self.assertEqual(request.state, "rejected")
        self.assertFalse(self._open_review(request))

    def test_reject_takes_the_review_and_closes_activities(self):
        request = self._validated()
        request.with_user(self.manager).action_reject(reason="No corresponde.")
        self.assertEqual(request.reviewer_id, self.manager)
        self.assertFalse(self._open_review(request))
        # Solo la actividad de quien rechazo queda como hecha; las demas se borran.
        done = self.env["mail.activity"].with_context(active_test=False).search([
            ("res_model", "=", request._name), ("res_id", "=", request.id),
            ("active", "=", False),
        ])
        self.assertEqual(done.user_id, self.manager)

    def test_cancel_closes_activities(self):
        request = self._validated()
        request.action_cancel()
        self.assertFalse(self._open_review(request))

    def test_create_bill_closes_all_review_activities(self):
        request = self._validated()
        self.assertGreater(len(self._open_review(request)), 1)
        request.action_create_bill()
        self.assertEqual(request.state, "invoiced")
        self.assertFalse(self._open_review(request))
        # El borrador no tiene numero en 19: el chatter no dice "False".
        bodies = " ".join(request.message_ids.mapped(lambda message: str(message.body)))
        # Sin numero, se nombra por la referencia del proveedor.
        self.assertIn("Factura de proveedor en borrador SETP990000001 creada", bodies)
        self.assertNotIn("False", bodies)

    def test_take_review_not_allowed_when_closed(self):
        request = self._validated()
        request.action_create_bill()
        with self.assertRaises(UserError):
            request.with_user(self.validator).action_take_review()

    # ------------------------------------------------------------------
    # Analitica y decimales
    # ------------------------------------------------------------------

    def test_credit_note_keeps_the_order_analytic(self):
        plan = self.env["account.analytic.plan"].create({"name": "Tiendas SPR"})
        account = self.env["account.analytic.account"].create({
            "name": "Tienda Centro", "plan_id": plan.id, "company_id": False,
        })
        order = self._standard_po()
        distribution = {str(account.id): 100.0}
        order.order_line.analytic_distribution = distribution
        invoice_request = self._create_request(order)
        invoice_request.action_validate()
        invoice_request.action_create_bill()
        invoice_request.move_id.action_post()
        # La factura la saca de purchase_line_id (core de 19).
        self.assertEqual(
            invoice_request.move_id.invoice_line_ids[0].analytic_distribution, distribution)

        note = self._create_request(None, xml_name="credit_note.xml", document_type="credit_note")
        note.action_validate()
        self.assertEqual(note.state, "approved", note.validation_summary)
        note.action_create_bill()
        lines = note.move_id.invoice_line_ids
        self.assertFalse(lines.purchase_line_id)
        self.assertTrue(lines)
        for line in lines:
            self.assertEqual(line.analytic_distribution, distribution)

    def test_templates_use_their_own_recipients(self):
        """En 19 use_default_to viene en True e ignora partner_to (#60)."""
        templates = self.env["mail.template"].search([
            ("id", "in", [self.env.ref("supplier_invoice_portal.%s" % name).id for name in (
                "mail_template_spr_received", "mail_template_spr_auto_rejected",
                "mail_template_spr_rejected", "mail_template_spr_invoiced",
                "mail_template_spr_instructions")]),
        ])
        self.assertEqual(len(templates), 5)
        self.assertFalse(any(templates.mapped("use_default_to")))

    def test_quantities_in_colombian_format(self):
        from ..services.validation_rules import _number
        self.assertEqual(_number(1234.5), "1.234,50")
        self.assertEqual(_number(50, 0), "50")

    def test_bill_form_shows_the_supplier_cufe(self):
        """El arch combinado de la factura (con o sin Jorels) valida y trae el
        CUFE con copiar y el enlace a la DIAN (DECISIONS.md #55)."""
        from lxml import etree
        views = self.env["account.move"].get_views([(False, "form"), (False, "search")])
        form = etree.fromstring(views["views"]["form"]["arch"])
        cufe = form.xpath("//group[@id='header_left_group']//field[@name='cufe']")
        self.assertEqual(len(cufe), 1)
        self.assertEqual(cufe[0].get("widget"), "CopyClipboardChar")
        link = form.xpath("//field[@name='spr_cufe_dian_url']")
        self.assertEqual(link[0].get("widget"), "url")
        self.assertEqual(link[0].get("text"), "Consultar en la DIAN")
        self.env.ref("account.view_account_invoice_filter")  # existe en 19
        search = etree.fromstring(
            self.env["account.move"].get_views(
                [(self.env.ref("account.view_account_invoice_filter").id, "search")]
            )["views"]["search"]["arch"])
        self.assertTrue(search.xpath("//field[@name='cufe']"))

        request = self._validated()
        request.action_create_bill()
        move = request.move_id
        self.assertTrue(move.cufe)
        self.assertEqual(
            move.spr_cufe_dian_url,
            "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=%s" % move.cufe)

    def test_amounts_in_findings_use_colombian_format(self):
        """$ 1.547.000,00 y no 1,547,000.00 (DECISIONS.md #56)."""
        request = self._create_request(self._standard_po())
        text = validation_rules._money(1547000.0, request)
        self.assertIn("1.547.000,00", text)
        self.assertIn(request.currency_id.symbol, text)
        # En un hallazgo real: la orden pide 60 kg y la factura cobra 100.
        order = self._create_po([(self.product_cafe, 60, 12000.0), (self.product_bag, 50, 2000.0)])
        request = self._create_request(order)
        request.action_validate()
        self.assertIn("1.547.000,00", request.validation_summary)
        self.assertNotIn("1,547,000.00", request.validation_summary)

    def test_quantity_uses_the_product_unit_precision(self):
        field = self.env["supplier.payment.request.line"]._fields["quantity"]
        precision = self.env.ref("uom.decimal_product_uom")
        # Con el nombre viejo ("Product Unit of Measure") precision_get caia en
        # 2 en silencio: el nombre tiene que existir.
        self.assertEqual(field._digits, precision.name)
        precision.digits = 3
        self.assertEqual(field.get_digits(self.env), (16, 3))
        request = self._create_request(self._standard_po())
        line = self.env["supplier.payment.request.line"].create({
            "request_id": request.id, "description": "Cafe", "quantity": 12.3456,
        })
        self.assertAlmostEqual(line.quantity, 12.346, places=6)

    def test_draft_bill_label_never_says_false(self):
        request = self._validated()
        request.action_create_bill()
        self.assertFalse(request.move_id.name)
        self.assertEqual(validation_rules.move_label(request.move_id), "SETP990000001")
        request.move_id.ref = False
        label = validation_rules.move_label(request.move_id)
        self.assertTrue(label)
        self.assertNotEqual(label, "False")
