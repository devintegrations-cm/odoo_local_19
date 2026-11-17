# -*- coding: utf-8 -*-
"""Clara card transactions, mirrored read-only from Clara's API.

The weekly sync asks Clara only for the transactions it created or updated since the last sync (Clara's
``lastUpdateDate``) and writes only the records that changed. Nothing goes back to Clara and no purchase order
is ever created, confirmed or modified here: the link with the order is computed from the order code (P#####) the
legalization bot writes on the first line of the Clara comment, and the reconciliation state follows the
reviewer's decision in Clara (``validationStatus``)."""
import json
import logging
import re
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

PARAM_LAST_SYNC = "clara_connector.last_sync_date"          # YYYY-MM-DD (company day) of the last successful transactions sync
PARAM_START_DATE = "clara_connector.sync_start_date"        # first sync: operation date to start from (settings, stored as datetime)
PARAM_OVERLAP_DAYS = "clara_connector.sync_overlap_days"    # days re-read before the last sync date, in case Clara's dates lag
DEFAULT_FIRST_SYNC_DAYS = 90
DEFAULT_OVERLAP_DAYS = 1
ADMIN_GROUP = "clara_purchase_bridge.group_clara_admin"
DEFAULT_TZ = "America/Bogota"

ORDER_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(P\d{4,8})(?![A-Za-z0-9])", re.IGNORECASE)
UNSETTLED_STATUSES = ("declined", "rejected", "reversed")   # the money never left: nothing to legalize or book
RECONCILIATION_STATES = [
    ("reconciled", "Conciliada"),
    ("approved_no_order", "Aprobada sin orden"),
    ("pending", "Pendiente"),
    ("rejected", "Rechazada"),
]
# keys that never reach the database: the card number and any identity document of the cardholder
PAN_KEYS = {"maskedpan", "pan", "cardnumber", "cvv", "cvc", "expirationdate", "expirydate", "expiration"}
PERSONAL_KEYS = {"documentnumber", "documentid", "document", "identification", "identificationnumber", "nationalid", "dni", "cedula", "taxid", "rfc", "curp"}
PERSONAL_OBJECTS = {"user", "holder", "cardholder", "owner", "employee"}


