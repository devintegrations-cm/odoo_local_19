## 19.0.1.3.0 (2026-10-28)

Funciones que la v17 tenía y la 19 no, más ajustes de producción (DECISIONS.md #62 a #74).

Traídas de la v17:

- **Órdenes de los últimos 12 meses.** El formulario de radicar solo ofrece órdenes con
  `date_order` dentro de una ventana móvil de 12 meses (#62).
- **Campos `spr_*` protegidos por grupo.** `spr_request_ids`/`count` en contacto, orden y factura,
  y los documentos del proveedor, quedan solo para Validador y Responsable. Un "leer todos los
  campos" desde el POS ya no da AccessError (#63).
- **Flete aprobado.** Con producto de flete en Ajustes, `EXTRA_CHARGES` pasa a OK (antes siempre
  era observación). Se reconocen más nombres de flete y también el código de barras o la
  referencia del producto (#64).
- **Unidades con IA.** La línea guarda `unit_code` y `uom_factor`, y cantidad y precio se comparan
  en la unidad de la orden. Revisión de unidades con IA y botón/acción **Validar con IA** (#65).
- **Vista previa del PDF y del XML, y PDF en el chatter.** Widget `spr_preview_binary` (el ojo en
  *Adjuntos*). El modelo hereda `mail.thread.main.attachment`: el PDF queda como adjunto principal
  y se ve al lado del formulario (#66, #67). La migración copia el PDF de las solicitudes que ya
  existen.
- **Pestaña "Orden de compra".** Las líneas de las órdenes al lado de la factura, con subtotal y
  total comparados (#68).
- **Instructivo QWeb.** Reporte dinámico (compañía, NIT, hora de corte, cuenta de cobro en vez de
  XML) generado por el módulo y enlazado a la plantilla del correo, junto a la guía estática (#69).

Ajustes de producción:

- **Factura de proveedor.** El CUFE ya pasaba a la factura (ahora con test), la fecha contable es
  la de la factura y la línea de flete hereda la analítica de la orden (#70).
- **Botón Aprobar.** El Responsable deja en *Aprobada* una solicitud con observaciones ya
  revisada; quién y cuándo quedan en el formulario. Solo desde *Con observaciones*; revalidar o
  volver a borrador descarta la aprobación (#71).
- **Eventos RADIAN de receptor.** Botón **Generar eventos RADIAN** en el encabezado de la factura
  de proveedor: crea y valida en orden el acuse 030, el recibo del bien 032 y la aceptación
  expresa 033, cada uno en su savepoint. Solo sale en facturas publicadas, con fecha y CUFE, sin
  eventos previos y en un diario marcado como *Eventos RADIAN de receptor* (nunca de documento
  soporte). Antes de numerar revisa token, TestSetId y datos del firmante. Si un evento falla, los
  ya aceptados se conservan y el resultado queda en el chatter. Nada se genera solo al publicar.
  Sin dependencia dura de Jorels; `cufe` se copia a `ei_uuid` (#72). Verificar en STG.
- **Tope del flete.** Ajuste *Tope del flete (%)* (10 por defecto, 0 = sin tope): con producto de
  flete, un flete que supera ese porcentaje del subtotal de la mercancía (base contra base, sin
  IVA) queda como observación (#73).
- **Instructivo con los dos PDF** (reporte QWeb y guía estática), y precio en la unidad de la
  orden sin redondear a la moneda: con factor 12 la factura ya no suma 99.999,96 sobre 100.000.
  La revisión de unidades con IA no toca líneas emparejadas a mano y la migración del PDF no deja
  nota en el chatter (#74).

Tests: 209 (193 del módulo). Escáner: 0 BLOQUEA / 0 ROMPE / 1 REVISAR (falso positivo
documentado).

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
