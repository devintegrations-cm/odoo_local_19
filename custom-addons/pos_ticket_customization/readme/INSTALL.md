## Dependencias

- `point_of_sale`. No hay dependencias externas ni librerías de Python adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. Crea el modelo `pos.receipt.custom.block`, sus permisos y
una regla multicompañía. Después de instalar o actualizar, hay que **volver a entrar al POS** desde
el backend (o recargar la pestaña) para que cargue los archivos nuevos y los bloques.

## Permisos

- **Administrador del POS** (`point_of_sale.group_pos_manager`) y **Ajustes** (`base.group_system`):
  lectura y escritura de bloques.
- **Usuario del POS** (`point_of_sale.group_pos_user`): solo lectura, que es lo que necesita la
  caja para cargar los bloques al abrir la sesión.

## Migración desde Odoo 17

El módulo conserva el nombre técnico, el modelo y los nombres de campo de la versión 17, así que
los bloques ya configurados se mantienen sin script de datos. Lo que cambió es el código del POS:
la carga de datos pasó al contrato `pos.load.mixin` de Odoo 19 y el ticket se arma a partir del
pedido vivo en lugar de `export_for_printing()`.
