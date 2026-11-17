import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DISCOUNT_FIELDS = [
    "discount_program_id",
    "discount_name",
    "discount_code",
    "discount_amount",
    "discount_vigencia",
    "discount_doc_type",
    "discount_doc_number",
    "discount_redeem_date",
]

DISCOUNT_DOC_TYPES = [
    ("nit", "NIT"),
    ("cc", "Cédula de ciudadanía"),
    ("ti", "Tarjeta de Identidad"),
    ("te", "Tarjeta de extranjería"),
    ("ce", "Cédula de extranjería"),
    ("passport", "Pasaporte"),
    ("niup", "NIUP"),
    ("external_id", "Nit de otro país"),
]

NUMERIC_DOC_TYPES = {"nit", "cc", "ti", "te", "ce", "niup"}


class PosOrder(models.Model):
    _inherit = "pos.order"

    discount_program_id = fields.Many2one(
        "loyalty.program",
        string="Programa de descuento",
        copy=False,
        ondelete="set null",
    )
    discount_name = fields.Char(string="Nombre del descuento", copy=False)
    discount_code = fields.Char(string="Código de descuento", copy=False)
    # Calculado en el servidor desde las líneas de recompensa reales de la
    # orden: el valor que envía el POS se ignora porque queda desactualizado
    # si el cajero cambia cantidades o productos después de aplicar el código.
    discount_amount = fields.Monetary(
        string="Valor del descuento",
        copy=False,
        currency_field="currency_id",
        compute="_compute_discount_amount",
        store=True,
        readonly=True,
    )
    # Estado del bono en la fecha del canje (almacenado).
    discount_state = fields.Selection(
        [("vigente", "Vigente"), ("vencido", "Vencido")],
        string="Estado al canjear",
        compute="_compute_discount_state",
        store=True,
        copy=False,
    )
    discount_vigencia = fields.Date(string="Fecha de vigencia", copy=False)
    discount_doc_type = fields.Selection(
        DISCOUNT_DOC_TYPES,
        string="Tipo de documento",
        copy=False,
    )
    discount_doc_number = fields.Char(string="Número de documento", copy=False)
    discount_redeem_date = fields.Datetime(string="Fecha de canje", copy=False)

    @api.depends("discount_code", "discount_vigencia", "discount_redeem_date")
    def _compute_discount_state(self):
        for order in self:
            if not order.discount_code:
                order.discount_state = False
                continue
            if not order.discount_vigencia or not order.discount_redeem_date:
                order.discount_state = "vigente"
                continue
            # La fecha de canje está en UTC: se pasa al día local del cajero
            # para compararla con la vigencia (que es una fecha, sin hora).
            tz = order.user_id.tz or order.env.context.get("tz") or order.env.user.tz
            redeem_day = fields.Date.context_today(
                order.with_context(tz=tz), order.discount_redeem_date
            )
            order.discount_state = (
                "vencido" if order.discount_vigencia < redeem_day else "vigente"
            )

    @api.depends("discount_program_id", "lines.reward_id", "lines.price_subtotal_incl")
    def _compute_discount_amount(self):
        for order in self:
            program = order.discount_program_id
            if not program:
                order.discount_amount = 0.0
                continue
            reward_lines = order.lines.filtered(
                lambda line: line.reward_id and line.reward_id.program_id == program
            )
            amount = abs(sum(reward_lines.mapped("price_subtotal_incl")))
            order.discount_amount = order.currency_id.round(amount) if order.currency_id else amount

    @api.model
    def _process_order(self, order, existing_order):
        # En Odoo 19 el POS envía los campos de la orden y el core los pasa
        # directo a create()/write(): los del canje se sanean antes.

        self._sanitize_discount_code_vals(order)
        return super()._process_order(order, existing_order)

    @api.model
    def _sanitize_discount_code_vals(self, order):
        """Deja en ``order`` solo valores del canje que se puedan guardar.

        Revisa el formato; si el bono quedó aplicado de verdad se decide
        después, contra las líneas ya guardadas (``_process_saved_order``).
        Nunca lanza error: un dato inválido no debe impedir que la orden se
        sincronice.
        """
        # Calculados en el servidor: lo que mande el POS se ignora.
        order.pop("discount_amount", None)
        order.pop("discount_state", None)
        if "discount_code" not in order:
            return
        code = (order.get("discount_code") or "").strip()
        program_id = order.get("discount_program_id")
        program = self.env["loyalty.program"]
        if code and isinstance(program_id, int) and not isinstance(program_id, bool):
            program = program.sudo().browse(program_id).exists()
        if not program:
            order.update({field: False for field in DISCOUNT_FIELDS if field != "discount_amount"})
            return
        doc_type = order.get("discount_doc_type")
        if doc_type not in dict(DISCOUNT_DOC_TYPES):
            doc_type = False
        order.update({
            "discount_program_id": program.id,
            "discount_name": program.name,
            "discount_code": code,
            "discount_vigencia": program.date_to or False,
            "discount_doc_type": doc_type,
            "discount_doc_number": self._clean_doc_number(doc_type, order.get("discount_doc_number")),
            "discount_redeem_date": self._parse_discount_redeem_date(order),
        })

    def _process_saved_order(self, draft):
        # Las líneas ya están guardadas y la orden todavía no se pasó a
        # pagada (eso lo hace super): el canje se valida contra las líneas reales.
        # Solo al cobrar. En 19 la respuesta de sync_from_ui pisa la orden de la
        # caja: si se limpiara un borrador enviado a cocina antes de llegar a la
        # compra mínima, el canje se perdería y la orden se cobraría con el
        # descuento pero sin documento.
        if not draft:
            self._check_discount_code_applied()
        return super()._process_saved_order(draft)

    def _check_discount_code_applied(self):
        """Limpia el canje si el bono no quedó aplicado de verdad.

        En Odoo 19 el POS solo envía las líneas nuevas o modificadas: la línea
        de recompensa de una orden ya sincronizada no viene en los datos, por
        eso se revisan las líneas guardadas y no lo que llegó del POS.
        """
        for order in self:
            if not order.discount_code:
                continue
            if order._discount_applied_program(order.discount_program_id, order.discount_code, order.lines):
                continue
            order.with_context(pos_discount_code_clear=True).write(
                {field: False for field in DISCOUNT_FIELDS if field != "discount_amount"}
            )

    @api.model
    def _discount_applied_program(self, program, code, lines):
        """El programa, si el código es suyo y las líneas traen una recompensa de ese programa."""
        program = program.sudo().exists()
        if not program or program not in lines.sudo().reward_id.program_id:
            return self.env["loyalty.program"]
        code_is_rule = code in program.rule_ids.filtered(lambda r: r.mode == "with_code").mapped("code")
        code_is_card = code_is_rule or bool(
            self.env["loyalty.card"].sudo().search_count(
                [("code", "=", code), ("program_id", "=", program.id)], limit=1
            )
        )
        return program if code_is_card else self.env["loyalty.program"]

    @api.model
    def _parse_discount_redeem_date(self, ui_order):
        """El POS envía la fecha en UTC; si falta o no es válida se usa la de la orden."""
        for value in (ui_order.get("discount_redeem_date"), ui_order.get("date_order")):
            if not value:
                continue
            try:
                return fields.Datetime.to_datetime(str(value).replace("T", " ")[:19])
            except ValueError:
                continue
        return fields.Datetime.now()

    @api.model
    def _clean_doc_number(self, doc_type, doc_number):
        """Quita espacios, puntos y guiones en los tipos numéricos; nunca lanza error."""
        doc_number = (doc_number or "").strip()
        if doc_type in NUMERIC_DOC_TYPES:
            doc_number = re.sub(r"[\s.\-]", "", doc_number)
        return doc_number or False

    def write(self, vals):
        if any(field in vals for field in DISCOUNT_FIELDS):
            # El POS crea la orden ya pagada al cobrar: solo se permite que
            # _check_discount_code_applied limpie un canje inválido.
            clearing = self.env.context.get("pos_discount_code_clear") and not any(
                vals.get(field) for field in DISCOUNT_FIELDS)
            if not clearing and any(order.state != "draft" for order in self):
                raise UserError(
                    _("Las órdenes validadas no permiten modificar los datos de descuento.")
                )
        return super().write(vals)
