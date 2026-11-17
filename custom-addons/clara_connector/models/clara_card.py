# -*- coding: utf-8 -*-
"""Clara corporate cards, mirrored read-only from Clara's API. The full card number and the cardholder's national
id never reach the database: only the last four digits, the cardholder's name, uuid and email are kept, and the
raw payload is not stored."""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CARD_STATUSES = [("active", "Activa"), ("blocked", "Bloqueada"), ("inactive", "Inactiva"), ("cancelled", "Cancelada")]
CARD_TYPES = [("physical", "Física"), ("virtual", "Virtual")]
BLOCKED_STATUSES = ("LOCKED", "MASTER_LOCKED", "CLARA_BLOCKED", "BLOCKED", "FROZEN")
CANCELLED_STATUSES = ("CANCELLED", "CANCELED", "CLOSED", "DELETED")


def safe_float(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class ClaraCard(models.Model):
    _name = "clara.card"
    _description = "Tarjeta corporativa Clara"
    _inherit = ["clara.sync.mixin"]
    _order = "cardholder_name, last_four, id"

    name = fields.Char("Nombre", compute="_compute_name", store=True)
    clara_uuid = fields.Char("Uuid en Clara", required=True, index=True, copy=False)
    alias = fields.Char("Alias en Clara")
    cardholder_name = fields.Char("Titular", index=True)
    cardholder_uuid = fields.Char("Uuid del titular en Clara")
    cardholder_email = fields.Char("Correo del titular")
    last_four = fields.Char("Últimos 4 dígitos", size=4)
    card_type = fields.Selection(CARD_TYPES, string="Tipo")
    status = fields.Selection(CARD_STATUSES, string="Estado", default="inactive", index=True)
    status_raw = fields.Char("Estado en Clara", help="Estado y bloqueo tal como los envía Clara.")
    monthly_limit = fields.Monetary("Límite mensual", currency_field="currency_id", help="Límite de la tarjeta cuando su periodicidad es mensual.")
    periodicity = fields.Char("Periodicidad del límite")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    analytic_rule_id = fields.Many2one("clara.analytic.rule", string="Regla de titular", compute="_compute_analytic_rule_id", store=True,
                                       help="Regla de la tabla de titulares (Compras › Configuración › Analítico por titular Clara) que da el área y el centro de costo.")
    area = fields.Char(related="analytic_rule_id.area", string="Área", store=True)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Cuenta analítica", compute="_compute_analytic_account_id", store=True)
    transaction_count = fields.Integer("Transacciones", compute="_compute_transaction_count")
    last_sync_date = fields.Datetime("Última sincronización con cambios")

    _card_uuid_uniq = models.Constraint("unique(clara_uuid)", "The Clara Card UUID must be unique!")

    @api.depends("cardholder_name", "alias", "last_four")
    def _compute_name(self):
        for card in self:
            card.name = "%s · %s" % (card.cardholder_name or card.alias or "Clara", card.last_four or "----")

    @api.depends("cardholder_uuid", "cardholder_email", "cardholder_name")
    def _compute_analytic_rule_id(self):
        Rule = self.env["clara.analytic.rule"].sudo()
        for card in self:
            card.analytic_rule_id = Rule._find_for(cardholder=card.cardholder_name, email=card.cardholder_email, uuid=card.cardholder_uuid)

    @api.depends("analytic_rule_id.analytic_distribution", "analytic_rule_id.multi_cost_center")
    def _compute_analytic_account_id(self):
        for card in self:
            card.analytic_account_id = card.analytic_rule_id._first_account() if card.analytic_rule_id else False

    def _compute_transaction_count(self):
        counts = {}
        if self.ids:
            for card, count in self.env["clara.transaction"].sudo()._read_group([("card_id", "in", self.ids)], ["card_id"], ["__count"]):
                counts[card.id] = count
        for card in self:
            card.transaction_count = counts.get(card.id, 0)

    def action_sync_now(self):
        """«Sincronizar ahora» from the cards list: the same weekly run, for Clara administrators only."""
        return self.env["clara.transaction"].action_sync_now()

    def action_open_transactions(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("clara_connector.action_clara_transactions")
        action["domain"] = [("card_id", "=", self.id)]
        action["context"] = {"search_default_purchases": 1}
        return action

    # ---------------------------------------------------------------- payload -> values
    @api.model
    def _map_status(self, status, lock_code):
        status, lock = str(status or "").upper(), str(lock_code or "").upper()
        if status in CANCELLED_STATUSES:
            return "cancelled"
        if status in BLOCKED_STATUSES or (lock and lock != "UNLOCKED"):
            return "blocked"
        if status == "ACTIVE":
            return "active"
        return "inactive"   # INACTIVE, PENDING and anything Clara adds later

    @api.model
    def _vals_from_payload(self, item):
        """The stored values of one Clara card: never the card number (only its last four digits) and never an
        identity document of the cardholder."""
        user = item.get("user") or item.get("holder") or item.get("cardholder") or {}
        masked = str(item.get("maskedPan") or "")
        status_raw = str(item.get("status") or item.get("claraStatus") or "")
        lock = str(item.get("lockCode") or "")
        card_type = str(item.get("type") or item.get("cardType") or "").upper()
        periodicity = str(item.get("periodicity") or "").upper()
        limit = safe_float(item.get("threshold")) or safe_float(item.get("creditLimitValue") or item.get("creditLimit"))
        currency_code = item.get("currency") or self.env.company.currency_id.name
        currency = self.env["res.currency"].with_context(active_test=False).search([("name", "=", currency_code)], limit=1) or self.env.company.currency_id
        return {
            "clara_uuid": item.get("uuid") or item.get("id") or item.get("card_id") or item.get("card_uuid"),
            "alias": item.get("alias") or item.get("name") or "",
            "cardholder_name": user.get("fullName") or user.get("name") or user.get("holderName") or item.get("holderName") or "",
            "cardholder_uuid": str(user.get("uuid") or user.get("id") or ""),
            "cardholder_email": user.get("username") or user.get("email") or "",
            "last_four": (item.get("lastFour") or item.get("last4") or masked[-4:] or "")[-4:],
            "card_type": "virtual" if ("VIRTUAL" in card_type or "SINGLE" in card_type) else "physical",
            "status": self._map_status(status_raw, lock),
            "status_raw": status_raw + ((" / " + lock) if lock and lock != "UNLOCKED" else ""),
            "monthly_limit": limit if periodicity == "MONTHLY" else 0.0,
            "periodicity": periodicity,
            "currency_id": currency.id,
        }

    # ---------------------------------------------------------------- sync
    @api.model
    def _run_card_sync(self, triggered_by="cron"):
        """Every card, in pages of the configured size (one call for a few dozen cards). Only cards that changed are written."""
        from .clara_transaction import differs

        sync_log = self._create_sync_log("cards", triggered_by)
        calls_before = self.env["clara.transaction"]._calls_this_month()
        try:
            raw_cards = self._get_api_service().get_cards()
            created = updated = unchanged = errored = 0
            now = fields.Datetime.now()
            for item in raw_cards:
                uuid_val = item.get("uuid") or item.get("id") or item.get("card_id") or item.get("card_uuid")
                if not uuid_val:
                    _logger.warning("Skipping Clara card without uuid: %s", list(item.keys()))
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
                    _logger.error("Failed to sync Clara card %s: %s", uuid_val, ex)
                    errored += 1
            sync_log.write({
                "state": "success" if errored == 0 else "partial",
                "records_fetched": len(raw_cards), "records_created": created, "records_updated": updated,
                "records_skipped": unchanged, "records_errored": errored,
                "api_calls": self.env["clara.transaction"]._calls_this_month() - calls_before, "finished_at": fields.Datetime.now(),
            })
        except UserError as e:   # configuration or Clara error, already explained: no traceback
            _logger.warning("Clara cards sync failed: %s", e)
            sync_log.write({"state": "failed", "error_message": str(e), "api_calls": self.env["clara.transaction"]._calls_this_month() - calls_before, "finished_at": fields.Datetime.now()})
        except Exception as e:  # noqa: BLE001
            _logger.exception("Clara cards sync failed")
            sync_log.write({"state": "failed", "error_message": str(e), "api_calls": self.env["clara.transaction"]._calls_this_month() - calls_before, "finished_at": fields.Datetime.now()})
        return sync_log
