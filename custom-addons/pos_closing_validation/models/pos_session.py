import psycopg2

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools import plaintext2html
from odoo.tools.translate import _lt

# Module-level terms must use the lazy translation helper: get_text_alias (`_`)
# resolves the language from the caller frame, which does not exist at import
# time (Odoo logs "no translation language detected" and stores the raw source).
DEFAULT_CASH_DIFFERENCE_BODY = _lt(
    "No puede cerrar esta sesión de Punto de Venta.\n\n"
    "La diferencia de efectivo supera la diferencia máxima autorizada.\n\n"
    "Debe contactar a un responsable del Punto de Venta."
)

BUSY_CASH_MOVE_MESSAGE = _lt(
    "No se pudo registrar el movimiento de efectivo.\n\n"
    "Otro terminal está utilizando la caja en este momento "
    "(probablemente cerrando la sesión).\n\n"
    "Espere unos segundos y vuelva a intentarlo."
)

BUSY_CLOSING_MESSAGE = _lt(
    "No se pudo cerrar la sesión en este momento.\n\n"
    "Otro terminal está utilizando la caja."
)

# Bounded lock waits.  A plain `FOR UPDATE` on pos.session would let a slow
# closing transaction (journal entry, pickings, chatter) hang the second
# terminal's HTTP worker until the request timeout, which leaves the cashier
# unsure whether the movement was recorded and provokes a duplicated attempt.
CASH_MOVE_LOCK_TIMEOUT = "2s"
CLOSING_LOCK_TIMEOUT = "10s"

POS_MANAGER_GROUP = "point_of_sale.group_pos_manager"
POS_USER_GROUP = "point_of_sale.group_pos_user"


