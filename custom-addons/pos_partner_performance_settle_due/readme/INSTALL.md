No se instala a mano: Odoo lo instala solo cuando están instalados `pos_partner_performance` **y**
`pos_settle_due`. Desinstalar `pos_partner_performance` lo desinstala.

**Solo funciona en bases con Enterprise** (staging y producción): depende de `pos_settle_due`, que
no existe en la base local Community. Es la única excepción a la regla del proyecto de no depender
de módulos Enterprise, y por eso vive en un módulo aparte: para que `pos_partner_performance` se
pueda instalar y probar en local. La carpeta tiene que estar en el código del servidor aunque no se
instale a mano.

Después de instalar, en cada caja: menú ☰ → **Recargar datos**.
