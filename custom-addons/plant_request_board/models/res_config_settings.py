import re

from odoo import _, api, fields, models

# Plant staff are a Many2many, which Odoo does not store through config_parameter: the only key handled by hand.
PARAM_PLANT_USERS = "plant_request_board.plant_user_ids"
# vocabulary of the product classifier: the automatic products (and their open lines) are classified again on change
RECLASSIFY_FIELDS = ("plant_beans_words", "plant_ground_words", "plant_ignore_words")
# "PALABRA=texto" lists are Char (config_parameter does not take Text), separated by ";" or by line breaks
PAIR_SEP = re.compile(r"[;\n]")
SHORT_WORDS_DEFAULT = "; ".join((
    "BOLSA PARA EMPACAR=Bolsa", "CODIGO DE BARRAS=(cód. barras)", "GRAMOS=g", "KILOS=kg", "KILO=kg", "ONZAS=oz", "ONZA=oz",
    "GENERICA=genérica", "EN GRANO=en grano", "MOLIDO=molido", "MEDIANA HORIZONTAL=mediana horiz.", "MEDIANA VERTICAL=mediana vert.",
    "PEQUEÑA=pequeña", "GRANDE=grande", "TAPAS=Tapa", "TAPA=Tapa", "VASOS=Vaso", "VASO=Vaso", "CAJAS=Caja", "CAJA=Caja",
    "ETIQUETAS=Etiqueta", "ETIQUETA=Etiqueta",
))