class PosSession(models.Model):
    """Extend POS session with Cash In/Out movement limits and closing
    cash difference validation."""

    _inherit = "pos.session"

    rescue_parent_session_id = fields.Many2one(
        "pos.session",
        string="Sesión Padre",
        readonly=True,
        copy=False,
        help="Sesión original que originó esta sesión de rescate.",
    )
    rescue_session_ids = fields.One2many(
        "pos.session",
        "rescue_parent_session_id",
        string="Sesiones de Rescate",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Snapshot: single source of truth for closing validation
    # ------------------------------------------------------------------

    def _get_cash_payment_method(self):
        """Cash payment method used by Odoo to compute the register balance.

        ``_compute_cash_balance`` filters on ``is_cash_count`` (not on
        ``type == 'cash'``); using anything else would make our breakdown
        disagree with the theoretical balance shown by the standard closing
        popup.
        """
        self.ensure_one()
        return self.payment_method_ids.filtered("is_cash_count")[:1]

    def _get_expected_cash(self):
        """Theoretical closing balance.

        Delegates to Odoo's own non-stored compute so there is exactly one
        definition of "expected cash" in the system.  Before 19 a hand rolled
        sum was used, which silently diverged from core whenever an order was
        cancelled/draft (core counts only captured payments) or when a
        statement line was created outside the Cash In/Out popup.
        """
        self.ensure_one()
        return self.cash_register_balance_end

    def _get_cash_sales(self):
        """Cash volume of captured orders, with core's own domain."""
        self.ensure_one()
        cash_pm = self._get_cash_payment_method()
        if not cash_pm:
            return 0.0
        domain = Domain.AND([
            self._get_captured_payments_domain(),
            [("payment_method_id", "=", cash_pm.id)],
        ])
        return self.env["pos.payment"]._read_group(
            domain, aggregates=["amount:sum"]
        )[0][0] or 0.0

    def _get_closing_cash_validation_data(self):
        """Produce the single source of truth for closing validation.

        ``expected_cash`` and ``difference`` come from Odoo's computed fields;
        the breakdown is read with the same domains so that
        ``opening + cash_sales + cash_in - cash_out`` reconciles against the
        expected cash.  ``cash_move_count`` is a different notion: it only
        counts operator-initiated movements (flagged lines), because it feeds
        the per-session limit.
        """
        self.ensure_one()
        config = self.config_id

        opening = self.cash_register_balance_start
        cash_sales = self._get_cash_sales()

        lines = self.sudo().statement_line_ids
        cash_in_lines = lines.filtered(lambda line: line.amount > 0)
        cash_out_lines = lines.filtered(lambda line: line.amount < 0)
        cash_in = sum(cash_in_lines.mapped("amount"))
        cash_out = abs(sum(cash_out_lines.mapped("amount")))

        expected = self._get_expected_cash()
        counted = self.cash_register_balance_end_real or 0.0

        state = self.state
        is_rescue = self.rescue

        has_orders = bool(self.order_ids)

        blockers = self._get_cash_validation_blockers()
        is_manager = self.env.user.has_group(POS_MANAGER_GROUP)
        blocking_reasons = self._get_blocking_reasons()

        return {
            "session_id": self.id,
            "session_name": self.name,
            "state": state,
            "is_rescue": is_rescue,
            "reason": self._get_structural_block_reason_key(),
            "is_manager": is_manager,
            "parent_session_name": (
                self.rescue_parent_session_id.name if is_rescue else False
            ),
            "opening_cash": opening,
            "cash_sales": cash_sales,
            "cash_in": cash_in,
            "cash_in_count": len(cash_in_lines),
            "cash_out": cash_out,
            "cash_out_count": len(cash_out_lines),
            "cash_move_count": self._get_cash_in_out_move_count(),
            "cash_move_limit": config.maximum_cash_in_out_moves,
            "expected_cash": expected,
            "counted_cash": counted,
            "difference": self.cash_register_difference,
            "statement_lines_count": len(lines),
            "orders_count": len(self.order_ids),
            "has_orders": has_orders,
            "can_close": not blocking_reasons,
            "blocking_reasons": blocking_reasons,
            "warnings": [entry["message"] for entry in blockers],
            "pending_rescue": any(
                entry["kind"] == "pending_rescue" for entry in blockers
            ),
        }

    # ------------------------------------------------------------------
    # Cash In / Out helpers
    # ------------------------------------------------------------------

    def _get_cash_in_out_moves(self):
        """Return only statement lines flagged as Cash In/Out movements.

        ``account.bank.statement.line`` is not readable by cashiers, hence the
        sudo; core does the same everywhere it touches session statement lines.
        """
        self.ensure_one()
        return self.sudo().statement_line_ids.filtered("pos_cash_move")

    def _get_cash_in_out_move_count(self):
        """Return the number of Cash In/Out movements in this session."""
        self.ensure_one()
        return len(self._get_cash_in_out_moves())

    def _find_cash_move_by_uuid(self, move_uuid):
        """Statement line already created for this client-generated uuid."""
        self.ensure_one()
        if not move_uuid:
            return self.env["account.bank.statement.line"]
        return self.env["account.bank.statement.line"].sudo().search([
            ("pos_session_id", "=", self.id),
            ("pos_cash_move_uuid", "=", move_uuid),
        ], limit=1)

    def _check_pos_user(self):
        """Mirror the guard core applies to the POS-only RPC entry points."""
        if not self.env.user.has_group(POS_USER_GROUP):
            raise AccessError(_(
                "You don't have the access rights to get the point of sale "
                "cash validation data."
            ))

    def get_cash_in_out_control_data(self):
        """RPC endpoint for the POS Cash In/Out popup: current count and limit.

        The popup keeps its own call (instead of reading a value cached by the
        store) so it stays correct when opened from anywhere else; an
        uninitialised limit would silently allow unlimited movements, which is
        the worst possible failure mode for a cash control.
        """
        self.ensure_one()
        self._check_pos_user()
        return {
            "count": self._get_cash_in_out_move_count(),
            "limit": self.config_id.maximum_cash_in_out_moves,
        }

    def get_closing_validation_info(self):
        """RPC endpoint: returns the closing validation snapshot.

        The frontend uses this to display consistent expected/counted/difference
        data and to detect rescue sessions or sync issues.
        """
        self.ensure_one()
        self._check_pos_user()
        return self._get_closing_cash_validation_data()

    # ------------------------------------------------------------------
    # Validation rules
    # ------------------------------------------------------------------

    def _cash_validation_error(self, kind, message, show_orders_action=False, redirect=False):
        """Uniform answer for the errors this module raises when closing.

        Two keys drive the frontend dialog:

        ``cash_validation``
            Marks the message as ours.  Odoo's ``ClosePosPopup.handleClosingError``
            pairs every unsuccessful answer with a "Cancel Orders" button that
            cancels all non-finalized orders of the terminal and then retries the
            closing.  That is the right escape hatch for draft orders and a data
            loss trap for a cash-difference message, so our messages opt out.

        ``show_orders_action``
            Whether reviewing orders is actually the way out of this error.  It is
            not for internal consistency problems, which become a single
            acknowledgement button.

        The policy lives here, next to the rules that produce it; the client only
        renders it.
        """
        return {
            "successful": False,
            "kind": kind,
            "message": message,
            "redirect": redirect,
            "show_orders_action": show_orders_action,
            "cash_validation": True,
        }

    def _get_cash_validation_blockers(self):
        """Rules that should stop a closing, as ``{'kind', 'message'}`` dicts.

        These are *internal consistency* checks: they detect data that should
        never happen (more movements than the limit, paid orders without
        payments, unresolved rescues).  They block a cashier but only warn a
        manager, because a false positive must never leave a store unable to
        close its register at the end of the day.  The monetary rule
        (``_check_authorized_cash_difference``) is deliberately NOT part of
        this list: it applies to every role.
        """
        self.ensure_one()
        blockers = []

        if not self.rescue and self.config_id.enable_rescue_session_validation:
            rescue_error = self._check_rescue_sessions_pending()
            if rescue_error:
                blockers.append(rescue_error)

        integrity = self._check_cash_in_out_integrity()
        if integrity:
            blockers.append(integrity)

        data_integrity = self._check_session_data_integrity()
        if data_integrity:
            blockers.append(data_integrity)

        return blockers

    def _post_cash_validation_bypass(self, blockers):
        """Audit trail for a manager closing over a consistency warning."""
        for entry in blockers:
            self.message_post(body=plaintext2html(_(
                "Validación de caja superada por un responsable.\n\n"
                "Regla: %(rule)s\n\n%(message)s",
                rule=entry["kind"],
                message=entry["message"],
            )))

    def _get_structural_block_reason(self):
        """Why this session cannot be closed from the POS, whatever the role.

        These are not heuristics: a rescue session has no closing flow in the
        interface (core closes it from the backend), and a session already
        closed or closing must not be closed twice.  Unlike the consistency
        checks above, a manager cannot bypass them.
        """
        key = self._get_structural_block_reason_key()
        if key == "rescue_session":
            return _(
                "Las sesiones de rescate no pueden cerrarse desde el Punto de "
                "Venta. Cierre la sesión desde la vista del backend."
            )
        if key == "session_closed":
            return _("La sesión ya está cerrada.")
        if key == "session_closing_control":
            return _("La sesión ya está en proceso de cierre.")
        return None

    def _get_structural_block_reason_key(self):
        """Stable machine-readable code for the structural block, or ``''``."""
        self.ensure_one()
        if self.rescue:
            return "rescue_session"
        if self.state == "closed":
            return "session_closed"
        if self.state == "closing_control":
            return "session_closing_control"
        return ""

    def _get_blocking_reasons(self):
        """Return the list of messages explaining why this session cannot close.

        Feeds both the backend decision (``_cannot_close_session``) and the
        frontend popup, so the operator and the server can never disagree.
        Empty when the current user may proceed.
        """
        self.ensure_one()
        reasons = []

        structural = self._get_structural_block_reason()
        if structural:
            reasons.append(structural)

        # Consistency checks: a manager may proceed, the decision is audited.
        if not self.env.user.has_group(POS_MANAGER_GROUP):
            reasons.extend(
                entry["message"] for entry in self._get_cash_validation_blockers()
            )

        return reasons

    def _check_cash_in_out_limit(self):
        """Raise UserError if the Cash In/Out limit is reached."""
        self.ensure_one()

        current_count = self._get_cash_in_out_move_count()
        maximum = self.config_id.maximum_cash_in_out_moves

        if current_count >= maximum:
            raise UserError(
                _(
                    "Se alcanzó el límite de movimientos de efectivo.\n\n"
                    "Este Punto de Venta permite un máximo de %(maximum)s "
                    "movimientos Cash In/Out por sesión.\n"
                    "Ya se han registrado %(current)s movimientos.",
                    maximum=maximum,
                    current=current_count,
                )
            )

    def _lock_session_row(self, timeout, busy_message):
        """Take the session row lock with a bounded wait.

        ``SET LOCAL`` keeps the setting inside the current transaction, and the
        savepoint guarantees a lock timeout does not abort the transaction: we
        can still read the movement counter to build an actionable message.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("SET LOCAL lock_timeout = %s", (timeout,))
                self.env.cr.execute(
                    "SELECT id FROM pos_session WHERE id = %s FOR UPDATE",
                    (self.id,),
                )
        except (
            psycopg2.errors.LockNotAvailable,
            psycopg2.errors.QueryCanceled,
        ):
            raise UserError(_(
                "%(base)s\n\n"
                "Movimientos de efectivo registrados hasta ahora: "
                "%(count)s de %(limit)s.\n\n"
                "Verifique ese conteo antes de reintentar, para no registrar "
                "el movimiento dos veces.",
                base=str(busy_message),
                count=self._get_cash_in_out_move_count(),
                limit=self.config_id.maximum_cash_in_out_moves,
            )) from None

    def try_cash_in_out(self, _type, amount, reason, partner_id, extras):
        """Override to enforce the movement limit and identify the movement.

        Cash In/Out movements are not permitted on rescue sessions. The
        user sees a friendly message (POS not synchronized) rather than
        a technical reference to "rescue" to avoid confusing store staff.

        ``extras['cash_move_uuid']`` makes the call idempotent.  The POS queues
        a cash move when the request fails with a connection error and replays
        it later (``data_service.execute`` retries with the very same
        arguments), so a movement whose response was lost would otherwise be
        written twice, silently exceeding the per-session limit.
        """
        self.ensure_one()

        if self.rescue:
            raise UserError(_(
                "El Punto de Venta no está sincronizado con la sesión "
                "actual.\n\n"
                "Actualice la página del Punto de Venta y vuelva a "
                "intentarlo.\n\n"
                "Si el problema persiste, contacte a un administrador."
            ))

        self._lock_session_row(CASH_MOVE_LOCK_TIMEOUT, BUSY_CASH_MOVE_MESSAGE)

        extras = dict(extras or {})
        move_uuid = extras.get("cash_move_uuid")
        if self._find_cash_move_by_uuid(move_uuid):
            # Replay of a movement that was already recorded.
            return True

        self._check_cash_in_out_limit()

        try:
            with self.env.cr.savepoint():
                return super().try_cash_in_out(
                    _type, amount, reason, partner_id, extras
                )
        except psycopg2.errors.UniqueViolation:
            # Concurrent replay of the same uuid; the savepoint keeps the
            # transaction usable and the movement exists exactly once.
            return True

    def _prepare_account_bank_statement_line_vals(
        self, session, sign, amount, reason, partner_id, extras
    ):
        """Tag the statement line as an operator Cash In/Out movement.

        Tagging happens where core builds the values instead of diffing the
        session's statement lines before and after the call: the diff could
        attribute another terminal's line to this movement, and it required
        invalidating the ORM cache to see it.
        """
        vals = super()._prepare_account_bank_statement_line_vals(
            session, sign, amount, reason, partner_id, extras
        )
        vals["pos_cash_move"] = True
        vals["pos_cash_move_uuid"] = (extras or {}).get("cash_move_uuid")
        return vals

    def delete_cash_in_out(self, absl_id, partner_id):
        """Cash moves may only be removed by a POS manager.

        Odoo 19 lets the cashier open the movement list and delete entries, and
        deleting a movement releases a slot of the per-session limit.  A plain
        cashier is refused here; ``cash_move_list_popup_patch.js`` hides the
        control as well so the restriction is not discovered by trial and error.
        """
        if not self.env.user.has_group(POS_MANAGER_GROUP):
            raise UserError(_(
                "Solo un responsable del Punto de Venta puede eliminar un "
                "movimiento de efectivo.\n\n"
                "Si el movimiento es incorrecto, registre el movimiento "
                "compensatorio y avise a un responsable."
            ))
        return super().delete_cash_in_out(absl_id, partner_id)

    # ------------------------------------------------------------------
    # Closing validation: _cannot_close_session
    # ------------------------------------------------------------------

    def _cannot_close_session(self, bank_payment_method_diffs=None):
        """Odoo extension point: block session close when validations fail.

        Managers are allowed through the consistency checks of this module
        (see ``_get_cash_validation_blockers``) so a false positive cannot trap
        a store; ``post_closing_cash_details`` records the decision in the
        session chatter.
        """
        result = super()._cannot_close_session(bank_payment_method_diffs)

        if result:
            return result

        if self.env.user.has_group(POS_MANAGER_GROUP):
            return result

        blockers = self._get_cash_validation_blockers()
        if blockers:
            return blockers[0]

        return result

    def _is_empty_rescue(self):
        """Return True if this rescue session has no meaningful data.

        A rescue session is considered empty when it has:
        - No POS orders (any state: draft, paid, done, invoice, cancel)
        - No payments
        - No bank statement lines
        """
        self.ensure_one()
        if not self.rescue:
            return False

        has_orders = self.env["pos.order"].search_count(
            [("session_id", "=", self.id)], limit=1
        )
        has_payments = self.env["pos.payment"].search_count(
            [("session_id", "=", self.id)], limit=1
        )
        has_statement_lines = self.env["account.bank.statement.line"].sudo().search_count(
            [("pos_session_id", "=", self.id)], limit=1
        )
        return not (has_orders or has_payments or has_statement_lines)

    def _filter_non_empty_rescues(self):
        """Return the subset of self with orders, payments, or statement lines.

        Batched equivalent of ``filtered(lambda s: not s._is_empty_rescue())``.
        Executes 3 database queries total regardless of how many rescue
        sessions are in the recordset, so cost stays constant as
        accumulated rescues grow across sedes.

        Non-rescue sessions in self are always excluded from the result
        (the method is designed for filtering rescue sessions).

        VERIFICAR EN 19: ``point_of_sale`` ya no crea sesiones de rescate en
        ninguna de sus rutas (solo las filtra y las menciona en mensajes), por
        lo que esta lógica puede ser inerte. Ver README, sección "Pendiente de
        verificación en Odoo 19".
        """
        rescue_ids = self.filtered(lambda s: s.rescue).ids
        if not rescue_ids:
            return self.env["pos.session"]

        with_orders = set(
            self.env["pos.order"].search([
                ("session_id", "in", rescue_ids),
            ]).mapped("session_id.id")
        )
        with_payments = set(
            self.env["pos.payment"].search([
                ("session_id", "in", rescue_ids),
            ]).mapped("session_id.id")
        )
        # statement.line access requires sudo for POS users; matches the
        # pattern used elsewhere in this module (see _get_closing_cash_validation_data)
        with_lines = set(
            self.env["account.bank.statement.line"].sudo().search([
                ("pos_session_id", "in", rescue_ids),
            ]).mapped("pos_session_id.id")
        )

        non_empty_ids = list(with_orders | with_payments | with_lines)
        return self.browse(non_empty_ids)

    def _check_rescue_sessions_pending(self):
        """Return error dict if non-empty rescue sessions are open.

        CLOSING validation: only blocks if the rescue has meaningful data
        (orders, payments, or statement lines).  Empty rescues are ignored
        because they do not affect the parent session's cash integrity.

        This is stricter for OPENING (see ``_check_pending_rescue_sessions``)
        where ANY open rescue blocks, regardless of emptiness.
        """
        self.ensure_one()

        if not self.config_id.enable_rescue_session_validation:
            return None

        rescue_sessions = self._get_pending_rescue_sessions()._filter_non_empty_rescues()

        if rescue_sessions:
            return self._cash_validation_error(
                "pending_rescue",
                _(
                    "Existe(n) %(count)s sesión(es) de rescate pendiente(s) "
                    "para este Punto de Venta.\n\n"
                    "Se recomienda revisarlas antes de cerrar para asegurar "
                    "que todos los movimientos estén contabilizados.\n\n"
                    "Sesiones: %(names)s",
                    count=len(rescue_sessions),
                    names=", ".join(rescue_sessions.mapped("name")),
                ),
                show_orders_action=True,
            )
        return None

    # ------------------------------------------------------------------
    # Closing validation: post_closing_cash_details
    # ------------------------------------------------------------------

    def post_closing_cash_details(self, counted_cash):
        """Validate and close with a lock to prevent race conditions.

        The lock is acquired at the start so two terminals cannot close the same
        session with stale snapshots.  Unlike the Cash In/Out path it is worth
        waiting here (longer, still bounded timeout): the terminal that loses
        the race should see ``closing_control`` and get the standard
        "already closing" answer, not an error.

        Rescue sessions cannot be closed through this endpoint — they must
        be closed from the backend view. This is consistent with the business
        rule that rescue sessions are backend-only.

        Only validations unique to this method run here (cash difference,
        which must be checked BEFORE super writes counted_cash).  All other
        validations are handled by our ``_cannot_close_session`` override,
        which Odoo's standard ``post_closing_cash_details`` invokes internally
        before writing the counted balance.
        """
        self.ensure_one()

        # Rescue sessions have no closing flow in the interface; the message is
        # shared with the frontend.  Already-closed sessions are left to core,
        # whose answer includes the redirect to the backend.
        if self.rescue:
            return self._cash_validation_error(
                "rescue_session", self._get_structural_block_reason()
            )

        self._lock_session_row(CLOSING_LOCK_TIMEOUT, BUSY_CLOSING_MESSAGE)

        # Invalidate the ORM cache: the reads below must hit the database now
        # that the row lock is ours.
        self.invalidate_recordset()

        blockers = self._get_cash_validation_blockers()
        bypass_as_manager = (
            bool(blockers) and self.env.user.has_group(POS_MANAGER_GROUP)
        )

        error = self._check_authorized_cash_difference(counted_cash)
        if error:
            return error

        result = super().post_closing_cash_details(counted_cash)

        if bypass_as_manager and isinstance(result, dict) and result.get("successful"):
            self._post_cash_validation_bypass(blockers)

        return result

    def _check_authorized_cash_difference(self, counted_cash):
        """Return error dict if cash difference exceeds the configured maximum.

        The expected amount is Odoo's theoretical closing balance
        (``_get_expected_cash``), so the number we validate is exactly the
        number the standard closing popup displays to the operator.
        """
        self.ensure_one()

        config = self.config_id

        if not config.set_maximum_difference:
            return None

        expected = self._get_expected_cash()
        difference = abs(counted_cash - expected)
        maximum_difference = config.amount_authorized_diff

        if self.currency_id.compare_amounts(difference, maximum_difference) > 0:
            body = (
                config.cash_difference_exceeded_message
                or str(DEFAULT_CASH_DIFFERENCE_BODY)
            )
            return self._cash_validation_error(
                "authorized_difference",
                _(
                    "%(body)s\n\n"
                    "Diferencia: %(difference)s\n"
                    "Máximo autorizado: %(maximum)s",
                    body=body,
                    difference=self.currency_id.format(difference),
                    maximum=self.currency_id.format(maximum_difference),
                ),
                show_orders_action=True,
            )

        return None

    # ------------------------------------------------------------------
    # Cash In/Out integrity
    # ------------------------------------------------------------------

    def _check_cash_in_out_integrity(self):
        """Return error dict if movement count exceeds the configured limit.

        This is an integrity safety net: normally the limit prevents creating
        excess movements, but if data inconsistencies occur (e.g. 4/3), the
        session must not be closed until the issue is resolved.
        Returns ``None`` if the count is within bounds.
        """
        self.ensure_one()

        current_count = self._get_cash_in_out_move_count()
        maximum = self.config_id.maximum_cash_in_out_moves

        if current_count > maximum:
            return self._cash_validation_error(
                "cash_move_integrity",
                _(
                    "Existe una inconsistencia en los movimientos de efectivo.\n\n"
                    "Se registraron %(current)s movimientos, pero el límite "
                    "configurado es de %(maximum)s.\n\n"
                    "No puede cerrar la sesión hasta que se resuelva esta "
                    "situación. Contacte a un responsable del Punto de Venta.",
                    current=current_count,
                    maximum=maximum,
                ),
            )

        return None

    # ------------------------------------------------------------------
    # Data integrity
    # ------------------------------------------------------------------

    def _check_session_data_integrity(self):
        """Return error dict if session data has inconsistencies.

        Checks for:
        - Paid orders without associated payments
        - Orphan payments without an order

        The orphan-payment branch cannot be produced by Odoo 19 (``pos.payment``
        requires ``pos_order_id``); it stays as a guard for sessions carried
        over from a previous major version, where such rows were possible.
        """
        self.ensure_one()
        issues = []

        # Paid orders without payments
        paid_no_payments = self.env["pos.order"].search([
            ("session_id", "=", self.id),
            ("state", "=", "paid"),
            ("payment_ids", "=", False),
        ])
        if paid_no_payments:
            issues.append(
                _("Hay %(count)s órdenes pagadas sin pagos registrados.",
                  count=len(paid_no_payments))
            )

        # Orphan payments
        orphan_payments = self.env["pos.payment"].search([
            ("session_id", "=", self.id),
            ("pos_order_id", "=", False),
        ])
        if orphan_payments:
            issues.append(
                _("Hay %(count)s pagos huérfanos sin orden asociada.",
                  count=len(orphan_payments))
            )

        if issues:
            return self._cash_validation_error(
                "data_integrity",
                _(
                    "Se detectaron inconsistencias en los datos de la sesión:\n\n"
                    "%(issues)s\n\n"
                    "Contacte a un responsable antes de cerrar.",
                    issues="\n".join(f"  • {i}" for i in issues),
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Rescue session linking
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Link rescue sessions to their parent (most recent normal session).

        Only fires when ``rescue`` arrives in the creation values; if a future
        Odoo version flags the session with a later write, the link has to be
        computed there instead.  See README, "Pendiente de verificación".
        """
        for vals in vals_list:
            if vals.get("rescue") and vals.get("config_id"):
                last_normal = self.search([
                    ("config_id", "=", vals["config_id"]),
                    ("rescue", "=", False),
                ], order="id desc", limit=1)
                if last_normal:
                    vals["rescue_parent_session_id"] = last_normal.id
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Cycle validation: pending rescue sessions
    # ------------------------------------------------------------------

    def _get_pending_rescue_sessions_for_config(self, config_id):
        """Return open rescue sessions for a POS config.

        Any rescue session with state != 'closed' is considered pending,
        regardless of whether it has orders or not.  This is stricter than
        the closing validation which ignores empty rescues.
        """
        return self.search([
            ("config_id", "=", config_id),
            ("rescue", "=", True),
            ("state", "!=", "closed"),
        ])

    def _has_pending_rescue_sessions(self):
        """Return True if this session's config has open rescue sessions."""
        self.ensure_one()
        return bool(
            self._get_pending_rescue_sessions_for_config(self.config_id.id)
        )

    def _get_pending_rescue_sessions(self):
        """Return recordset of open rescue sessions for this config."""
        self.ensure_one()
        return self._get_pending_rescue_sessions_for_config(self.config_id.id)

    def _get_pending_rescue_validation_data(self):
        """Return structured data about pending rescue sessions.

        Used by both backend validation and frontend display.
        """
        self.ensure_one()
        rescues = self._get_pending_rescue_sessions()
        return [
            {"id": s.id, "name": s.name, "state": s.state}
            for s in rescues
        ]

    def _check_pending_rescue_sessions(self):
        """Return error dict if any rescue session is open for this config.

        For OPENING validation: any open rescue blocks, no exceptions.
        Empty rescues are NOT ignored here — the operator must close or
        resolve every rescue before opening a new normal session.

        Returns ``None`` if no pending rescues exist.
        """
        self.ensure_one()
        pending = self._get_pending_rescue_sessions()
        if pending:
            names = ", ".join(pending.mapped("name"))
            return {
                "blocked": True,
                "reason": "pending_rescue",
                "message": _(
                    "No puede abrir una nueva sesión porque existe(n) "
                    "%(count)s sesión(es) de rescate pendiente(s) "
                    "para este Punto de Venta.\n\n"
                    "Sesiones pendientes: %(names)s\n\n"
                    "Cierre las sesiones de rescate antes de continuar.",
                    count=len(pending),
                    names=names,
                ),
                "sessions": [
                    {"id": s.id, "name": s.name}
                    for s in pending
                ],
            }
        return {"blocked": False, "reason": "", "sessions": []}
