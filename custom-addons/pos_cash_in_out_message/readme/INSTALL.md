## Dependencias

- `pos_closing_validation` (módulo propio de este repositorio). Trae a su vez `point_of_sale`. No
  hay dependencias externas ni librerías de Python adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. No crea modelos nuevos ni permisos: agrega dos campos a
la configuración del punto de venta y los archivos del POS. Después de instalar o actualizar, hay
que **volver a entrar al POS** desde el backend para que cargue los archivos nuevos.

## Migración desde Odoo 17

En Odoo 17 el módulo se llamaba `cash_in_out_message`. Al instalarse, un `pre_init_hook`
(`hooks.py`) renombra el módulo viejo en la base: pasa sus xmlids (`ir_model_data`), su registro
en `ir_module_module` y las dependencias registradas a `pos_cash_in_out_message`. Las consultas son
`UPDATE` que no hacen nada si el nombre viejo no existe, así que el hook se puede ejecutar más de
una vez sin efecto.

Los campos de configuración conservan el mismo nombre técnico que en 17
(`cash_in_out_message_enabled` y `cash_in_out_message` en `pos.config`), por lo que la
configuración existente se mantiene sin script de datos.
