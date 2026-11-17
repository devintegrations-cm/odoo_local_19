"""Area and default analytic account (cost centre) per Clara cardholder or area: the cardholder table.

The company standardised, in the card consolidation sheet, which cost centre every cardholder books to:
Institucional (commercial), Mercadeo (marketing), Administrativo (finance, HR, legal, processes). Operations,
expansion and IT cardholders book to several cost centres. The Clara dashboard (clara_connector) reads this
table to show the area and the cost centre of every card and transaction; nothing is written back to Clara
and no purchase order is created from it.
"""
import logging
import re
import unicodedata

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


def name_key(value):
    """Comparison key: 'MARÍA ISABEL MONTOYA' and 'maria isabel  Montoya' give the same key."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def standard_name(account_name):
    """'[INST] Institucional - Libertario Coffee Roasters SAS' -> 'institucional'."""
    text = re.sub(r"^\[[^\]]*\]\s*", "", account_name or "")
    text = re.split(r"\s+-\s+", text)[0]
    return name_key(text)


def uuid_key(value):
    """Comparison key of a Clara user uuid: trimmed, lower case."""
    return str(value or "").strip().lower()


class ClaraAnalyticRule(models.Model):
    _name = "clara.analytic.rule"
    _description = "Cuenta analítica predeterminada por titular o área (tarjetas Clara)"
    _inherit = ["analytic.mixin"]
    _order = "kind desc, area, name"

    name = fields.Char("Titular / área", required=True)
    kind = fields.Selection(
        [("cardholder", "Titular"), ("area", "Área")],
        string="Tipo",
        required=True,
        default="cardholder",
        help="Titular: aplica a las tarjetas y transacciones de esa persona. Área: valor por defecto para los titulares del área sin regla propia.",
    )
    cardholder_uuid = fields.Char("Uuid del titular en Clara", index=True, help="Identificador del usuario en Clara (viene en cada tarjeta y transacción). Es la llave más segura de la tabla: gana sobre el correo y el nombre.")
    cardholder_email = fields.Char("Correo del titular", help="Correo del usuario en Clara (viene en cada tarjeta).")
    area = fields.Char("Área", help="Área del titular (COMERCIAL, MERCADEO, OPERACIONES, ...). Se muestra en el dashboard de tarjetas y transacciones.")
    analytic_name = fields.Char(
        "Analítico estándar",
        help="Centro de costo según la tabla estándar (Institucional, Mercadeo, Administrativo). "
        "Con «Buscar cuentas por nombre» se enlaza a la cuenta analítica de Odoo que se llame así.",
    )
    multi_cost_center = fields.Boolean(
        "Varios centros de costo",
        help="El titular imputa a varios centros de costo: la tabla no le asigna una cuenta analítica fija.",
    )
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    note = fields.Char("Observación")
    name_key = fields.Char(compute="_compute_keys", store=True, index=True)
    email_key = fields.Char(compute="_compute_keys", store=True, index=True)
    uuid_key = fields.Char(compute="_compute_keys", store=True, index=True)
    area_key = fields.Char(compute="_compute_keys", store=True, index=True)

    @api.depends("name", "cardholder_email", "cardholder_uuid", "area")
    def _compute_keys(self):
        for rule in self:
            rule.name_key = name_key(rule.name)
            rule.email_key = name_key(rule.cardholder_email)
            rule.uuid_key = uuid_key(rule.cardholder_uuid)
            rule.area_key = name_key(rule.area)

    # ------------------------------------------------------------------ lookup
    @api.model
    def _lookup(self, cardholder=None, email=None, area=None, company=None, uuid=None):
        """``(rule, problem)``: the rule for a cardholder, or why none can be chosen with certainty.

        Keys, in order: the Clara user uuid, the email, the exact normalised name; then the area default for a
        cardholder with no rule of their own (or whose rule decides nothing). Nothing is guessed: a name that
        matches several rules, or a rule found by a weaker key whose uuid is not the cardholder's, is a problem
        and no rule is returned.
        """
        company = company or self.env.company
        base = [("company_id", "in", [False, company.id])]
        rule, how = self.browse(), ""
        for how_, field, value in (("uuid", "uuid_key", uuid_key(uuid)), ("email", "email_key", name_key(email))):
            if value:
                rule = self._first_deciding(base + [("kind", "=", "cardholder"), (field, "=", value)])
                if rule:
                    how = how_
                    break
        if not rule and name_key(cardholder):
            rules = self.search(base + [("kind", "=", "cardholder"), ("name_key", "=", name_key(cardholder))])
            if len(rules) > 1:
                return self.browse(), _("Hay %s reglas de titular con el nombre «%s»: hay que reconocerlo por uuid o correo.") % (len(rules), cardholder)
            rule, how = rules, "name"
        if rule and how != "uuid" and uuid_key(uuid) and rule.uuid_key and rule.uuid_key != uuid_key(uuid):
            labels = {"email": _("correo"), "name": _("nombre")}
            return self.browse(), _("La regla «%s» coincide por %s pero su uuid de Clara es otro: no se adivina.") % (rule.name, labels[how])
        undecided = rule and rule.kind == "cardholder" and not rule.multi_cost_center and not rule._distribution()
        area = rule.area if undecided and rule.area else area
        if area and (not rule or undecided):
            rule = self._first_deciding(base + [("kind", "=", "area"), ("area_key", "=", name_key(area))]) or rule
        return rule, ""

    @api.model
    def _first_deciding(self, domain):
        """Among several rules matching one key, the one that decides something (account or multi flag) wins."""
        rules = self.search(domain)
        return rules.filtered(lambda r: r.multi_cost_center or r._distribution())[:1] or rules[:1]

    @api.model
    def _find_for(self, cardholder=None, email=None, area=None, company=None, uuid=None):
        """The rule for a cardholder, or none when it cannot be chosen with certainty (see ``_lookup``)."""
        return self._lookup(cardholder=cardholder, email=email, area=area, company=company, uuid=uuid)[0]

    def _distribution(self):
        """The analytic distribution of the rule, keeping only accounts that still exist. ``{}`` when empty."""
        self.ensure_one()
        Account = self.env["account.analytic.account"]
        result = {}
        for key, percentage in (self.analytic_distribution or {}).items():
            ids = [int(i) for i in str(key).split(",") if i.strip().isdigit()]
            if ids and len(Account.browse(ids).exists()) == len(ids):
                result[key] = percentage
        return result

    def _first_account(self):
        """The first analytic account of the rule's distribution (the cost centre the dashboard shows), or empty."""
        self.ensure_one()
        Account = self.env["account.analytic.account"]
        for key in self._distribution():
            ids = [int(i) for i in str(key).split(",") if i.strip().isdigit()]
            account = Account.browse(ids[:1]).exists()
            if account:
                return account
        return Account

    def _account_names(self):
        self.ensure_one()
        Account = self.env["account.analytic.account"]
        ids = [int(i) for key in self._distribution() for i in str(key).split(",")]
        return ", ".join(Account.browse(ids).exists().mapped("name"))

    # ------------------------------------------------------------------ standard name -> Odoo account
    @api.model
    def _account_by_standard_name(self, standard):
        """The analytic account whose name is the standard name, ignoring the '[CODE]' prefix and the
        ' - Company' suffix ('Institucional' matches '[INST] Institucional - Libertario Coffee Roasters SAS')."""
        Account = self.env["account.analytic.account"]
        key = name_key(standard)
        if not key:
            return Account
        candidates = Account.search([("name", "ilike", standard), ("company_id", "in", [False, self.env.company.id])])
        exact = candidates.filtered(lambda a: standard_name(a.name) == key)
        if len(exact) == 1:
            return exact
        if len(candidates) == 1:
            return candidates
        return Account

    def action_resolve_analytic_accounts(self):
        """Fill the distribution of the rules that only carry the standard name. Rules already linked are kept."""
        rules = self or self.search([])
        resolved = 0
        for rule in rules.filtered(lambda r: r.analytic_name and not r.multi_cost_center and not r._distribution()):
            account = self._account_by_standard_name(rule.analytic_name)
            if account:
                rule.analytic_distribution = {str(account.id): 100.0}
                resolved += 1
            else:
                _logger.info("Clara analytic rule «%s»: no analytic account named «%s» in Odoo", rule.name, rule.analytic_name)
        _logger.info("Clara analytic rules: %s linked to analytic accounts by name", resolved)
        return resolved
