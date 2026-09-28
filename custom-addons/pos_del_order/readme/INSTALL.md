## Dependencias

- `point_of_sale` y `pos_hr` (Odoo Community). `pos_hr` hace falta porque el permiso se asigna a
  empleados (`hr.employee`) y se evalúa sobre el empleado que inició sesión en el POS. No hay
  dependencias externas ni librerías de Python adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. No crea modelos ni permisos de acceso: agrega un campo a
la configuración del punto de venta y dos archivos JavaScript al POS. Después de instalar o
actualizar, hay que **volver a entrar al POS** desde el backend para que cargue los archivos
nuevos.

## Migración desde Odoo 17

El campo conserva el nombre técnico y la tabla de relación de Odoo 17 (`able_del_employee_ids`,
`pos_config_able_del_employee_rel`), así que la lista de empleados autorizados se mantiene sin
script de datos.

Cambió el identificador de la vista de Ajustes (`view_hr_employee_inh_form` pasó a
`res_config_settings_view_form_inherit_pos_del_order`). Al actualizar, Odoo borra la vista vieja y
crea la nueva, sin intervención manual.
