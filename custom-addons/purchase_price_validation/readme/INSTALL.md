## Dependencias

- `purchase`, `product` y `stock`, todos de Odoo Community. No hay dependencias externas ni
  librerías de Python adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. Agrega el campo *Porcentaje de variación* al producto, dos
opciones en los ajustes de Inventario y los dos asistentes de aviso. Las dos validaciones quedan
**activas** desde la instalación.

## Migración desde Odoo 17

No hay script de datos: el campo del producto (`porcent_variation`) y los parámetros de
configuración conservan el mismo nombre técnico que en 17, así que los porcentajes ya cargados y
el estado de las opciones se mantienen.

Cambios de código en la migración:

- El filtro de productos pasó de `type == 'product'` a `type == 'consu'`, porque Odoo 19 eliminó el
  tipo *Almacenable*. Esto **amplía** el alcance (ver *Limitaciones conocidas*).
- La recepción recorre `move_ids` en lugar de `move_ids_without_package`, que ya no existe en 19.
