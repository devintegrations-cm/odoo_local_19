from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The code is structure: it decides how a line is counted (grams of bulk coffee, bags × grams, units) and which
# block of the card and of the plan it goes to. The label, the icon, the order and the words the classifier uses
# to propose the kind of a new product are records, edited in Planta › Tipos de línea: a renamed product or label
# needs no deployment. The kind of a product is a field on the product (plant_kind_id), reviewed by the plant.
KIND_CODES = [
    ("prepare", "Granel: se cuenta en kg"),
    ("packed", "Empacado: bolsas × gramaje"),
    ("ready", "Listo: unidades, sin tostar"),
    ("supply", "Insumo: unidades"),
    ("green", "Café verde: kg sin tostar, fuera de la hoja"),
]


class PlantKind(models.Model):
    """One kind of order line as the plant sees it, seeded with the five kinds and kept by the plant."""

    _name = "plant.kind"
    _description = "Tipo de línea de la planta"
    _order = "sequence, id"

    code = fields.Selection(KIND_CODES, string="Cómo se cuenta", required=True, readonly=True, help="Fijo: decide si la línea se cuenta en kg de granel, en bolsas por gramaje o en unidades.")
    name = fields.Char(string="Etiqueta", required=True, help="Como se ve en la tarjeta del tablero, el consolidado, el plan de tostión y el análisis.")
    icon = fields.Char(string="Icono", default="fa-tag", help="Clase de Font Awesome 4 del título del grupo en la tarjeta: fa-fire, fa-archive, fa-check-circle-o, fa-cube…")
    sequence = fields.Integer(default=10, help="Orden de los grupos en la tarjeta.")
    keywords = fields.Char(string="Palabras clave del producto", help="Separadas por coma. Si el nombre del producto contiene alguna, la línea es de este tipo; mayúsculas y minúsculas dan igual.")
    category_keywords = fields.Char(string="Palabras clave de la categoría", help="Separadas por coma, buscadas en el nombre completo de la categoría del producto (Café empacado: PRODUCTO TERMINADO).")

    _code_uniq = models.Constraint("unique(code)", "Ya existe un tipo con esa forma de contar.")

    @api.model
    def _words(self, raw):
        return [w.strip().upper() for w in (raw or "").split(",") if w.strip()]

    @api.model
    def _by_code(self):
        """{code: kind} in the plant's order."""
        return {kind.code: kind for kind in self.sudo().search([])}

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {"keywords", "category_keywords"}:
            self.env["product.template"]._plant_reclassify_auto()
        return res

    def unlink(self):
        raise UserError(_("Los tipos de línea son fijos: cambia la etiqueta, el icono o las palabras clave."))
