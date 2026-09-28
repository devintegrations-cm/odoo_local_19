## Dependencias

- `pos_restaurant` (Odoo 19 Community), que a su vez instala `point_of_sale`. De ahí vienen el campo
  *Comensales* de la orden y los métodos del POS que usa el módulo. No hay otras dependencias ni
  librerías de Python adicionales.

## Pasos de instalación

Instalar *Ask Number of Customers* desde *Aplicaciones*. El módulo agrega tres campos a la
configuración del punto de venta y un archivo JavaScript al POS. No crea menús, modelos ni permisos.
Después de instalar o actualizar, **volver a entrar al POS** desde el backend para que cargue el
archivo nuevo.

## Migración desde Odoo 17

- La casilla conserva su nombre técnico (`enable_obligatory_ask_number_customers` en `pos.config`),
  así que los puntos de venta que la tenían marcada en la 17 la siguen teniendo. No hace falta
  script de datos.
- Los campos nuevos `number_customers_min` y `number_customers_max` se crean con sus valores por
  defecto, 1 y 20: el mismo rango que la 17 tenía escrito en el JavaScript. El comportamiento no
  cambia hasta que alguien modifique el rango.
- En la 17 la pregunta salía al pulsar *Pago* en la pantalla de productos. En la 19 sale al entrar a
  la pantalla de pago y, como respaldo, al pulsar *Validar* (ver *Uso*).