def scrub_payload(value, personal=False):
    """A copy of a Clara payload without the card number and without any identity document of the cardholder."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            k = str(key).lower()
            if k in PAN_KEYS or (personal and k in PERSONAL_KEYS):
                continue
            out[key] = scrub_payload(item, personal or k in PERSONAL_OBJECTS)
        return out
    if isinstance(value, list):
        return [scrub_payload(v, personal) for v in value]
    return value


def order_code(comment):
    """The order code (P#####) on the first line of a Clara comment, upper case, or an empty string."""
    text = (comment or "").strip()
    first_line = text.splitlines()[0] if text else ""
    match = ORDER_CODE_RE.search(first_line)
    return match.group(1).upper() if match else ""


def to_date(raw):
    try:
        return fields.Date.to_date(str(raw)[:10]) if raw else False
    except ValueError:
        return False


def differs(record, vals):
    """Does writing ``vals`` change ``record``? The sync writes only what changed."""
    for key, value in vals.items():
        if key == "last_sync_date":
            continue
        current = record[key]
        if isinstance(current, models.BaseModel):
            current = current.id or False
        if (current or False) != (value or False):
            return True
    return False


class ClaraTransaction(models.Model):
    _name = "clara.transaction"
    _description = "Transacción de tarjeta Clara"
    _inherit = ["clara.sync.mixin"]
    _order = "transaction_date desc, id desc"

    clara_uuid = fields.Char("Uuid en Clara", required=True, index=True, copy=False)
    name = fields.Char("Nombre", compute="_compute_name", store=True)
    amount = fields.Monetary("Monto", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    merchant_name = fields.Char("Comercio")
    merchant_category = fields.Char("Categoría del comercio")
    tx_type = fields.Char("Tipo", compute="_compute_from_payload", store=True, index=True, help="Tipo de operación en Clara: PURCHASE, PAYMENT, FEE, REFUND...")
    status = fields.Selection([
        ("pending", "Pendiente"), ("pre_authorized", "Preautorizada"), ("authorized", "Autorizada"), ("approved", "Aprobada"),
        ("declined", "Declinada"), ("rejected", "Rechazada por Clara"), ("reversed", "Reversada"), ("inactive", "Inactiva"),
        ("blocked", "Bloqueada"), ("system_transaction", "Del sistema"), ("notification", "Notificación"), ("other", "Otra"),
    ], string="Estado de la operación", default="pending", help="Si el dinero salió de la tarjeta, según Clara.")
    card_uuid = fields.Char("Uuid de la tarjeta")
    card_last_four = fields.Char("Tarjeta (últimos 4)")
    card_id = fields.Many2one("clara.card", string="Tarjeta", compute="_compute_card_id", store=True)
    cardholder_name = fields.Char("Titular", index=True)
    cardholder_uuid = fields.Char("Uuid del titular en Clara", compute="_compute_from_payload", store=True)
    cardholder_email = fields.Char("Correo del titular")
    transaction_date = fields.Date("Fecha", index=True)
    posting_date = fields.Date("Fecha contable")
    last_update_date = fields.Date("Última actualización en Clara", help="Fecha en que Clara creó o modificó por última vez la transacción (lastUpdateDate).")
    clara_comment = fields.Text("Comentario en Clara", compute="_compute_from_payload", store=True,
                                help="Lo que el titular escribió en Clara. El bot de legalización escribe el código de la orden de compra en la primera línea.")
    approval_status = fields.Char("Estado en Clara", compute="_compute_from_payload", store=True, index=True,
                                  help="Legalización decidida por el revisor en Clara: Approved, Needs Approval o Rejected.")
    approval_comment = fields.Char("Comentario del revisor", compute="_compute_from_payload", store=True)
    has_receipt = fields.Boolean("Con comprobante", compute="_compute_from_payload", store=True)
    analytic_rule_id = fields.Many2one("clara.analytic.rule", string="Regla de titular", compute="_compute_analytic_rule_id", store=True,
                                       help="Regla de la tabla de titulares (Compras › Configuración › Analítico por titular Clara) que da el área y el centro de costo.")
    area = fields.Char(related="analytic_rule_id.area", string="Área", store=True)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Cuenta analítica", compute="_compute_analytic_account_id", store=True)
    purchase_order_id = fields.Many2one("purchase.order", string="Orden ligada", compute="_compute_purchase_order_id", store=True,
                                        help="Orden de compra cuyo nombre es el código P##### de la primera línea del comentario de Clara (las canceladas no cuentan).")
    purchase_state = fields.Selection(related="purchase_order_id.state", string="Estado de la orden")
    reconciliation_state = fields.Selection(RECONCILIATION_STATES, string="Conciliación", compute="_compute_reconciliation_state", store=True, index=True,
                                            help="Conciliada: aprobada en Clara y con orden existente. Aprobada sin orden: aprobada en Clara y sin orden. "
                                                 "Pendiente: sin legalizar. Rechazada: rechazada en Clara. Vacío: no es una compra con dinero cobrado.")
    reconciled_ratio = fields.Float("Conciliado (%)", compute="_compute_reconciliation_state", store=True, aggregator="avg",
                                    help="100 si la transacción está conciliada, 0 si no: el promedio por mes es el porcentaje conciliado.")
    raw_payload = fields.Text("Payload", help="Respuesta de Clara sin el número de la tarjeta ni documentos de identidad.")
    last_sync_date = fields.Datetime("Última sincronización con cambios")

    _clara_uuid_uniq = models.Constraint("unique(clara_uuid)", "The Clara UUID must be unique!")

    # ---------------------------------------------------------------- computed fields
    @api.depends("merchant_name", "transaction_date")
    def _compute_name(self):
        for tx in self:
            tx.name = "%s · %s" % (tx.merchant_name or _("Sin comercio"), fields.Date.to_string(tx.transaction_date) if tx.transaction_date else _("sin fecha"))

    def _raw(self):
        try:
            return json.loads(self.raw_payload or "{}") or {}
        except ValueError:
            return {}

    @api.depends("raw_payload")
    def _compute_from_payload(self):
        for tx in self:
            raw = tx._raw()
            validation = raw.get("validationStatus") or {}
            user = raw.get("user") or {}
            tx.tx_type = raw.get("type") or False
            tx.has_receipt = bool((raw.get("hasAttachments") or {}).get("value"))
            tx.clara_comment = (raw.get("comment") or "").strip() or False
            tx.approval_status = (validation.get("status") or "").strip() or False
            tx.approval_comment = (validation.get("comment") or "").strip()[:200] or False
            tx.cardholder_uuid = str(user.get("uuid") or user.get("id") or "") or False

    @api.depends("card_uuid")
    def _compute_card_id(self):
        uuids = [u for u in self.mapped("card_uuid") if u]
        cards = {c.clara_uuid: c for c in self.env["clara.card"].sudo().search([("clara_uuid", "in", uuids)])} if uuids else {}
        for tx in self:
            tx.card_id = cards.get(tx.card_uuid, self.env["clara.card"])

    @api.depends("cardholder_uuid", "cardholder_email", "cardholder_name")
    def _compute_analytic_rule_id(self):
        Rule = self.env["clara.analytic.rule"].sudo()
        for tx in self:
            tx.analytic_rule_id = Rule._find_for(cardholder=tx.cardholder_name, email=tx.cardholder_email, uuid=tx.cardholder_uuid)

    @api.depends("analytic_rule_id.analytic_distribution", "analytic_rule_id.multi_cost_center")
    def _compute_analytic_account_id(self):
        for tx in self:
            tx.analytic_account_id = tx.analytic_rule_id._first_account() if tx.analytic_rule_id else False

    @api.depends("clara_comment")
    def _compute_purchase_order_id(self):
        """The order whose name is the code on the first line of the Clara comment. One search for the whole batch;
        a cancelled order does not count."""
        codes = {order_code(tx.clara_comment) for tx in self}
        codes.discard("")
        orders = {}
        if codes:
            for order in self.env["purchase.order"].sudo().search([("name", "in", list(codes)), ("state", "!=", "cancel")], order="id"):
                orders.setdefault(order.name.upper(), order)
        for tx in self:
            tx.purchase_order_id = orders.get(order_code(tx.clara_comment), self.env["purchase.order"])

    @api.depends("tx_type", "status", "approval_status", "purchase_order_id", "purchase_order_id.state")
    def _compute_reconciliation_state(self):
        for tx in self:
            if (tx.tx_type or "").upper() != "PURCHASE" or tx.status in UNSETTLED_STATUSES:
                state = False   # not an expense: a payment, a fee, a declined attempt
            else:
                legalization = tx._clara_legalization()
                if legalization == "rejected":
                    state = "rejected"
                elif legalization == "approved":
                    state = "reconciled" if tx.purchase_order_id and tx.purchase_order_id.state != "cancel" else "approved_no_order"
                else:
                    state = "pending"
            tx.reconciliation_state = state
            tx.reconciled_ratio = 100.0 if state == "reconciled" else 0.0

    def _clara_legalization(self):
        """approved | rejected | pending: the reviewer's decision in Clara (validationStatus of the payload)."""
        self.ensure_one()
        value = (self.approval_status or "").strip().lower()
        return "approved" if value == "approved" else "rejected" if value == "rejected" else "pending"

    def action_open_order(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "purchase.order", "res_id": self.purchase_order_id.id, "view_mode": "form", "target": "current"}

    # ---------------------------------------------------------------- payload -> values
    @api.model
    def _map_status(self, raw):
        """Clara adds statuses over time: unknown ones land in 'other' instead of failing the record."""
        value = str(raw or "pending").lower()
        return value if value in dict(self._fields["status"].selection) else "other"

    @api.model
    def _vals_from_payload(self, item):
        """The stored values of one Clara transaction. The payload is kept without the card number and without any
        identity document; the legalization, the comment and the type are computed from it."""
        merchant = item.get("merchant") or {}
        user = item.get("user") or {}
        card = item.get("card") or {}
        audit = item.get("audit") or {}
        amount_val = item.get("amountValue") or {}
        if not amount_val and item.get("amount") is not None:
            amount_val = {"amount": item.get("amount"), "currency": item.get("currency")}
        currency_code = amount_val.get("currency") or item.get("currency") or self.env.company.currency_id.name
        currency = self.env["res.currency"].with_context(active_test=False).search([("name", "=", currency_code)], limit=1) or self.env.company.currency_id
        masked = str(card.get("maskedPan") or "")
        return {
            "clara_uuid": item.get("uuid") or item.get("id"),
            "amount": abs(float(amount_val.get("amount") or 0.0)),
            "currency_id": currency.id,
            "merchant_name": merchant.get("name") or item.get("transactionLabel") or _("Desconocido"),
            "merchant_category": merchant.get("category") or merchant.get("description") or "",
            "card_uuid": card.get("uuid") or card.get("id") or "",
            "card_last_four": (card.get("lastFour") or masked[-4:] or "")[-4:],
            "cardholder_name": user.get("holderName") or user.get("fullName") or user.get("name") or "",
            "cardholder_email": user.get("email") or user.get("username") or "",
            "transaction_date": to_date(audit.get("operationDate") or item.get("createdAt") or item.get("transactionDate")) or fields.Date.today(),
            "posting_date": to_date(audit.get("accountingDate") or item.get("postingDate")),
            "last_update_date": to_date(audit.get("lastUpdateDate") or item.get("updatedAt")),
            "status": self._map_status(item.get("status")),
            "raw_payload": json.dumps(scrub_payload(item), indent=2, sort_keys=True, ensure_ascii=False, default=str),
        }

    # ---------------------------------------------------------------- sync
    @api.model
    def _today_local(self):
        tz = pytz.timezone(self.env.company.partner_id.tz or DEFAULT_TZ)
        return datetime.now(pytz.utc).astimezone(tz).date()

    @api.model
    def _sync_window(self):
        """What to ask Clara for. After the first sync: only the transactions created or updated since the last sync
        (``lastUpdateDateRangeStart``, with a safety overlap). The first sync reads by operation date from the
        configured start, or the last 90 days."""
        icp = self.env["ir.config_parameter"].sudo()
        last = icp.get_param(PARAM_LAST_SYNC)
        if last:
            try:
                overlap = max(0, int(icp.get_param(PARAM_OVERLAP_DAYS, DEFAULT_OVERLAP_DAYS) or 0))
            except ValueError:
                overlap = DEFAULT_OVERLAP_DAYS
            return {"updated_since": fields.Date.from_string(last) - timedelta(days=overlap)}
        start = (icp.get_param(PARAM_START_DATE) or "").strip()
        if start:
            if len(start) > 10:   # the settings page stores a UTC datetime: take the company's local day
                local = fields.Datetime.context_timestamp(self.with_context(tz=self.env.company.partner_id.tz or DEFAULT_TZ), fields.Datetime.from_string(start))
                return {"from_date": local.date()}
            return {"from_date": fields.Date.from_string(start)}
        return {"from_date": self._today_local() - timedelta(days=DEFAULT_FIRST_SYNC_DAYS)}

    @api.model
    def _calls_this_month(self):
        return int(self.env["ir.config_parameter"].sudo().get_param("clara_connector.calls_" + datetime.now().strftime("%Y%m"), "0") or 0)

    @api.model
    def _run_sync(self, triggered_by="cron"):
        """Transactions created or updated in Clara since the last sync, pages of the configured size (100, the API's
        maximum). Only records that changed are written. The last sync date advances only when every record was
        stored, so a failed one is read again next time."""
        sync_log = self._create_sync_log("transactions", triggered_by)
        icp = self.env["ir.config_parameter"].sudo()
        calls_before = self._calls_this_month()
        try:
            service = self._get_api_service()
            window = self._sync_window()
            raw_txs = service.get_transactions(**window)
            created = updated = unchanged = errored = 0
            now = fields.Datetime.now()
            for item in raw_txs:
                uuid_val = item.get("uuid") or item.get("id")
                if not uuid_val:
                    continue
                try:
                    with self.env.cr.savepoint():
                        vals = self._vals_from_payload(item)
                        existing = self.search([("clara_uuid", "=", uuid_val)], limit=1)
                        if existing:
                            if differs(existing, vals):
                                vals["last_sync_date"] = now
                                existing.write(vals)
                                updated += 1
                            else:
                                unchanged += 1
                        else:
                            vals["last_sync_date"] = now
                            existing = self.create(vals)
                            created += 1
                        existing.flush_recordset()
                except Exception as ex:  # noqa: BLE001
                    self.env.invalidate_all()
                    _logger.error("Failed to sync Clara transaction %s: %s", uuid_val, ex)
                    errored += 1
            sync_log.write({
                "state": "success" if errored == 0 else "partial",
                "records_fetched": len(raw_txs), "records_created": created, "records_updated": updated,
                "records_skipped": unchanged, "records_errored": errored,
                "api_calls": self._calls_this_month() - calls_before, "finished_at": fields.Datetime.now(),
            })
            if errored == 0:
                icp.set_param(PARAM_LAST_SYNC, fields.Date.to_string(self._today_local()))
        except UserError as e:   # configuration or Clara error, already explained: no traceback
            _logger.warning("Clara transactions sync failed: %s", e)
            sync_log.write({"state": "failed", "error_message": str(e), "api_calls": self._calls_this_month() - calls_before, "finished_at": fields.Datetime.now()})
        except Exception as e:  # noqa: BLE001
            _logger.exception("Clara transactions sync failed")
            sync_log.write({"state": "failed", "error_message": str(e), "api_calls": self._calls_this_month() - calls_before, "finished_at": fields.Datetime.now()})
        return sync_log

    @api.model
    def _relink_after_sync(self):
        """Links that depend on other records: a transaction whose card arrived in this sync, an approved or pending
        transaction whose order was booked (or cancelled) since the last sync, a record whose cardholder joined the
        table."""
        Transaction = self.sudo()
        # "modified" on the dependency recomputes the link and everything that follows from it (state, area, account)
        Transaction.search([("card_id", "=", False), ("card_uuid", "!=", False)]).modified(["card_uuid"])
        # the order link only follows the orders here: an approved or pending transaction with a code in its comment
        # and no order yet (the bot may have booked it since), and any transaction whose linked order was cancelled
        # (the link is computed without cancelled orders)
        unlinked = Transaction.search([("reconciliation_state", "in", ("approved_no_order", "pending")), ("purchase_order_id", "=", False), ("clara_comment", "!=", False)])
        with_code = unlinked.filtered(lambda tx: order_code(tx.clara_comment))
        (with_code | Transaction.search([("purchase_order_id.state", "=", "cancel")])).modified(["clara_comment"])
        for model in ("clara.transaction", "clara.card"):
            self.env[model].sudo().search([("analytic_rule_id", "=", False)]).modified(["cardholder_uuid"])
        self.env.flush_all()

    @api.model
    def _run_weekly_sync(self, triggered_by="cron"):
        """The whole weekly run: transactions, cards, then the links between them. Two syncs, each with its log."""
        transactions_log = self._run_sync(triggered_by)
        cards_log = self.env["clara.card"]._run_card_sync(triggered_by)
        self._relink_after_sync()
        _logger.info("Clara weekly sync (%s): transactions %s, cards %s", triggered_by, transactions_log.state, cards_log.state)
        return {"transactions": transactions_log, "cards": cards_log}

    @api.model
    def _cron_weekly_sync(self):
        return self._run_weekly_sync("cron")

    def action_sync_now(self):
        """«Sincronizar ahora»: the weekly run, by hand, for Clara administrators only."""
        if not self.env.user.has_group(ADMIN_GROUP):
            raise AccessError(_("Solo el grupo «Clara / Administrador» puede sincronizar con Clara."))
        result = self._run_weekly_sync("manual")
        logs = result["transactions"] | result["cards"]
        failed = logs.filtered(lambda l: l.state == "failed")
        if failed:
            reasons = "; ".join(dict.fromkeys(m for m in failed.mapped("error_message") if m))[:400]
            params = {"title": _("La sincronización con Clara falló"), "message": reasons or _("Revisa el menú Sincronizaciones."), "type": "danger", "sticky": True}
        else:
            t, c = result["transactions"], result["cards"]
            params = {"title": _("Sincronización con Clara"), "type": "success", "sticky": False,
                      "message": _("Transacciones: %s nuevas, %s actualizadas, %s sin cambios. Tarjetas: %s nuevas, %s actualizadas, %s sin cambios. Llamadas a la API: %s.") % (
                          t.records_created, t.records_updated, t.records_skipped, c.records_created, c.records_updated, c.records_skipped, t.api_calls + c.api_calls)}
        params["next"] = {"type": "ir.actions.client", "tag": "reload"}
        return {"type": "ir.actions.client", "tag": "display_notification", "params": params}
