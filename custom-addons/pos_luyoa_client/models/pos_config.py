# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

# URL del API donde está registrado y habilitado el negocio (validado contra
# la API real: app.luyoa.com responde 401 para estas credenciales).
LUYOA_DEFAULT_BASE_URL = "https://demo.luyoa.com/api/external/v1"

# Credenciales que NUNCA deben llegar al navegador: el POS solo necesita
# `luyoa_client_enabled`; la consulta a Luyoa la hace el servidor.
LUYOA_SECRET_FIELDS = ("luyoa_integration_uid", "luyoa_business_uid", "luyoa_api_token")


class PosConfig(models.Model):
    _inherit = "pos.config"

    luyoa_client_enabled = fields.Boolean(
        string="Botón Luyoa",
        help=(
            "Muestra el botón 'Luyoa' en la pantalla de la orden para "
            "escanear la tarjeta de lealtad del cliente y asignarlo."
        ),
    )
    # Las credenciales solo las lee el responsable del POS: el cajero no las
    # necesita (el servidor las lee con sudo al consultar) y así tampoco
    # viajan en la carga de datos del POS (`read([])` usa `fields_get`, que
    # omite los campos sin acceso). Obligatorias en la práctica (sin
    # cualquiera de ellas Luyoa responde 401); no se marcan `required` a
    # nivel ORM para no bloquear configs que no usan Luyoa: la vista las
    # exige con el botón activo y `res.partner._pos_luyoa_config_error`
    # bloquea el uso.
    luyoa_integration_uid = fields.Char(
        string="Luyoa Integration UID",
        groups="point_of_sale.group_pos_manager",
        help=(
            "Identificador de la integración (partner). Lo entrega Luyoa al "
            "registrar la integración; debe ser el de la misma integración "
            "que generó el token."
        ),
    )
    luyoa_business_uid = fields.Char(
        string="Luyoa Business UID",
        groups="point_of_sale.group_pos_manager",
        help=(
            "Identificador del negocio en el dashboard de Luyoa. Cada token "
            "de autenticación pertenece a un negocio."
        ),
    )
    luyoa_api_token = fields.Char(
        string="Luyoa API Token",
        groups="point_of_sale.group_pos_manager",
        help=(
            "Token de autenticación del negocio, generado en el dashboard de "
            "Luyoa. Es información sensible: guárdela con cuidado."
        ),
    )
    luyoa_base_url = fields.Char(
        string="Luyoa API URL",
        # El path completo es /api/external/v1/customer/:customerUID
        # (docs.luyoa.dev). Las credenciales valen solo en el entorno donde
        # se generaron: demo y app no son intercambiables.
        default=LUYOA_DEFAULT_BASE_URL,
        help=(
            "Base URL del API de Luyoa. Debe ser el entorno donde está "
            "registrado el negocio (hoy demo.luyoa.com). No es la web de la "
            "tarjeta del cliente."
        ),
    )

    @api.onchange("luyoa_base_url")
    def _onchange_luyoa_base_url(self):
        """Advierte al cambiar la URL: las credenciales están ligadas a un
        entorno y apuntar a otro deja el botón respondiendo 'credenciales
        inválidas' en todas las cajas que usen esta configuración."""
        saved = self._origin.luyoa_base_url
        if saved and self.luyoa_base_url != saved:
            return {"warning": {
                "title": _("Cambio de URL de Luyoa"),
                "message": _(
                    "Va a cambiar la URL del API de Luyoa de\n%(old)s\na\n%(new)s\n\n"
                    "Las credenciales solo funcionan en el entorno donde se "
                    "generaron. Si no está seguro, descarte los cambios.",
                    old=saved, new=self.luyoa_base_url or "",
                ),
            }}
        return None

    def _load_pos_data_read(self, records, config):
        # Defensa en profundidad: el responsable del POS sí puede leer las
        # credenciales, pero tampoco deben viajar a su navegador.
        read_records = super()._load_pos_data_read(records, config)
        for record in read_records:
            for fname in LUYOA_SECRET_FIELDS:
                record.pop(fname, None)
        return read_records
