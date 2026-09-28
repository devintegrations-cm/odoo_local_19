## Dependencias

- `point_of_sale` (Odoo 19 Community). No hay otras dependencias ni librerías de Python adicionales.

## Pasos de instalación

Instalar *POS Tip Percentage* desde *Aplicaciones*. El módulo agrega cuatro campos a la
configuración del punto de venta, un ajuste en *Punto de venta › Configuración › Ajustes* y un
archivo JavaScript y una plantilla al POS. No crea menús, modelos ni permisos. Después de instalar o
actualizar, **volver a entrar al POS** desde el backend para que cargue los archivos nuevos.

## Migración desde Odoo 17

- Los campos conservan su nombre técnico en `pos.config` (`iface_tippercent`, `tip_percent1`,
  `tip_percent2`, `tip_percent3`), así que los porcentajes configurados en la 17 se mantienen sin
  script de datos.
- La 17 traía restos de un modelo `pos.tip` que ya no se usaba: un controlador `/pos/tip/name` y una
  línea de permisos. En la 19 se quitaron; el modelo ya estaba comentado en la 17.
- En la 17 la casilla estaba dentro del ajuste *Propinas*. En la 19 es un ajuste aparte, justo
  después de *Propinas*, y solo se ve con *Propinas* activado.