class ResConfigSettings(models.TransientModel):
    """Planta settings. Each field is stored as the ir.config_parameter named in config_parameter, which Odoo reads
    and writes by itself; the other models read them through _plant_get, so a key and its default live only here."""

    _inherit = "res.config.settings"

    plant_warehouse_ids = fields.Many2many("stock.warehouse", string="Almacenes de planta", help="Toda transferencia o entrega que sale de estos almacenes es una solicitud a la planta. Es la bandera «Almacén de planta» de cada almacén.")
    plant_user_ids = fields.Many2many("res.users", string="Personal de planta", help="Reciben el sonido y la notificación en Odoo; las solicitudes creadas por ellos no disparan la alerta.")
    plant_channel_id = fields.Many2one("discuss.channel", string="Canal de Conversaciones", help="Cada solicitud nueva se publica aquí. Los miembros la ven en Conversaciones, con sonido, y en el celular si tienen la app o las notificaciones push activas.", config_parameter="plant_request_board.channel_id")
    plant_anthropic_model = fields.Char(string="Modelo", default="claude-sonnet-5", config_parameter="plant_request_board.anthropic_model")
    plant_ai_enabled = fields.Boolean(string="Análisis IA activo", compute="_compute_plant_ai_enabled", help="La clave de Anthropic vive en el servidor: variable de entorno PLANT_ANTHROPIC_API_KEY o la opción plant_anthropic_api_key de odoo.conf.")
    plant_history_days = fields.Integer(string="Días de histórico", default=90, help="Días hacia atrás para calcular lo usual de cada tienda en el análisis.", config_parameter="plant_request_board.history_days")
    # channel rules live in plant.channel (records, not text); how a line is read from the product name
    plant_beans_words = fields.Char(string="Palabras de «en grano»", default="GRANO", help="Separadas por coma: si el nombre de un producto nuevo contiene alguna, el clasificador propone molienda «en grano».", config_parameter="plant_request_board.beans_words")
    plant_ground_words = fields.Char(string="Palabras de «molido»", default="MOLIDO", help="Separadas por coma: si el nombre de un producto nuevo contiene alguna, el clasificador propone molienda «molido».", config_parameter="plant_request_board.ground_words")
    plant_ignore_words = fields.Char(string="Palabras ignoradas al clasificar", default="CON CODIGO DE BARRAS, CODIGO DE BARRAS, (COPIA)", help="Separadas por coma: se quitan del nombre antes de clasificarlo y antes de buscar duplicados (la versión con código de barras es el mismo producto).", config_parameter="plant_request_board.ignore_words")
    # the automatic rows of the sheet
    plant_prep_bag_grams = fields.Float(string="Gramos por bolsa de preparación", default=2500.0, help="El café a granel (y las bolsas de ese gramaje) se cuentan en la hoja en bolsas de este tamaño: 2500 = «Preparación 2,5».", config_parameter="plant_request_board.prep_bag_grams")
    # green coffee and supplies
    plant_default_shrinkage = fields.Float(string="Merma de tostión por defecto (%)", default=16.0, digits=(5, 2), help="Pérdida de peso al tostar cuando la línea de café no tiene su propia merma: kg verde = kg tostado ÷ (1 − merma).", config_parameter="plant_request_board.default_shrinkage")
    plant_green_minimum_kg = fields.Float(string="Mínimo de café verde por línea (kg)", default=10.0, digits=(12, 2), help="Por debajo de estos kg de café verde la alerta de la línea pasa a amarillo, salvo que la línea tenga su propio mínimo.", config_parameter="plant_request_board.green_minimum_kg")
    plant_supply_minimum = fields.Float(string="Mínimo de insumos por fabricar (unidades)", default=0.0, digits=(12, 0), help="Por debajo de estas unidades sobrantes, el insumo de una lista de materiales pasa a amarillo.", config_parameter="plant_request_board.supply_minimum")
    plant_row_grind = fields.Selection([("split", "Una fila por molienda (Paz 340 en grano / Paz 340 molido)"), ("merge", "Grano y molido en la misma fila (Paz 340)")], string="Filas y molienda", default="split", config_parameter="plant_request_board.row_grind")
    plant_short_words = fields.Char(string="Abreviaturas de la tarjeta", default=SHORT_WORDS_DEFAULT, help="PALABRA=texto, separadas por punto y coma, aplicadas en orden al nombre del producto en la tarjeta del tablero (palabras completas).", config_parameter="plant_request_board.short_words")
    plant_card_rows = fields.Integer(string="Filas por grupo en la tarjeta", default=8, config_parameter="plant_request_board.card_rows")

    def _compute_plant_ai_enabled(self):
        enabled = self.env["stock.picking"]._plant_ai_enabled()
        for settings in self:
            settings.plant_ai_enabled = enabled

    # --- reading, for the other models -------------------------------------------------
    @api.model
    def _plant_get(self, name):
        """Value of a Planta setting: its ir.config_parameter, else the default of the field."""
        field = self._fields[name]
        value = self.env["ir.config_parameter"].sudo().get_param(field.config_parameter)
        if value in (False, None):
            value = field.default(self) if field.default else ""
        return value or ""

    @api.model
    def _plant_get_list(self, name, upper=True):
        items = [x.strip() for x in str(self._plant_get(name)).split(",") if x.strip()]
        return [x.upper() for x in items] if upper else items

    @api.model
    def _plant_get_int(self, name):
        try:
            return int(self._plant_get(name))
        except (TypeError, ValueError):
            return int(self._fields[name].default(self))

    @api.model
    def _plant_get_float(self, name):
        try:
            return float(self._plant_get(name))
        except (TypeError, ValueError):
            return float(self._fields[name].default(self))

    @api.model
    def _plant_get_pairs(self, name, upper=True):
        """The "PALABRA=texto" items of a setting as (word, text), in order; items without "=" are ignored."""
        pairs = []
        for item in PAIR_SEP.split(str(self._plant_get(name))):
            word, sep, text = item.partition("=")
            if sep and word.strip():
                pairs.append((word.strip().upper() if upper else word.strip().lower(), text.strip()))
        return pairs

    @api.model
    def _plant_staff_ids(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(PARAM_PLANT_USERS) or ""
        return {int(x) for x in raw.split(",") if x.strip().isdigit()}

    # --- the settings form ---------------------------------------------------------------
    @api.model
    def get_values(self):
        res = super().get_values()
        res["plant_user_ids"] = [(6, 0, list(self._plant_staff_ids()))]
        res["plant_warehouse_ids"] = [(6, 0, self.env["stock.picking"]._plant_warehouses().ids)]
        return res

    def set_values(self):
        before = {name: self._plant_get(name) for name in RECLASSIFY_FIELDS}
        super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(PARAM_PLANT_USERS, ",".join(str(u.id) for u in self.plant_user_ids))
        current = self.env["stock.picking"]._plant_warehouses()
        (current - self.plant_warehouse_ids).write({"plant_is_plant": False})   # each write classifies the transfers of the warehouse again
        (self.plant_warehouse_ids - current).write({"plant_is_plant": True})
        if self.plant_channel_id and self.plant_user_ids:
            self.plant_channel_id.sudo().add_members(partner_ids=self.plant_user_ids.partner_id.ids)   # plant staff join the channel automatically
        if any(self._plant_get(name) != before[name] for name in RECLASSIFY_FIELDS):
            self.env["product.template"]._plant_reclassify_auto()

    def action_plant_test_notification(self):
        self.env["stock.picking"].action_plant_test_notification()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"type": "info", "message": _("Si no sonó, haz clic en cualquier parte de la página y prueba de nuevo: el navegador solo reproduce audio después de una interacción."), "sticky": False}}
