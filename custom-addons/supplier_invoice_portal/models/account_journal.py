# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Tipo de documento DIAN de la resolucion de documento soporte en Jorels
# (l10n_co_edi_jorels/models/account_move.py, _compute_ei_type_document).
SPR_SUPPORT_DOCUMENT_RESOLUTION_TYPE = 12


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # El boton "Generar eventos RADIAN" solo sale en los diarios marcados
    # (DECISIONS.md #72). Se marca a mano: el nombre cambia entre bases y se
    # traduce, y produccion tiene varios diarios de compras (gastos,
    # importaciones...).
    spr_radian_enabled = fields.Boolean(
        string="Eventos RADIAN de receptor",
        default=False,
        help="Las facturas de proveedor publicadas en este diario muestran el boton "
             "'Generar eventos RADIAN' (acuse 030, recibo del bien 032 y aceptacion "
             "expresa 033). Solo para el diario de facturas electronicas de proveedores: "
             "no aplica a diarios de documento soporte.",
    )

    def _spr_is_support_document_journal(self):
        """True si el diario tiene la resolucion DIAN de documento soporte.

        Mismo criterio que Jorels (``_compute_ei_type_document``): tipo de
        documento 12 en la resolucion de facturas del diario. Sin Jorels el
        campo no existe y el diario cuenta como no soporte.
        """
        self.ensure_one()
        try:
            resolution_type = self.resolution_invoice_id.resolution_type_document_id.id
        except AttributeError:
            resolution_type = None
        return resolution_type == SPR_SUPPORT_DOCUMENT_RESOLUTION_TYPE

    @api.constrains("spr_radian_enabled", "type")
    def _check_spr_radian_enabled(self):
        """RADIAN de receptor solo en diarios de compras que no sean de
        documento soporte (DECISIONS.md #72). La resolucion no va en el
        constrains porque sin Jorels el campo no existe; si se la ponen
        despues, la factura igual oculta el boton
        (``account.move._spr_is_supplier_bill_journal``)."""
        for journal in self.filtered("spr_radian_enabled"):
            if journal.type != "purchase":
                raise ValidationError(_(
                    "El diario %s no es de compras: los eventos RADIAN de receptor "
                    "solo aplican a facturas de proveedor.") % journal.display_name)
            if journal._spr_is_support_document_journal():
                raise ValidationError(_(
                    "El diario %s es de documento soporte: los eventos RADIAN de "
                    "receptor son de las facturas electronicas que emite el "
                    "proveedor, no del documento soporte que emitimos nosotros."
                ) % journal.display_name)
