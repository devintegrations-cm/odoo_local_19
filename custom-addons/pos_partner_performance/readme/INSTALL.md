Instalar **manualmente** desde *Aplicaciones* (no tiene instalación automática): es una mejora de
rendimiento que se decide por entorno.

Depende de `point_of_sale` y `pw_pos_default_customer`.

Si la base tiene `pos_settle_due` (Enterprise), al instalar este módulo Odoo instala también
`pos_partner_performance_settle_due`. Desinstalar este módulo desinstala también el puente. Las dos
carpetas tienen que estar en el código del servidor.

Después de instalar o desinstalar, en cada caja: menú ☰ → **Recargar datos**, para que el POS tome
los cambios.
