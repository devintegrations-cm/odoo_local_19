## Dependencias

- `point_of_sale`. No hay otras dependencias de Odoo ni librerías de Python adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. Crea dos modelos (`pos.payment.customer.restriction` y
`pos.payment.restriction.field`) con estos permisos: el grupo *Punto de venta / Administrador* puede
crear, editar y borrar; el grupo *Punto de venta / Usuario* solo leer, que es lo que necesita el
POS. Después de instalar o actualizar, hay que **volver a entrar al POS** desde el backend para que
cargue los archivos nuevos.

## Migración desde Odoo 17

Los modelos, los campos y la tabla de clientes autorizados (`pos_payment_restrict_partner_rel`)
conservan el nombre técnico de la versión 17, así que las restricciones existentes se mantienen sin
script de datos.

Al actualizar desaparece la acción *Crear factura electrónica agrupada*: dependía del diario
electrónico del POS (`electronic_invoice_journal_id`), que Jorels 19 eliminó. Tampoco se porta el
archivo de 17 que desactivaba dos vistas de búsqueda de `pos_sale`, porque `pos_sale` no está
instalado.
