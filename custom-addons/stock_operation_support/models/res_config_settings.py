# -*- coding: utf-8 -*-
"""Ajustes del modulo, dentro de Inventario."""

from odoo import api, fields, models

from ..services import vision_adapter


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- Comparacion de cantidades -----------------------------------
    sos_qty_tolerance_pct = fields.Float(
        string="Tolerancia de cantidad (%)",
        config_parameter="sos.qty_tolerance_pct",
        help="Diferencia porcentual admitida entre el soporte y la operacion. "
             "0 = no se admite ninguna diferencia.",
    )
    sos_qty_tolerance_abs = fields.Float(
        string="Tolerancia de cantidad (unidades)",
        config_parameter="sos.qty_tolerance_abs",
        help="Diferencia absoluta admitida. Pasa si la diferencia esta dentro "
             "del porcentaje O dentro de las unidades.",
    )

    # --- Verificaciones ----------------------------------------------
    # Sin config_parameter a proposito: Odoo borra el parametro cuando un
    # Boolean de Ajustes queda en False, y entonces "ausente" se confundiria
    # con "activado". Se guardan a mano en _SOS_MANUAL_BOOLEANS.
    sos_party_check = fields.Boolean(
        string="Verificar quien entrega y quien recibe",
        help="Compara NIT y razon social del soporte con la compania y el "
             "contacto de la operacion. Desactivado, esas reglas no corren.",
    )
    sos_signature_check = fields.Boolean(
        string="Exigir constancia de recibido",
        help="Revisa que el comprobante tenga una marca de recibido escrita a "
             "mano. Si falta: error en remisiones, observacion en facturas; los "
             "tiquetes de caja no la necesitan. Desactivado, no se exige.",
    )
    sos_auto_validate = fields.Boolean(
        string="Validar la recepcion si el soporte cuadra exacto",
        help="Si el soporte de una recepcion queda aprobado y las cantidades "
             "coinciden exactamente con lo pedido, la recepcion se valida sola. "
             "Nunca con productos con lote o serie, ni con diferencias dentro "
             "de la tolerancia.",
    )
    sos_company_nit = fields.Char(
        string="NIT de la compania", config_parameter="sos.company_nit",
        help="Se compara contra la parte que corresponda segun el tipo de "
             "operacion. Vacio = NIT de la compania activa.",
    )

    # --- IA de vision -------------------------------------------------
    sos_vision_enabled = fields.Boolean(
        string="Habilitar lectura con IA de vision",
        help="Sin esto, el soporte se adjunta y se captura a mano.",
    )
    sos_vision_provider = fields.Selection(
        [("anthropic", "Anthropic (Messages API)"),
         ("http", "Servicio HTTP propio")],
        string="Proveedor de vision", default="anthropic",
        config_parameter="sos.vision_provider",
    )
    sos_vision_url = fields.Char(
        string="URL del servicio de vision", config_parameter="sos.vision_url",
    )
    sos_vision_api_key = fields.Char(
        string="API key de vision", config_parameter="sos.vision_api_key",
    )
    sos_vision_model = fields.Char(
        string="Modelo", default=vision_adapter.DEFAULT_MODEL,
        config_parameter="sos.vision_model",
    )
    sos_vision_timeout = fields.Integer(
        string="Timeout de vision (s)", default=vision_adapter.DEFAULT_TIMEOUT,
        config_parameter="sos.vision_timeout",
    )

    # --- Conexion de prueba por CLI local ------------------------------
    sos_vision_cli_enabled = fields.Boolean(
        string="Conexion de prueba por CLI local",
        help="Solo para desarrollo: apunta la Messages API al puente local "
             "anthropic_cli_bridge y usa una CLI con sesion iniciada, sin API "
             "key. Mientras este activa, el proveedor y la API key de arriba "
             "no se usan.",
    )
    sos_vision_cli_tool = fields.Selection(
        [(tool, tool) for tool in vision_adapter.CLI_TOOLS],
        string="Herramienta de CLI", default=vision_adapter.CLI_TOOLS[0],
        config_parameter="sos.vision_cli_tool",
    )
    sos_vision_cli_url = fields.Char(
        string="URL del puente", default=vision_adapter.DEFAULT_CLI_URL,
        config_parameter="sos.vision_cli_url",
    )
    sos_vision_cli_api_key = fields.Char(
        string="API key del puente", config_parameter="sos.vision_cli_api_key",
    )
    sos_vision_cli_timeout = fields.Integer(
        string="Timeout de la CLI (s)", default=vision_adapter.DEFAULT_CLI_TIMEOUT,
        config_parameter="sos.vision_cli_timeout",
    )

    # (campo, parametro, valor por defecto)
    _SOS_MANUAL_BOOLEANS = (
        ("sos_party_check", "sos.party_check", True),
        ("sos_signature_check", "sos.signature_check", True),
        ("sos_auto_validate", "sos.auto_validate", True),
        ("sos_vision_enabled", "sos.vision_enabled", False),
        ("sos_vision_cli_enabled", "sos.vision_cli_enabled", False),
    )

    @api.model
    def get_values(self):
        values = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        for field_name, key, default in self._SOS_MANUAL_BOOLEANS:
            raw = params.get_param(key)
            values[field_name] = default if raw in (None, False, "") \
                else str(raw).lower() in ("true", "1")
        return values

    def set_values(self):
        super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        for field_name, key, _default in self._SOS_MANUAL_BOOLEANS:
            params.set_param(key, "True" if self[field_name] else "False")
