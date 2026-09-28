## Dependencias

- `pos_restaurant` (Odoo Community), que trae `point_of_sale`. No hay dependencias externas ni
  librerías de Python adicionales.
- `pos_hr` no es dependencia del módulo, pero hace falta en la práctica: el campo de Ajustes solo se
  ve con *Iniciar sesión como empleado* activo, y el control se evalúa sobre el empleado que inició
  sesión en la caja.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. No crea modelos ni permisos de acceso: agrega un campo a la
configuración del punto de venta, un campo a las líneas de pedido y los archivos del POS. Después de
instalar o actualizar, hay que **volver a entrar al POS** desde el backend para que cargue los
archivos nuevos.

## Migración desde Odoo 17

Los campos conservan el nombre técnico y la tabla de relación de Odoo 17:
`able_del_pol_employee_ids` en `pos.config` (tabla `abl_pol_employee_ids`) y `ordered_quantities`
en `pos.order.line`. La lista de empleados autorizados y las cantidades ordenadas de las órdenes
existentes se mantienen sin script de datos.

El archivo `models/pos_session.py` de 17 ya no existe: en Odoo 19 cada modelo declara sus campos
para el POS en `_load_pos_data_fields`. El archivo `security/ir.model.access.csv` de 17 tampoco:
se refería a un modelo de otro módulo y el manifiesto de 17 no lo cargaba.
