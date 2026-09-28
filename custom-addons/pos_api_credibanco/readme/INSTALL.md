## Dependencias

- `point_of_sale` (Odoo Community). No hay dependencias de Python adicionales.
- `pos_voucher_num` es **opcional**: si está instalado, el número de aprobación se copia también a
  su campo `voucher_num`. En Odoo 17 era una dependencia obligatoria; en 19 la integración es por
  valor y este módulo se instala sin él.
- **Servicio puente WebSocket** `websocket-api-credibanco` (imagen Docker
  `soportedevlibertario/api_credibanco`), instalado en el equipo de cada caja. Expone el WebSocket
  en el puerto `8080` (ruta `/ws`) y escucha al datáfono en el puerto TCP `8013`. Su código y su
  guía de instalación están en `api_credibanco-main/` dentro de este módulo; Odoo no lo instala ni
  lo arranca.
- **Datáfono Credibanco** en la misma red que la caja, configurado desde su menú técnico con la IP y
  el puerto del equipo de la caja. La integración se desarrolló con un Ingenico Lane/3000.

## Pasos de instalación

- En el equipo de la caja: instalar Docker y levantar el puente con el `stack.yml` de
  `api_credibanco-main/` (ver su `README.md`). En `resource/tcpIp.ini` del puente se asocia la IP de
  cada datáfono con el **nombre de terminal** (por ejemplo `dataf001`) que luego se configura en
  Odoo.
- En Odoo: instalar el módulo desde *Aplicaciones*. Crea el modelo del desglose
  (`pos.payment.credibanco`), el asistente de carga manual, los campos de `pos.payment` y
  `pos.payment.method`, y el menú *Credibanco Settings*.
- Configurar el método de pago (ver *Configuración*) y **volver a entrar al POS** desde el backend
  para que cargue los archivos y los datos nuevos.

## Migración desde Odoo 17

- En 17 la terminal se activaba con la casilla `enable_pos_credibanco` del método de pago. El script
  `migrations/19.0.1.0.0/pre-migration.py` pasa esos métodos a `use_payment_terminal = 'credibanco'`
  e `Integración = Terminal`. Solo toca los métodos que tenían la casilla marcada y que no tenían
  otra terminal asignada, así que se puede ejecutar más de una vez. Si la columna vieja no existe
  (instalación nueva), no hace nada.
- Nombre, host y puerto del datáfono conservan el mismo nombre técnico que en 17
  (`pos_payment_terminal_name`, `pos_ip_host`, `pos_websocket_port`) y no necesitan script. El script
  **no rellena** los valores que en 17 se asumían cuando estaban vacíos (`dataf001`, `localhost`,
  `8080`): un método migrado sin esos datos no se puede guardar hasta completarlos.
- **Número de voucher**: el código de 19 escribe en `voucher_num` (en 17 el campo se llamaba
  `vaucher_num`). El renombre de la columna y de los datos lo hace `pos_voucher_num` en su
  migración `19.0.1.1.0`; este módulo no migra datos de voucher.
- Los ajustes de *Payment Terminals* de 17 (`module_pos_credibanco` en Ajustes) no se portaron.
