# -*- coding: utf-8 -*-
"""Revision de las solicitudes en el backend (DECISIONS.md #49) y ajustes de 19.

- Una actividad por validador, incluidos los que llegan al grupo por herencia
  (en 19 ``res.groups.user_ids`` solo trae los explicitos).
- Sin duplicados al revalidar.
- "Tomar revision" y la toma automatica al trabajar la solicitud.
- Crear la factura, rechazar o cancelar cierran las actividades de revision.
- Analitica en las notas (DECISIONS.md #52) y precision de la cantidad.
- Aprobacion manual y eventos RADIAN de receptor (DECISIONS.md #71 y #72).
"""

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
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

    def _radian_skip_if_no_jorels(self):
        if "l10n_co_edi_jorels.radian" not in self.env:
            self.skipTest("Jorels no instalado")

    def _radian_ensure_sequences(self):
        # Las secuencias RADIAN de Jorels nacen para la empresa principal; el
        # test usa otra, asi que se replican aqui (action_post las exige).
        for code in ("030", "032", "033"):
            sequence_code = "radian_%s_supplier" % code
            if not self.env["ir.sequence"].search([
                    ("code", "=", sequence_code),
                    ("company_id", "=", self.company.id)], limit=1):
                self.env["ir.sequence"].create({
                    "name": sequence_code,
                    "code": sequence_code,
                    "prefix": "E%s" % code,
                    "padding": 1,
                    "company_id": self.company.id,
                })

    def _radian_supplier_events(self, move):
        return self.env["l10n_co_edi_jorels.radian"].sudo().search([
            ("move_id", "=", move.id), ("type", "=", "supplier")])

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

    def _warning_request(self):
        other = self.env["product.product"].create({
            "name": "Bolsa generica", "type": "consu",
            "purchase_method": "purchase",
            "supplier_taxes_id": [(6, 0, self.tax_19.ids)],
        })
        order = self._create_po([(self.product_cafe, 100, 12000.0), (other, 50, 2000.0)])
        request = self._create_request(order)
        request.action_validate()
        self.assertEqual(request.state, "warning")
        return request

    def test_approve_by_hand_overrides_warning(self):
        """DECISIONS.md #71: el Responsable aprueba a mano una solicitud con observaciones."""
        request = self._warning_request()
        self.assertFalse(request.approved_by_id)

        request.with_user(self.manager).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.manager)
        self.assertTrue(request.approved_date)
        bodies = " ".join(request.message_ids.mapped(lambda message: str(message.body)))
        self.assertIn("Aprobada a mano", bodies)

        # Solo aplica a solicitudes con observaciones.
        draft = self._create_request(self._standard_po())
        with self.assertRaises(UserError):
            draft.action_approve()

    def test_approve_not_allowed_from_validating(self):
        """DECISIONS.md #71: en validacion no hay hallazgos que aprobar."""
        request = self._create_request(self._standard_po())
        request.write({"state": "validating"})
        with self.assertRaises(UserError):
            request.with_user(self.manager).action_approve()
        self.assertEqual(request.state, "validating")
        self.assertFalse(request.approved_by_id)

    def test_approve_requires_the_manager_group(self):
        """DECISIONS.md #71: un validador sin el grupo Responsable no aprueba a mano."""
        request = self._warning_request()
        with self.assertRaises(AccessError):
            request.with_user(self.validator).action_approve()
        self.assertEqual(request.state, "warning")
        self.assertFalse(request.approved_by_id)

    def test_manual_approval_is_cleared_by_reset_and_revalidation(self):
        """DECISIONS.md #71: revalidar o volver a borrador descarta la aprobacion."""
        request = self._warning_request()
        request.with_user(self.manager).action_approve()
        self.assertTrue(request.approved_by_id)
        request.action_validate()
        self.assertEqual(request.state, "warning", "las reglas vuelven a dejar observaciones")
        self.assertFalse(request.approved_by_id)
        self.assertFalse(request.approved_date)

        request.with_user(self.manager).action_approve()
        self.assertTrue(request.approved_by_id)
        request.action_reset_to_draft()
        self.assertEqual(request.state, "draft")
        self.assertFalse(request.approved_by_id)
        self.assertFalse(request.approved_date)

    def test_converted_price_is_not_rounded_to_the_currency(self):
        """DECISIONS.md #74: con factor 12 sobre un subtotal de 100.000 el
        precio convertido no se redondea y la linea de la factura da 100.000."""
        order = self._create_po([
            (self.product_cafe, 100, 12000.0),
            (self.product_bag, 600, 2000.0 / 12),
        ])
        request = self._create_request(order)
        request.action_validate()
        bag = request.line_ids.filtered(lambda line: line.product_code == "EMP-500")
        self.assertEqual(bag.subtotal, 100000.0)
        bag.write({"uom_factor": 12.0, "match_method": "manual"})
        request.action_validate()
        self.assertIn(request.state, ("approved", "warning"), request.validation_summary)
        bag = request.line_ids.filtered(lambda line: line.product_code == "EMP-500")
        self.assertAlmostEqual(bag.po_price_unit, 2000.0 / 12, places=6)
        request.action_create_bill()
        bill_line = request.move_id.invoice_line_ids.filtered(
            lambda line: line.product_id == self.product_bag)
        self.assertEqual(bill_line.quantity, 600.0)
        self.assertEqual(bill_line.discount, 0.0)
        self.assertEqual(bill_line.price_subtotal, 100000.0)

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

    # ------------------------------------------------------------------
    # Eventos RADIAN de receptor (DECISIONS.md #72)
    # ------------------------------------------------------------------

    def _radian_class(self):
        return type(self.env["l10n_co_edi_jorels.radian"])

    def _radian_bill(self, post=True, enable_journal=True):
        """Factura de proveedor con CUFE y fecha, en un diario habilitado."""
        self._radian_skip_if_no_jorels()
        self._radian_ensure_sequences()
        request = self._validated()
        request.action_create_bill()
        move = request.move_id
        self.assertTrue(move.cufe and move.invoice_date)
        move.journal_id.spr_radian_enabled = enable_journal
        if post:
            move.action_post()
        return move

    def _radian_offline(self):
        """Sin red: los prechequeos de compania y firmante se prueban aparte y
        la validacion ante la DIAN no sale (el mock cuenta las llamadas)."""
        return (
            patch.object(type(self.env["account.move"]),
                         "_spr_radian_missing_requirements", return_value=[]),
            patch.object(self._radian_class(), "validate_dian", autospec=True),
        )

    def _can_generate(self, move):
        move.invalidate_recordset(["spr_radian_can_generate"])
        return move.spr_radian_can_generate

    def test_radian_button_creates_the_three_events(self):
        """El boton crea, publica y valida 030, 032 y 033 y luego se oculta."""
        move = self._radian_bill()
        self.assertFalse(move.ei_uuid)
        self.assertTrue(self._can_generate(move))

        requirements, validate = self._radian_offline()
        with requirements, validate as validate_dian:
            action = move.action_spr_generate_radian_events()
        self.assertEqual(move.ei_uuid, move.cufe, "cufe se puentea a ei_uuid")
        events = self._radian_supplier_events(move)
        self.assertEqual(len(events), 3)
        self.assertEqual(set(events.mapped("event_id.code")), {"030", "032", "033"})
        self.assertEqual(set(events.mapped("state")), {"posted"})
        self.assertEqual(events.user_id, self.env.user)
        self.assertEqual(events.company_id, move.company_id)
        # La compania de pruebas tiene el estado intermedio de Jorels: se
        # valida aqui, una vez por evento.
        self.assertTrue(move.company_id.enable_validate_state)
        self.assertEqual(validate_dian.call_count, 3)
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertFalse(action["params"]["sticky"])
        bodies = " ".join(move.message_ids.mapped(lambda m: str(m.body)))
        self.assertIn("generados y validados", bodies)
        # Ya tiene eventos: el boton desaparece y la accion no repite.
        self.assertFalse(self._can_generate(move))
        with self.assertRaises(UserError):
            move.action_spr_generate_radian_events()
        self.assertEqual(len(self._radian_supplier_events(move)), 3)

    def test_radian_button_hidden_in_draft(self):
        move = self._radian_bill(post=False)
        self.assertEqual(move.state, "draft")
        self.assertFalse(self._can_generate(move))
        with self.assertRaises(UserError):
            move.action_spr_generate_radian_events()
        self.assertFalse(self._radian_supplier_events(move))

    def test_radian_button_hidden_without_cufe(self):
        move = self._radian_bill()
        move.write({"cufe": False})
        self.assertFalse(self._can_generate(move))
        # ei_uuid no cuenta: en documento soporte guarda nuestro CUDS.
        move.sudo().ei_uuid = "a" * 96
        self.assertFalse(self._can_generate(move))
        with self.assertRaises(UserError):
            move.action_spr_generate_radian_events()

    def test_radian_button_hidden_without_invoice_date(self):
        move = self._radian_bill()
        # Una factura publicada no deja borrar la fecha por el ORM.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_move SET invoice_date = NULL WHERE id = %s", [move.id])
        move.invalidate_recordset()
        self.assertFalse(self._can_generate(move))
        with self.assertRaises(UserError):
            move.action_spr_generate_radian_events()

    def test_radian_button_hidden_on_supplier_credit_notes(self):
        """Los eventos 030-033 son de la factura: la nota credito no los lleva."""
        self._radian_skip_if_no_jorels()
        invoice_request = self._validated()
        invoice_request.action_create_bill()
        invoice_request.move_id.journal_id.spr_radian_enabled = True
        invoice_request.move_id.action_post()
        note = self._create_request(None, xml_name="credit_note.xml", document_type="credit_note")
        note.action_validate()
        note.action_create_bill()
        refund = note.move_id
        self.assertEqual(refund.move_type, "in_refund")
        refund.action_post()
        self.assertTrue(refund.cufe and refund.invoice_date)
        self.assertTrue(refund.journal_id.spr_radian_enabled)
        self.assertFalse(self._can_generate(refund))
        with self.assertRaises(UserError):
            refund.action_spr_generate_radian_events()

    def test_radian_button_needs_an_enabled_journal(self):
        """Solo en diarios marcados: un diario de compras sin marcar no
        muestra el boton; al marcarlo, si."""
        move = self._radian_bill(enable_journal=False)
        self.assertFalse(move.journal_id.spr_radian_enabled)
        self.assertFalse(self._can_generate(move))
        with self.assertRaisesRegex(UserError, "no esta habilitado para eventos RADIAN"):
            move.action_spr_generate_radian_events()
        move.journal_id.spr_radian_enabled = True
        self.assertTrue(self._can_generate(move))

    def test_radian_button_hidden_on_support_document_journal(self):
        """Documento soporte (resolucion tipo 12) es guarda dura aunque el
        diario este marcado: se simula porque el test no arma la resolucion."""
        move = self._radian_bill()
        self.assertTrue(self._can_generate(move))
        with patch.object(type(self.env["account.journal"]),
                          "_spr_is_support_document_journal", return_value=True):
            self.assertFalse(self._can_generate(move))
            with self.assertRaises(UserError):
                move.action_spr_generate_radian_events()

    def test_radian_button_hidden_when_events_exist(self):
        """Si ya hay eventos (p. ej. creados a mano en Jorels), no se duplica."""
        move = self._radian_bill()
        event = self.env["l10n_co_edi_jorels.events"].sudo().search([("code", "=", "030")], limit=1)
        self.env["l10n_co_edi_jorels.radian"].sudo().create({
            "move_id": move.id, "event_id": event.id, "type": "supplier",
            "user_id": self.env.user.id,
        })
        self.assertFalse(self._can_generate(move))
        with self.assertRaises(UserError):
            move.action_spr_generate_radian_events()
        self.assertEqual(len(self._radian_supplier_events(move)), 1)

    def test_radian_button_in_the_bill_header(self):
        """El boton va en el encabezado del formulario, no en el engranaje."""
        from lxml import etree
        arch = etree.fromstring(
            self.env["account.move"].get_views([(False, "form")])["views"]["form"]["arch"])
        button = arch.xpath("//header/button[@name='action_spr_generate_radian_events']")
        self.assertEqual(len(button), 1)
        self.assertEqual(button[0].get("invisible"), "not spr_radian_can_generate")
        self.assertFalse(self.env["ir.actions.server"].search([
            ("binding_model_id.model", "=", "account.move"),
            ("code", "ilike", "action_spr_generate_radian_events"),
        ]))
        journal_arch = etree.fromstring(
            self.env["account.journal"].get_views([(False, "form")])["views"]["form"]["arch"])
        self.assertTrue(journal_arch.xpath("//field[@name='spr_radian_enabled']"))

    def test_radian_journal_constraint(self):
        """Solo diarios de compras que no sean de documento soporte."""
        self._radian_skip_if_no_jorels()
        sale = self.company_data["default_journal_sale"]
        with self.assertRaises(ValidationError):
            sale.spr_radian_enabled = True
        purchase = self.company_data["default_journal_purchase"]
        with patch.object(type(purchase), "_spr_is_support_document_journal", return_value=True):
            with self.assertRaises(ValidationError):
                purchase.spr_radian_enabled = True
        purchase.spr_radian_enabled = True
        self.assertTrue(purchase.spr_radian_enabled)

    def test_radian_requires_company_and_signer_data(self):
        """Lo que Jorels exige y hoy falla tarde se avisa antes de numerar."""
        move = self._radian_bill()
        move.company_id.write({
            "ei_enable": True, "api_key": "token-de-prueba",
            "is_not_test": False, "test_set_id": "set-de-prueba",
        })
        self.env.user.partner_id.function = False
        with self.assertRaisesRegex(UserError, "cargo del usuario firmante"):
            move.action_spr_generate_radian_events()
        self.assertFalse(self._radian_supplier_events(move))

        move.company_id.write({"api_key": False, "test_set_id": False})
        missing = move._spr_radian_missing_requirements()
        self.assertTrue(any("api_key" in item for item in missing))
        self.assertTrue(any("TestSetId" in item for item in missing))

        # El NIT generico de consumidor final no cuenta como documento.
        self.env.user.partner_id.vat = "222222222222"
        missing = move._spr_radian_missing_requirements()
        self.assertTrue(any("consumidor final" in item for item in missing))

    def test_radian_failure_keeps_the_events_already_accepted(self):
        """Si falla el 032, el 030 queda, 032 y 033 no, y no se lanza error:
        un rollback perderia lo que la DIAN ya acepto."""
        move = self._radian_bill()
        original = self._radian_class().action_post

        def action_post(radian):
            if radian.event_id.code == "032":
                raise UserError("DIAN rechazo el recibo del bien")
            return original(radian)

        requirements, validate = self._radian_offline()
        with requirements, validate, patch.object(
                self._radian_class(), "action_post", action_post):
            action = move.action_spr_generate_radian_events()
        events = self._radian_supplier_events(move)
        self.assertEqual(events.event_id.mapped("code"), ["030"])
        self.assertEqual(events.state, "posted")
        self.assertEqual(action["params"]["type"], "warning")
        self.assertTrue(action["params"]["sticky"])
        bodies = " ".join(move.message_ids.mapped(lambda m: str(m.body)))
        self.assertIn("Fallo el evento 032", bodies)
        self.assertIn("DIAN rechazo el recibo del bien", bodies)
        self.assertIn(events.name, bodies)

    def test_radian_edipo_unreachable_gives_a_clear_message(self):
        """Edipo caido: Jorels deja escapar un UnboundLocalError envuelto en un
        UserError en ingles; el chatter dice que no hubo respuesta y no queda
        ningun evento."""
        move = self._radian_bill()

        def action_post(radian):
            # Lo que hace validate_dian_generic cuando requests.post falla.
            try:
                raise UnboundLocalError(
                    "cannot access local variable 'response' where it is not "
                    "associated with a value")
            except UnboundLocalError as error:
                raise UserError("Failed to process the DIAN request for document: %s: %s"
                                % (radian.name, error))

        requirements, validate = self._radian_offline()
        with requirements, validate, patch.object(
                self._radian_class(), "action_post", action_post):
            action = move.action_spr_generate_radian_events()
        self.assertFalse(self._radian_supplier_events(move))
        self.assertEqual(action["params"]["type"], "warning")
        bodies = " ".join(move.message_ids.mapped(lambda m: str(m.body)))
        self.assertIn("No hubo respuesta del servicio de facturacion electronica", bodies)
        self.assertIn("vuelva a pulsar 'Generar eventos RADIAN'", bodies)
        self.assertNotIn("local variable", bodies)
        self.assertTrue(self._can_generate(move))

    def test_radian_production_rejection_is_rolled_back(self):
        """En produccion, un evento que la DIAN no valida (Jorels con
        ei_always_validate no lanza) se revierte y no se siguen los demas."""
        move = self._radian_bill()
        # Por SQL: el write de Jorels sobre is_not_test llama a la API de Edipo.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE res_company SET is_not_test = TRUE WHERE id = %s", [move.company_id.id])
        move.company_id.invalidate_recordset(["is_not_test"])
        requirements, validate = self._radian_offline()
        with requirements, validate:  # validate_dian no marca edi_is_valid
            action = move.action_spr_generate_radian_events()
        self.assertFalse(self._radian_supplier_events(move))
        self.assertEqual(action["params"]["type"], "warning")
        bodies = " ".join(move.message_ids.mapped(lambda m: str(m.body)))
        self.assertIn("Fallo el evento 030", bodies)

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
