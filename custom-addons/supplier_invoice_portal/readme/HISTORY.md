## 19.0.1.2.0 (2026-10-02)

Migración de Odoo 17 a Odoo 19 Community, con cambios de comportamiento pedidos durante la
validación.

Cambios de comportamiento:

- **Sin documentos no se radica.** Si a la empresa le falta la cámara de comercio, el RUT o la
  certificación bancaria, el formulario de radicar no se muestra ni procesa el envío. En `/my`, en
  la lista y desde la orden de compra se ve el aviso con el enlace a *Mi cuenta*. La creación desde
  el backend no se bloquea.
- **Datos de facturación obligatorios en *Mi cuenta*.** Con Jorels instalado, el proveedor
  habilitado no guarda sin tipo de régimen, tipo de responsabilidad, municipio y email de
  facturación. Odoo 19 exige además código postal para Colombia. La zona del documento con error
  se pinta de rojo y la página baja hasta los errores.
- **Una actividad por validador y "Tomar revisión".** Los validadores se leen de
  `all_user_ids`; en 19, `user_ids` dejaba fuera a los que heredan el grupo. Se crea una actividad
  por validador, sin dejarlos como seguidores. Nuevo campo *Revisor asignado*, botón **Tomar
  revisión**, aviso "En revisión por" para los demás, filtro *Mis revisiones* y *Agrupar por
  revisor*. Crear la factura, rechazar o cancelar cierran la revisión.
- **Analítica en las notas.** En 19 la línea de factura toma la analítica de `purchase_line_id`, y
  las notas no tienen ese vínculo. Ahora la copian de la línea de la orden, como en 17.
- **Precisión de cantidades.** La precisión se llama `Product Unit` en 19. Con el nombre viejo,
  las cantidades se redondeaban a 2 decimales sin dar error.
- **Factura borrador sin número.** En 19 el nombre es `False` hasta confirmar; los mensajes usan
  la referencia del proveedor: "Factura de proveedor en borrador FEQA1001 creada…".
- **Correos a quien radica.** En 19 el autor del mensaje quedaba fuera de los destinatarios: quien
  radicaba no recibía "recibimos su factura" ni "requiere corrección" (una persona natural no
  recibía nada). Ahora les llega a la empresa y a quien radicó, una vez a cada uno.
- **CUFE en la factura de proveedor.** La factura y la nota crédito de proveedor muestran el
  *CUFE / CUDE del proveedor* con botón de copiar y el enlace *Consultar en la DIAN*; se puede
  buscar por CUFE.
- **Montos, cantidades y porcentajes en formato colombiano** en los hallazgos de la validación:
  `$ 1.547.000,00`, `factura 50, pendiente 40`, `19,00 %`.
- **Destinatarios de los correos.** En 19 las plantillas vienen con *Destinatarios por defecto*
  activo y proponían destinatarios de más (por ejemplo *Administrator* en el instructivo). Las
  cinco plantillas usan otra vez su propio destinatario, como en 17.
- **Notas sobre facturas publicadas.** El selector de la factura que corrige la nota solo ofrece
  facturas publicadas. Si el XML apunta a una factura que sigue en borrador, la nota queda con
  observación, no rechazada.
- **Asteriscos en *Mi cuenta*.** Los datos de facturación electrónica y los documentos que faltan
  se marcan con el asterisco de obligatorio.
- **Instructivo.** Agrega el paso de cargar documentos y datos en *Mi cuenta* antes de radicar
  (se actualiza en la migración solo si la plantilla no fue personalizada).
- **Guía del instructivo adjunta.** El botón *Enviar instructivo del portal* abre el correo con
  la guía en PDF ya adjunta (attachment creada o reutilizada en el servidor y enlazada por id),
  en lugar de que compras la adjunte a mano en cada envío (DECISIONS.md #61).
- **JSON técnico solo para usuarios internos**: `validation_json`, `extracted_json` y
  `validation_summary` llevan `groups="base.group_user"`.

Correcciones tras la prueba en navegador (DECISIONS.md #54 a #59):

- Los correos "recibimos su factura" y "requiere corrección" llegan también a quien radicó. Antes,
  Odoo 19 lo excluía por ser el usuario activo.
- La factura y la nota crédito de proveedor muestran el **CUFE / CUDE del proveedor**, con botón
  para copiarlo y enlace *Consultar en la DIAN*.
- Los montos de los hallazgos salen en formato colombiano (`$ 1.547.000,00`). Solo en validaciones
  nuevas o revalidadas.
- La lista de "factura que corrige" de las notas solo trae facturas publicadas. Si el XML apunta a
  una en borrador, la solicitud queda con observación.
- *Mi cuenta*: asterisco de obligatorio en los cuatro datos de Jorels y en los documentos que
  falten; se quitó la insignia "Requerido para radicar".
- El instructivo tiene el paso "Cargue sus documentos y datos".
- El aviso "En revisión por" va en una línea, y el chatter dice "Factura de proveedor en borrador
  <ref> creada desde la solicitud…".

Adaptación a Odoo 19:

- El estado `done` de la orden de compra ya no existe; se quitó de dominios y estados abiertos.
- Listas `<list>`, `<chatter/>` en el formulario, plantillas con `t-out` y campos renombrados en
  19, como `product_uom_id` y `tax_ids`.

Scripts de migración (`migrations/19.0.1.2.0`):

- `pre-migrate`: pasa a `list` las vistas del módulo que sigan como `tree` y renombra
  `view_spr_request_tree` a `view_spr_request_list` si el nuevo xmlid no existe.
- `post-migrate`: reactiva con el ORM, cada una en su savepoint, las vistas del módulo que el
  upgrade dejó inactivas. No toca `portal_my_home_spr`, que puede estar apagada a propósito.
  Actualiza el instructivo para el proveedor solo si conserva el texto de 17.

## 17.0.1.2.0

- Los documentos del proveedor pasan a ser adjuntos del contacto, con vista previa. Solo se
  aceptan PDF de hasta 2 MB y sin contraseña.
- XML obligatorio para quien está obligado a facturar. Zonas de arrastrar y soltar.
- Una orden con una radicación en curso no acepta otra factura.

## 17.0.1.1.0

- Varias órdenes de compra por solicitud.
- Notas crédito y débito, cuenta de cobro (documento soporte), fletes como cargo adicional y
  cierre de fin de mes.
