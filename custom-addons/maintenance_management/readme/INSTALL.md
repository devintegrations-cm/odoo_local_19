## Dependencias

- Módulos de Odoo Community: `maintenance`, `portal`, `purchase` y `stock`. No requiere librerías
  de Python adicionales: el QR se genera con el generador de códigos de barras que ya trae Odoo.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones* (aparece como *Gestión Integral de Mantenimiento*). La
instalación crea:

- las secuencias *Mantenimiento: Número de Activo* (prefijo `ACT`) y *Mantenimiento:
  Incidencia/Solicitud* (prefijo `INC`), ambas de 5 dígitos y compartidas por todas las compañías;
- el parámetro del sistema `maintenance_management.enforce_checklist` con valor `True`;
- el menú *Mantenimiento › Configuración › Plantillas de Checklist*;
- la acción *Asignar Nº de activo, QR y serial* en el menú *Acción* de los equipos;
- los reportes *Etiqueta QR del Equipo* y *Orden de Mantenimiento*.

Los equipos que ya existían antes de instalar el módulo quedan sin número de activo, sin serie
automática y sin token de portal (el QR no abre la hoja de vida). Para completarlos, en
*Mantenimiento › Equipo* seleccionarlos en la lista y ejecutar *Acción › Asignar Nº de
activo, QR y serial*. Solo llena lo que falta, así que se puede repetir sin riesgo.

En bases con datos de demostración se cargan además tres categorías (*Neveras*, *Molinos*,
*Máquinas de espresso*) con su plantilla de checklist.

## Migración desde Odoo 17

El módulo conserva el nombre, los modelos y los nombres técnicos de los campos de la versión 17,
por lo que los datos existentes se mantienen sin script de migración. Los cambios de la migración
fueron de forma: la restricción de número de activo único pasó a la sintaxis `models.Constraint`,
las vistas de lista usan `list` en lugar de `tree` y la hoja de vida del portal dejó de mostrar el
campo *Ubicación* (`location`) del equipo, que ya no existe en `maintenance` de Odoo 19. La tienda
se sigue mostrando como *Tienda / Almacén*.
