# Decisiones de diseno

Registro de las decisiones tomadas donde el spec era ambiguo o chocaba con el
entorno. Cada una dice **que** se decidio y **por que**.

## Entorno

- **Odoo 17.0** confirmado leyendo `odoo/release.py` dentro de la imagen
  `odoo:17.0`: `17.0-20260119`, `(17, 0, 0, 'final', 0, '')`.
- El entorno local es Docker Compose (`odoodkr17/stack.yml`), no Odoo.sh. El
  destino de produccion sigue siendo Odoo.sh y el codigo no asume nada del
  entorno local.

## 1. `pypdf` no se declara en `external_dependencies`

La imagen `odoo:17.0` no trae `pypdf`. Declararlo en el manifest impediria
instalar el modulo en el entorno local y, por lo tanto, verificar cada fase.

- `lxml` (4.8.0, ya presente) si se declara.
- `pypdf` se importa de forma diferida y opcional en
  `services/ocr_adapter.pdf_page_count()`: si no esta, devuelve `None` y el
  flujo sigue.
- Para Odoo.sh se agrega `pypdf` al `requirements.txt` de la raiz del repo.

En el MVP el OCR es un servicio externo, asi que `pypdf` solo sirve para
comprobar que el PDF se puede abrir. No justifica bloquear la instalacion.

## 2. Campo `cufe` en `account.move` y su relacion con Jorels

`l10n_co_edi_jorels` ya guarda un CUFE en `account.move.ei_uuid`, pero ese es el
CUFE de las facturas que **nosotros emitimos**. El campo `cufe` que agrega este
modulo es el del documento que el **proveedor** recibio de la DIAN. Son cosas
distintas y el nombre `cufe` estaba libre.

- La constraint de unicidad se acota a `move_type in ('in_invoice', 'in_refund')`
  y `state != 'cancel'`, por compania. Si fuera global chocaria el dia que otro
  modulo escriba un CUFE de venta en el mismo campo.
- **No** se declara dependencia de Jorels en el manifest: el modulo debe poder
  instalarse en otras instancias del grupo que no lo tengan.

## 3. Comparacion de NITs

`res.partner.vat` en Colombia llega inconsistente: con DV, sin DV, con guiones o
con puntos. Se normaliza a solo digitos y se compara **sin digito de
verificacion** (`services/dian_xml_parser.same_nit`). Como los NIT no tienen
largo fijo (8 o 9 digitos de persona juridica, cedulas de 6 a 10), no se recorta
a 9 a ciegas: son iguales si coinciden digito a digito o si uno es el otro mas
exactamente un digito al final. (Corregido en la revision de la Fase 5: el
recorte fijo rechazaba a personas naturales con DV pegado.)

## 4. Moneda distinta a la de la compania

Multi-moneda esta fuera del alcance del MVP, pero un XML puede venir en USD.
En vez de crear una factura con montos silenciosamente equivocados, la Fase 2
agrega la regla `CURRENCY_UNSUPPORTED` con nivel **error**.

## 5. Como se combinan las dos tolerancias de monto

El spec define `spr_amount_tolerance_pct` y `spr_amount_tolerance_abs` sin decir
como se combinan. Se usa el criterio mas permisivo: la diferencia pasa si esta
dentro del porcentaje **o** dentro del monto absoluto. Es lo que uno espera con
facturas pequenas, donde 0.5 % son veinte pesos.

Para el **precio unitario** (`PRICE_UNIT_MISMATCH`) se usa solo el porcentaje:
con el absoluto, un sobreprecio de 900 pesos por unidad pasaba sin observacion
en una linea de 10.000 unidades. (Revision de la Fase 5.)

## 6. Pendiente por facturar de la orden de compra

Odoo 17 no expone un campo directo. Se calcula como `order.amount_total` menos
lo facturado **linea por linea**: la suma de `price_total` de las lineas de
factura no canceladas ligadas a cada `purchase.order.line`. No se resta el
total de cada factura porque `invoice_ids` incluye facturas que agrupan varias
ordenes o traen lineas extra (flete), y descontarlas enteras rechazaba facturas
legitimas. (Revision de la Fase 5.)

## 7. URL del catalogo DIAN

El spec escribe el parametro como `documentKey`; Jorels usa `documentkey` en
minuscula y es el que responde. Se usa el de Jorels. El catalogo devuelve HTML,
no JSON, asi que la verificacion es heuristica y `dian_cufe_check` puede quedar
en `error` o `skipped` **sin bloquear nunca** el flujo.

## 8. Formato y normalizacion del CUFE

`^[0-9a-f]{96}$` (SHA-384 en hexadecimal). Se normaliza a minusculas y sin
espacios antes de guardar y de comparar duplicados, tanto en `create` como en
`write`. El campo lleva indice.

## 9. Textos de interfaz en espanol, sin archivo `.po`

Todas las instancias del grupo son colombianas y una sola persona administra IT.
Un `i18n/es.po` duplicaria el mantenimiento sin beneficio real. Los nombres
tecnicos (modelos, campos, metodos) siguen en ingles, como pide el spec.

Los textos van sin tildes en el codigo fuente para evitar problemas de
codificacion en entornos mal configurados; las tildes reales se pueden agregar
despues via traduccion si hiciera falta.

## 10. Secuencia sin compania

`ir.sequence` con `company_id = False`: multi-compania no esta en el MVP y una
secuencia global es una cosa menos que configurar al instalar en otra instancia.

## 11. El estado `validating` se mantiene aunque la validacion sea sincrona

En el MVP el pipeline corre dentro de la misma transaccion, asi que
`validating` casi no se ve. Se deja declarado porque es el punto de enganche
para mover el pipeline a una cola (cron o `queue_job`) despues, sin migracion de
datos.

## 12. El PDF obligatorio se valida en el pipeline, no con `required=True`

`pdf_file` no es `required` a nivel de modelo: eso obligaria a tener el PDF
antes de poder guardar un borrador desde el backend. La obligatoriedad se
verifica en `_run_pipeline()` (`UserError` si falta) y se exigira tambien en el
formulario del portal (Fase 3).

## 13. Helpers de NIT y CUFE dentro de `dian_xml_parser`

`normalize_nit`, `strip_dv`, `same_nit`, `normalize_cufe` e `is_valid_cufe`
viven en `services/dian_xml_parser.py` en vez de en un `utils.py` aparte, para
no agregar archivos fuera del arbol acordado. Son funciones puras y las importan
tanto los modelos como `validation_rules`.

## 14. Alcance real de la Fase 1

Lo que quedo como esqueleto documentado, no implementado:

- `services/validation_rules.run_rules()` devuelve un unico hallazgo
  `RULES_PENDING` de nivel *warning*. Es deliberado: asi ninguna solicitud queda
  marcada como *aprobada* mientras las reglas duras no existan. Se reemplaza en
  la Fase 2.
- `services/line_matcher.match_lines()` devuelve lista vacia. Fase 2.
- `get_ocr_adapter()` y `get_ai_adapter()` siempre devuelven la implementacion
  *noop*, y dejan un WARNING en el log si el ajuste esta habilitado. Fase 4.
- `action_create_bill()` **no** se declara todavia: un metodo que existe y
  revienta es peor que un metodo que no existe. Fase 2.

## 15. Las vistas de lista usan `<tree>`, no `<list>`

En Odoo **17.0** el campo `ir.ui.view.type` todavia no acepta el valor `list`:
usar `<list>` como etiqueta raiz falla al instalar con

```
ValueError: Wrong value for ir.ui.view.type: 'list'
```

El renombramiento de `<tree>` a `<list>` es de Odoo 18.0. Aqui se usa `<tree>`
y `view_mode = "tree,form"`. Verificado contra la imagen `odoo:17.0`
(`17.0-20260119`), no asumido.

## 16. Revalidar conserva los emparejamientos manuales, por posicion

Las lineas del request se recrean desde el documento en cada validacion (el
XML manda). Antes de borrarlas se guarda `{posicion: linea de OC}` de las que
tienen `match_method = manual` y se vuelven a aplicar a la misma posicion. Es
por posicion y no por codigo porque las lineas sin codigo son justo las que
requieren emparejamiento manual.

## 17. Consistencia del total: se aceptan varias lecturas del UBL

En los XML DIAN reales `AllowanceTotalAmount` a veces resume descuentos de
linea (ya restados de `LineExtensionAmount`) y a veces descuentos de documento
(que si restan del total). La regla `AMOUNT_INCONSISTENT` acepta el total si
cuadra con **cualquiera** de: `subtotal + impuestos`, `subtotal + impuestos -
descuentos + recargos`, o eso menos el anticipo. Es una observacion, no un
error, porque el total que manda es el de la OC (`AMOUNT_TOTAL`).

## 18. El descuento de la factura se traslada como porcentaje implicito

Al crear la factura se usa la cantidad y el precio unitario del proveedor, no
los de la OC, y el descuento de la OC **no** se copia. Si `subtotal < cantidad
x precio`, la diferencia se convierte en `discount` porcentual de la linea de
factura. Asi el borrador reproduce lo que dice el documento del proveedor y las
diferencias con la OC quedan visibles como observaciones, no escondidas.

## 19. Borrar la factura borrador devuelve la solicitud a *Aprobada*

`account.move.unlink` busca solicitudes ligadas y las deja en `approved` sin
factura. No se hace lo mismo al **cancelar** la factura: una factura cancelada
sigue existiendo y su CUFE queda liberado por la constraint, asi que el
validador decide si crea otra o rechaza la solicitud.

## 20. Rechazar pide motivo con un asistente

`action_reject` exige motivo. El boton del formulario abre un
`TransientModel` de un solo campo en vez de rechazar directo, porque ese texto
lo va a leer el proveedor en el portal (Fase 3). Solo el grupo *Responsable*
puede rechazar, como dice el README.

## 21. El controlador del portal corre con `sudo` y filtra por proveedor

El usuario portal no tiene acceso a `purchase.order.line`, `product.product`,
`account.move` ni a escribir en la solicitud, y no se le va a dar: el pipeline
toca todo eso. Por eso el controlador crea la solicitud y corre el pipeline con
`sudo`, y compensa con dos reglas fijas: el proveedor es siempre
`commercial_partner_id` del usuario conectado, y el id de la orden que viene
del formulario solo se acepta si esta en la lista de ordenes abiertas de ese
proveedor. Las lecturas (lista y detalle) si van con el usuario real y la
record rule; el detalle acepta `access_token` para el enlace del correo.

## 22. La validacion del formulario ocurre antes de crear el registro

PDF presente y con firma `%PDF`, XML parseable, CUFE con formato y coincidente
con el XML, orden valida: todo se comprueba en memoria. Si algo falla se
re-renderiza el formulario con los errores y no queda nada en la base. Si
falla el pipeline despues de crear (caso raro), un `savepoint` deshace la
creacion. Asi el proveedor no ve "solicitudes fantasma" rechazadas por errores
de captura, y `CUFE_DUPLICATE` no se dispara por sus propios reintentos.

## 23. Al proveedor se le escribe una sola vez por validacion

`_apply_findings` envia el correo solo si `validation_json` estaba vacio, es
decir en la primera validacion. Las revalidaciones que hace contabilidad
(despues de emparejar lineas a mano, por ejemplo) no le cambian nada al
proveedor y solo generarian ruido. Rechazo manual y factura creada si avisan
siempre, porque son decisiones.

## 24. Los archivos se sirven por `/web/content` sin controlador propio

El PDF y el XML del detalle se descargan con
`/web/content/supplier.payment.request/<id>/pdf_file`. Odoo aplica ahi la
misma ACL y record rule del modelo, asi que el proveedor solo baja lo suyo.
No hace falta un endpoint aparte. Nota: `/web/content` ignora `access_token`
en modelos que no son `ir.attachment`, asi que el enlace del correo sirve para
ver el detalle pero la descarga exige sesion; es aceptable para el MVP.

## 25. Anthropic se llama con `requests`, no con el SDK `anthropic`

La recomendacion general para codigo Python es el SDK oficial. Aqui no aplica:
la imagen `odoo:17.0` no lo trae, el modulo no agrega dependencias Python
(ver #1) y la llamada es una sola (`POST /v1/messages` con salida
estructurada). `requests` ya viene con Odoo. Si en el futuro se necesita
streaming, reintentos finos o herramientas, se agrega el SDK al
`requirements.txt` y se reemplaza `AnthropicAiAdapter` sin tocar el contrato.

Detalles que si se tomaron de la referencia de la API y no de memoria:
`output_config.format` con `type: json_schema` y `additionalProperties: false`
en todos los objetos; no se envia `thinking` (el modelo por defecto lo trae
adaptativo); no se envia `temperature`; `stop_reason` `refusal` y `max_tokens`
se tratan como fallo.

## 26. *No encontrado* en la DIAN es observacion, no error

El catalogo DIAN responde HTML sin API y la lectura es heuristica. El caso
positivo (CUFE existente) no se pudo verificar en desarrollo porque no habia un
CUFE real disponible. Rechazar facturas validas por una heuristica sin
calibrar seria peor que dejar pasar una observacion que contabilidad revisa en
segundos con el boton *Consultar DIAN*. Cuando se calibre con documentos reales
se puede subir a error cambiando una linea en `_rule_dian_cufe_check`.

## 27. Sin datos extraidos, las reglas de montos y lineas no corren

Sin XML y con el OCR apagado o caido, la solicitud no tiene montos ni lineas.
Correr `AMOUNT_TOTAL` o `LINES_MATCHED` en ese estado daria errores vacios
("total cero", "sin lineas") y la solicitud quedaria rechazada por una falla
nuestra, no del proveedor. En su lugar corre solo el bloque `ALWAYS_RULES`
(CUFE, duplicados, estado de la OC, DIAN) mas la observacion
`MANUAL_CAPTURE_REQUIRED`, y la solicitud queda *Con observaciones* con
actividad para el validador. La condicion es "no hay lineas y el total es
cero" sobre el request, no sobre el origen: en cuanto contabilidad captura
datos y revalida, corren todas.

## 28. El modelo por defecto de Anthropic es `claude-opus-5`

En la Fase 1 quedo `claude-sonnet-5`. Se cambia a `claude-opus-5`, que es el
modelo recomendado actualmente para uso general. El emparejamiento de lineas
es una tarea corta (unas decenas de lineas por factura), asi que la diferencia
de costo por factura es de centavos. Si el volumen crece, `claude-sonnet-5`
se configura en Ajustes sin tocar codigo.

**Actualizado el 2026-10-01:** el defecto pasa a `claude-opus-5-5`, el Opus
vigente y 20 % mas barato por token. La peticion no cambia: no fuerza
`tool_choice` ni desactiva `thinking`, que es lo que Opus 5.5 rechaza. Probado
contra la API real con la llave de staging (7,8 s, emparejo bien).

## 29. La conexion de prueba por CLI pasa por un puente HTTP, no por subprocesos en Odoo

Se agrega un tercer camino para la IA: las CLI con sesion iniciada del
administrador (`claude` con perfil, `agy`, `codex`), para probar el
emparejamiento sin API key.

La primera version ejecutaba las CLI con `subprocess` dentro de Odoo. Se
descarto el mismo dia porque Odoo corre en Docker (y en produccion en Odoo.sh),
donde no hay CLI ni sesion interactiva, y montar la home del anfitrion en el
contenedor acopla el modulo a la maquina. En su lugar:

- Un proyecto aparte, `claude_projects/anthropic_cli_bridge`, **emula la
  Messages API de Anthropic** y ejecuta la CLI que diga el campo `model`.
  Corre en el equipo del administrador con la biblioteca estandar de Python.
- En el modulo, `CliAiAdapter` es una subclase de `AnthropicAiAdapter` con la
  URL del puente y la herramienta como `model`. Cero codigo nuevo de protocolo
  y nada que ejecutar en el servidor de Odoo.
- Las CLI corren sin herramientas y en carpeta temporal, nunca por shell (eso
  vive en el puente, que es quien toca el sistema).
- Es un ajuste separado del proveedor y manda sobre el. Queda marcado como
  *solo para desarrollo*.
- Cualquier fallo (puente apagado, CLI sin sesion, timeout) devuelve la
  respuesta vacia del contrato, igual que los otros adaptadores.

## 30. Correcciones de la revision de codigo de la Fase 5

Hallazgos de `/code-review` sobre el modulo completo (2026-09-10) que cambiaron
comportamiento; los tests cubren cada uno.

- **El portal no tiene `create` por ORM.** El controlador crea con `sudo` y
  valida todo antes; el permiso de creacion para `base.group_portal` permitia
  fabricar solicitudes por JSON-RPC con estado y factura a dedo. Se quita del
  CSV y de la regla de registro.
- **La consulta DIAN se puede apagar de verdad.** Odoo borra el
  `ir.config_parameter` cuando un Boolean de Ajustes queda en False, y el
  codigo tomaba "ausente" como "activado". El campo ya no usa
  `config_parameter`: se guarda a mano como `"True"`/`"False"`.
- **CUFE normalizado tambien en `account.move`**, para que una factura manual
  con el CUFE en mayusculas no escape a la deteccion de duplicados.
- **Un CUFE malformado en el XML no aborta la validacion**: no se escribe en
  el request y la regla `CUFE_FORMAT` lo reporta. El portal lo rechaza con
  mensaje claro en el formulario.
- **Los emparejamientos manuales se reconocen por contenido** (codigo,
  descripcion, precio), no por posicion: reordenar las lineas con el handle
  los movia a otra linea.
- **Rechazo manual**: no se puede rechazar una solicitud facturada o
  cancelada, y una rechazada por el Responsable no se revalida hasta
  "Volver a borrador" (que limpia el motivo).
- Tambien: tolerancia porcentual para precios unitarios (#5), pendiente de la
  OC linea por linea (#6), comparacion de NIT sin largo fijo (#3), y la fecha
  del OCR se descarta si no es AAAA-MM-DD.

**Quedan anotados sin cambiar** (decision pendiente del usuario):

- El pipeline corre dentro de la peticion HTTP del portal y la suma de los
  timeouts (OCR 60 s + DIAN 15 s + IA 45 s) roza el `limit_time_real` de 120 s
  de Odoo (DECISIONS #11). Mitigacion posible: bajar los timeouts o pasar el
  pipeline a un cron.
- Una tolerancia de monto en 0 vuelve al valor por defecto por el mismo
  mecanismo de los Boolean (Odoo borra el parametro cuando el Float es 0).
- Con OCR que devuelve totales pero ninguna linea, la solicitud se rechaza por
  `LINES_MATCHED` en vez de pedir captura manual.

## 31. La consulta al catalogo DIAN queda apagada por defecto: exige captcha

Probado el 2026-09-11 con un CUFE real (factura FEDC2437 de un proveedor,
validada por la DIAN el 2026-09-07): `GET /document/searchqr?documentkey=...`
redirige al buscador `/User/SearchDocument`, y el POST de ese formulario con
CUFE y NIT responde *"Falta Token de validacion de captcha"*. No hay captcha
visible ni API publica; el token lo genera JavaScript en el navegador.

Decisiones:

- **No se intenta saltar el captcha.** La verificacion automatica queda
  fuera del alcance mientras la DIAN lo exija.
- **El buscador ya no se interpreta como "no encontrado"** (antes si, y con
  esta factura real daba un falso *no aparece en la DIAN*). Ahora es `error`:
  *no se pudo verificar*.
- `error` y `not_found` son **observaciones con el enlace al buscador**, para
  que contabilidad verifique a mano. Antes `error` era silencioso (nivel ok);
  con la consulta activa, callar que el CUFE no se verifico es peor que una
  observacion.
- El ajuste queda **apagado por defecto** (antes activado): activo solo puede
  agregar 15 s por validacion y una observacion fija. Se deja configurable por
  si la DIAN reabre la consulta directa; la heuristica de lectura sigue ahi.
- El boton *Consultar DIAN* ahora refresca el hallazgo en el resumen sin
  cambiar el estado de la solicitud.

Esto cierra la verificacion "caso positivo del catalogo DIAN" que estaba
pendiente desde la Fase 4: no es alcanzable con el catalogo actual.

## 32. La verificacion de emisor y receptor es un ajuste

A pedido del usuario (2026-09-11), *Verificar emisor y receptor* (NIT y razon
social) se puede desactivar en Ajustes. Con el lote de 25 facturas reales de
staging, todas sin XML, cada solicitud traia las observaciones `SUPPLIER_NIT`
y `CUSTOMER_NIT` "no se pudo verificar", que en captura manual no aportan.

- Activado por defecto: con XML, el NIT del emisor es la barrera contra
  radicar la factura de otro proveedor, y el del adquiriente contra facturas
  dirigidas a otra empresa. El texto de ayuda lo advierte.
- Desactivado, las dos reglas devuelven nada y los grupos *Emisor* y
  *Adquiriente* se ocultan en la pestana *Datos extraidos* (campo calculado
  `party_check_enabled`). Los datos se siguen extrayendo y guardando.
- Se guarda como `"True"/"False"` con el mismo mecanismo que la consulta
  DIAN (hallazgo 7 de la revision), centralizado en `_SPR_MANUAL_BOOLEANS`.

## Ajustes del comite (2026-09-23)

Lista de 12 puntos del comite de compras y contabilidad. Lo que cambio el
codigo esta en #33 a #38 (version 17.0.1.1.0, con migracion); lo que no, en
#39.

## 33. Notas credito y debito

El parser ya no rechaza `CreditNote` ni `DebitNote`: lee sus lineas
(`CreditNoteLine`/`CreditedQuantity`, `DebitNoteLine`/`DebitedQuantity`), los
totales (la nota debito los trae en `RequestedMonetaryTotal`, no en
`LegalMonetaryTotal`) y la factura que corrigen (`BillingReference`: numero y
CUFE). La solicitud tiene `document_type` y `origin_move_id`.

- **La factura de origen** se toma de lo que elija el proveedor o, si no
  elige, del CUFE y luego del numero de `BillingReference`, siempre entre las
  facturas de proveedor de ese mismo tercero. Se ofrecen todas las facturas
  no canceladas, no solo las radicadas por el portal: la nota puede ser de una
  factura anterior al portal.
- **Emparejamiento**: las lineas de la nota se emparejan contra las lineas de
  las ordenes de la factura de origen, con el mismo matcher (codigo, flete,
  IA, manual). Solo sirve para saber producto, cuenta e impuesto: la linea de
  la nota **no** lleva `purchase_line_id`, porque una nota corrige valor y no
  cantidades recibidas; con el vinculo, una nota por descuento bajaria la
  cantidad facturada de la orden. Las devoluciones fisicas siguen el flujo de
  inventario de Odoo.
- **Reglas**: no corren las de la orden (`PO_STATE`, `AMOUNT_TOTAL`,
  `QTY_OVER_PO`, `PRICE_UNIT_MISMATCH`), porque la orden ya se facturo. Corren
  `NOTE_ORIGIN` (error si no hay factura, es de otro proveedor, esta cancelada
  o el CUFE referenciado es otro) y, en credito, `NOTE_AMOUNT` (error si supera
  el saldo: total de la factura menos notas credito registradas y radicadas).
- **Nota credito** -> `in_refund` con `reversed_entry_id`.
- **Nota debito** -> `in_invoice`, con `debit_origin_id` solo si
  `account_debit_note` esta instalado (Jorels lo usa); no se agrega como
  dependencia. **Siempre requiere aceptacion**: la regla
  `DEBIT_NOTE_ACCEPTANCE` es observacion hasta que el Responsable pulsa
  *Aceptar nota debito* (queda quien y cuando), y `action_create_bill` la
  exige. Es el "aceptar las notas debito" que pidio el comite: un incremento
  de precio nunca pasa solo. *Volver a borrador* borra la aceptacion.
- `DOCUMENT_TYPE` (error): el XML adjunto es de otro tipo del radicado. El
  portal lo ataja antes, en el formulario.
- Las notas de ajuste al **documento soporte** las emite la compania, no el
  proveedor: no aplican aqui.

## 34. Varias ordenes de compra en una solicitud

`purchase_id` (Many2one) pasa a `purchase_ids` (Many2many, tabla
`supplier_payment_request_purchase_rel`). Algunos proveedores agrupan varias
remisiones en una sola factura para facturar menos.

- En el portal las ordenes se marcan con casillas; todas deben estar en la
  lista de abiertas del proveedor y ser de la misma compania.
- `PO_STATE` revisa cada orden; `AMOUNT_TOTAL` compara contra la **suma** de
  lo pendiente; el matcher busca en las lineas de todas; `invoice_origin` lleva
  los nombres separados por coma. Plazo de pago y posicion fiscal se toman de
  la primera orden.
- **Migracion**: `post-migrate` copia la columna vieja `purchase_id` a la tabla
  de relacion (Odoo no la borra). `pre-migrate` borra la plantilla *recibida*
  para que se recree: usaba `object.purchase_id`, y en un archivo `noupdate`
  Odoo 17 salta los registros existentes aunque se cambie la marca. Probado
  instalando el zip de 17.0.1.0.0 con demo y actualizando.

## 35. Fletes y envios: cargo adicional

El envio sale en la factura pero no en la remision ni en la orden. Antes eso
dejaba una linea sin emparejar y el total por encima de lo pendiente
(rechazo por `AMOUNT_TOTAL`).

- Campo `is_extra_charge` en la linea. El matcher marca como cargo, **antes**
  de la IA, las lineas no emparejadas por codigo cuya descripcion tenga
  flete, envio, transporte, domicilio, despacho, acarreo, mensajeria o cargo
  adicional (palabra completa, sin tildes). No se le pasan a la IA porque las
  emparejaria con cualquier producto.
- Los cargos de **documento** (`cac:AllowanceCharge` hijo directo con
  `ChargeIndicator=true`) no estan en ninguna linea pero si en el total: el
  parser los agrega como linea "Cargo adicional: <motivo>", que el matcher
  reconoce.
- El validador puede marcar o desmarcar la casilla a mano; queda como
  `manual` y sobrevive a la revalidacion igual que un emparejamiento manual.
- `AMOUNT_TOTAL` compara el total **sin** cargos (con su IVA) contra lo
  pendiente. `EXTRA_CHARGES` es **observacion** con el valor: contabilidad
  confirma el flete antes de registrar. No hay tope automatico.
- En la factura, cada cargo va con el producto de flete de Ajustes
  (`spr.freight_product_id`), sin orden, con los impuestos del producto solo
  si la factura le cobro impuesto. Sin producto configurado, *Crear factura*
  lo pide.

## 36. Cuenta de cobro de no obligados a facturar (documento soporte)

Indicador `spr_support_document` en el proveedor y tipo `support_doc`. Solo
esos proveedores ven la opcion en el portal (y la tienen por defecto).

- Sin XML ni CUFE: el documento electronico lo emite la compania. El
  proveedor declara numero, fecha y total. Las lineas se crean **una vez**
  desde lo pendiente de las ordenes (`qty_to_invoice`, o lo ordenado menos lo
  facturado si la politica es por recepcion y no ha llegado nada), ya
  emparejadas (`match_method = order`); despues son de contabilidad, que las
  ajusta si la cuenta de cobro no cubre todo. El total declarado no se pisa:
  `AMOUNT_INCONSISTENT` lo compara con lo que suman las lineas.
- No corren las reglas de CUFE, NIT de emisor/adquiriente ni DIAN. El numero
  repetido para el mismo proveedor es **error** (`INVOICE_REF_DUPLICATE`),
  porque sin CUFE es lo unico que identifica el documento. `SUPPORT_DOC` es
  observacion si el proveedor no esta marcado como no obligado.
- La factura se crea **siempre** en el diario de documento soporte
  (`spr.support_journal_id`): con Jorels, es el diario con resolucion tipo 12
  el que convierte la `in_invoice` en documento soporte al confirmarla. No se
  depende de Jorels; sin el diario configurado, *Crear factura* lo pide.

## 37. Requisitos para habilitar un proveedor; contactos padre e hijo

Constraint en `res.partner` sobre `portal_invoice_enabled`:

1. Solo el contacto comercial (empresa, o persona natural sin padre). En un
   hijo el indicador no tendria efecto: el portal lee el del comercial. La
   vista esconde la casilla en los hijos (`parent_id and not is_company`);
   sigue visible para personas naturales sin padre (regresion del
   2026-09-16).
2. Con NIT.
3. ~~Sin otro tercero con el mismo NIT~~. **Quitado el 2026-09-30** a pedido
   del usuario: al desplegar a staging, 87 de los 705 proveedores con ordenes
   en 2026 tenian otro tercero con el mismo NIT (casi siempre un duplicado sin
   DV y sin ordenes), y la regla no dejaba habilitar a ninguno de ellos. No
   hace falta: quien radica es el usuario portal que se le crea al proveedor,
   y ese usuario solo ve las ordenes de su propio tercero. Fusionar los
   repetidos sigue siendo buena limpieza, pero ya no es requisito.

Contactos padre e hijo:

- La solicitud queda siempre a nombre del contacto comercial, aunque se elija
  un hijo (en `create`/`write`). El dominio del campo acepta personas
  naturales sin padre (antes exigia `is_company`, el mismo error del
  2026-09-16).
- `submitted_by_partner_id` guarda el contacto que radico. Los correos van a
  la empresa **y** a esa persona: el correo de la empresa suele ser generico
  y quien espera respuesta es quien subio la factura. Antes, sin correo en la
  empresa no salia nada.

## 38. Cierre de radicacion de fin de mes

El ultimo dia habil del mes, desde la hora de corte (12:00 por defecto), el
portal no muestra el formulario ni acepta el POST hasta el dia 1 del mes
siguiente, e indica desde cuando reabre. Todos los dias el formulario avisa la
hora de corte.

- Dia habil: lunes a viernes que no sea festivo en Colombia. Los festivos se
  **calculan** en `services/cutoff.py` (fijos, Ley Emiliani y los que
  dependen de la Pascua) en vez de leerlos de un calendario de recursos que
  alguien tendria que cargar cada ano; todas las instancias del grupo son
  colombianas (#9). Verificado contra el calendario oficial 2026 (18
  festivos) y contra junio de 2025, que termina en lunes festivo.
- Hora local de la compania (`partner_id.tz`, por defecto `America/Bogota`).
- Ajustes: activo por defecto (Boolean guardado a mano, como #30) y hora de
  corte. Solo cierra el portal: el backend sigue creando solicitudes.
- Los tests desactivan el cierre en `SprCase` para no fallar el ultimo dia
  habil por la tarde; se prueba aparte con fechas fijas.

## 39. Puntos del comite que no cambian codigo

- **2. "Factura el pago"**: quedo anotado sin detalle ("no me acuerdo"). Sin
  definicion no hay que implementar.
- **9. Compras de otras areas**: el modulo no restringe por area; cualquier
  orden de compra confirmada del proveedor sirve. Quien valida y a quien le
  llega la actividad es organizacional (grupo validador en Ajustes). Queda
  para el comite.
- **10. Proveedores que facturan solo despues de cobrar** (pago anticipado,
  no entregan inventario antes): pendiente de validar el caso de uso. Hoy el
  modulo no lo bloquea: las reglas comparan contra lo **ordenado**, no lo
  recibido, asi que una factura por mercancia no entregada pasa si la orden
  esta confirmada. Lo que no existe es una solicitud de pago **sin**
  factura (anticipo contra cotizacion o cuenta de cobro previa); si el comite
  lo confirma, seria un tipo de documento nuevo.
- **11. Instructivo por correo**: no es regla sino plantilla
  (`mail_template_spr_instructions`, en `res.partner`) y un boton *Enviar
  instructivo del portal* en la ficha del proveedor habilitado. Abre el
  asistente de correo en vez de enviar directo, para revisar destinatarios y
  adjuntar la guia en PDF. El texto menciona la hora de corte configurada y,
  si aplica, la cuenta de cobro.

## 40. Una orden con factura ya no acepta otra factura: solo notas

Pedido del usuario el 2026-10-01. Antes se bloqueaba solo la orden
**totalmente** facturada (`invoice_status = invoiced`) y una orden con factura
parcial seguia aceptando facturas por lo pendiente. Ahora basta con que la
orden tenga una factura de proveedor no anulada (borrador incluido,
`purchase.order._spr_vendor_bills`):

- El portal no la ofrece para factura ni cuenta de cobro, y un id enviado a
  mano no pasa del filtro de ordenes vigentes.
- La regla `PO_STATE` rechaza la solicitud creada desde el backend. La factura
  que creo la misma solicitud no cuenta, para que revalidarla no la rechace.
- Las notas credito y debito no cambian: se radican sobre la factura que
  corrigen y no pasan por el estado de la orden.
- Anular la factura libera la orden.

En staging, al 2026-10-01, son 8 ordenes de 2026 con factura parcial.

## 41. La factura que corrige una nota se busca entre todas las del proveedor

Encontrado al validar staging el 2026-10-01: la proveedora de prueba tiene
1.618 facturas y el formulario de notas solo trae las 100 mas recientes
(`limit=100`, para que la lista sea usable). Esa misma lista se usaba para
validar, asi que una nota sobre una factura mas vieja salia con "no
encontramos registrada" aunque existiera. Ahora la lista sigue en 100, pero
`_spr_validate_origin` busca por id, CUFE o numero con el dominio completo del
proveedor (`_spr_origin_domain`).

## 42. Diario por tipo de proveedor; las casillas del contacto en su grupo

- **Diario.** Factura y notas van al *Diario de compras por defecto*; la
  cuenta de cobro (proveedor no obligado) al *Diario de documento soporte*.
  Es el mismo patron de staging en 2026: 276 proveedores solo en FACTU, 175
  solo en DSO. Si el diario por defecto queda vacio, el modulo toma el primer
  diario de compras por secuencia, que en staging es *Facturas de Activos*:
  hay que configurarlo siempre (en staging, FACTU id 3).
- **Vista del contacto.** Las casillas iban "despues del NIT". Con `base_vat`
  el NIT vive dentro de `div[@name='vat_vies_container']`, y ahi los campos
  salian sin etiqueta. Ahora van en un grupo propio *Portal de facturas*
  debajo del bloque principal del contacto.

## 43. IVA como producto (mayor valor IVA) y cargos que entran a la orden

Pedido del usuario el 2026-10-01. En Libertario el IVA no va como impuesto de
la linea: las lineas de la orden y de la factura van con *IVA Compra Exento*
0 % y el IVA se registra con el producto *[MAYVALIVACOM191] Mayor Valor Iva
Compras 19-15-8-5*. En staging, desde junio, 2.882 lineas de orden van sin
impuesto y 470 lineas de 2026 usan ese producto.

Ajuste *IVA como producto* (`spr.tax_as_product`, apagado por defecto) con
dos campos: producto de mayor valor IVA (`spr.tax_product_id`) e impuesto de
las lineas (`spr.exempt_tax_id`). Activo:

- **Factura:** todas las lineas llevan el impuesto 0 %, y el IVA total del
  documento (`amount_tax` del XML) va como una linea del producto de mayor
  valor IVA. El total sigue cuadrando con el de la factura.
- **Orden:** las lineas involucradas pasan al 0 %, y si la orden no tiene una
  linea de mayor valor IVA sin facturar, se le agrega (mensaje en su chatter).
  Si la tiene, se reusa.
- **Reglas:** `TAX_RATE_MISMATCH` no corre (la orden al 0 % es la practica);
  `AMOUNT_TOTAL` compara sin IVA y sin las lineas de IVA y flete de la orden;
  `TAX_AS_PRODUCT` compara el IVA con la linea de la orden: OK si coincide,
  observacion si no coincide o si la orden no la tiene.
- **Notas:** llevan la linea de IVA, pero no tocan la orden (DECISIONS #33).
- Activo sin producto o sin impuesto, *Crear factura* lo pide.

**Fletes (con o sin el ajuste):** el cargo ya no queda suelto en la factura
(cambia #35). Se liga a una linea del producto de flete de la orden; si no la
hay, se agrega. El flete y el mayor valor IVA de la orden no se ofrecen al
emparejador: se ligan al crear la factura.

## 44. Documentos y datos de facturacion del proveedor en "Editar informacion"

Pedido del usuario el 2026-10-01. El proveedor usa el formulario estandar del
portal (`/my/account`) para cargar camara de comercio, RUT y certificacion de
cuenta bancaria, y sus datos de facturacion electronica de Jorels. Codigo en
archivos propios: `controllers/portal_account.py`,
`views/portal_account_templates.xml`, `models/res_partner_documents.py`,
`views/res_partner_documents_views.xml`.

- **Solo para proveedores habilitados** (`portal_invoice_enabled` en el
  comercial). A los demas usuarios portal el formulario no les cambia y un
  envio con estos campos se rechaza como *Unknown field*. Si compras quiere
  pedir documentos antes de habilitar, habria que ampliar la condicion en
  `_spr_account_partner`.
- **Se escribe en el contacto comercial**, con sudo, aunque el usuario sea un
  contacto hijo: los documentos y los datos DIAN son de la empresa (Jorels
  muestra su pestana solo en el comercial). El contacto nunca viene del
  formulario. El resto (nombre, NIT, direccion) sigue el camino de Odoo, con
  su bloqueo `can_edit_vat` intacto: un hijo sigue sin poder cambiar el NIT.
- **Jorels es condicional.** Campos `type_regime_id`, `type_liability_id`,
  `municipality_id` (Many2one) y `email_edi` (Char), leidos en
  `l10n_co_edi_jorels/models/res_partner.py` de staging (version
  17.0.24.05.010000). No se agrega a `depends`: si el campo no esta en
  `res.partner._fields`, no se muestra ni se acepta. El codigo soporta
  many2one, many2many y texto por si Jorels cambia el tipo de alguno. Las
  opciones se leen con sudo (el portal no tiene ACL en las listas de Jorels) y
  solo se aceptan ids que existan en el modelo del campo.
- **Mecanismo**: se extiende `_get_optional_fields` (asi
  `details_form_validate` no los tiene por desconocidos),
  `details_form_validate` (ids validos, correo, tipo y tamano de archivo) y
  `on_account_update`, que saca estos campos de `values` antes de que Odoo
  escriba el contacto del usuario. Los valores de la pagina se agregan al
  `qcontext` de la respuesta de `account()`.
- **Documentos**: `Binary` con `attachment=True` y su `_filename`, con
  `groups="base.group_user"`: el usuario portal no los lee por ORM, el portal
  solo le muestra el nombre del archivo. Se aceptan PDF, PNG y JPEG
  reconocidos por la firma del contenido, hasta 10 MB (`MAX_DOC_BYTES`). Un
  input sin archivo no borra el que habia. Con cualquier error no se guarda
  nada; el navegador no conserva los archivos elegidos al volver el formulario.
- **Chatter**: cada envio con cambios deja una nota en el comercial con el
  autor (el contacto que envio) y la lista de documentos (con nombre de
  archivo) y campos de facturacion cambiados.
- En el backend los documentos van en el grupo *Portal de facturas* de la ficha
  (`view_partner_form_spr`), heredando esa vista sin editarla.

Pruebas: sin Jorels, el camino generico (many2one, many2many, texto) se
prueba cambiando la lista por `title`, `category_id` y `ref`.
`test_jorels_fields_when_installed` solo corre si Jorels esta: se paso en una
base desechable con la copia local `addons/l10n_co_edi_jorels` (otra
revision que staging, con los mismos cuatro campos). Ahi `base_vat` exige DV valido con pais
Colombia, por eso los tests usan `900123456-8`. Falta verlo en pantalla con
datos reales de staging (municipios: un select de unas 1.100 opciones).

## 45. XML obligatorio para obligados a facturar; arrastrar y soltar archivos

Pedido del usuario el 2026-10-01.

- **XML.** Un proveedor obligado a facturar (sin la casilla *No obligado a
  facturar*) tiene que adjuntar el XML de la DIAN en facturas y notas: sin el
  no pasa del formulario, y el campo CUFE ya no se muestra porque sale del XML.
  Para los no obligados sigue opcional y basta el CUFE. Solo aplica al portal:
  lo que contabilidad captura en el backend no cambia.
- **Arrastrar y soltar.** Los campos de archivo del portal (PDF y XML al
  radicar; Camara de Comercio, RUT y certificacion bancaria en *Edit
  information*) van dentro de una zona `.o_spr_dropzone`. El input es
  transparente y cubre la zona, asi que el clic abre el dialogo y soltar el
  archivo funciona sin JS; `static/src/js/spr_dropzone.js` (eventos delegados)
  solo resalta la zona y muestra el nombre del archivo.

## 46. Una orden con una radicacion en curso no acepta otra factura

Encontrado en la prueba del usuario el 2026-10-01: la RPS4584 sobre P42693
quedo *Aprobada* y el portal seguia ofreciendo la orden, porque todavia no
tenia factura en Odoo (#40 solo miraba facturas). Se radico dos veces mas;
salieron rechazadas por CUFE repetido, pero no debia poder intentarse.

`purchase.order._spr_open_requests`: radicaciones de factura o cuenta de
cobro sobre la orden que no esten rechazadas ni canceladas. Con alguna, el
portal no ofrece la orden (ni el boton de la orden) y `PO_STATE` rechaza otra
solicitud sobre ella. Rechazada la radicacion, la orden vuelve a ofrecerse
para que el proveedor corrija. Las notas no cuentan.

## 47. Solo PDF livianos y sin contrasena; vista previa de los documentos

Pedido del usuario el 2026-10-01.

- **PDF.** `services/pdf_check.py`: todo PDF que se adjunta (el de la
  radicacion y los tres documentos del proveedor) debe ser PDF, de maximo
  **2 MB** y sin contrasena ni cifrado. 2 MB porque en staging los documentos
  reales pesan 180-520 KB y el p95 de los PDF de facturas es 95 KB. El cifrado
  se detecta con pypdf si esta (Odoo.sh lo trae) y si no, por el `/Encrypt`
  del trailer. Los documentos ya no aceptan imagenes (cambia #44): asi se
  pueden previsualizar igual en todos lados. Tambien hay constraint en
  `res.partner` para lo que se cargue desde el backend. El XML sigue en 10 MB.
- **Vista previa en el backend:** pestana *Documentos del proveedor* en la
  ficha del contacto con `widget="pdf_viewer"` para cada documento.
- **Vista previa en el portal:** en *Edit information*, "Ver" despliega el PDF
  en un iframe (lazy, no se descarga hasta abrirlo) y "Abrir" lo abre en otra
  pestana. Ruta `/my/account/document/<campo>`: solo los tres campos y solo
  del contacto comercial del usuario conectado; no lleva id, asi que no se
  puede pedir el de otro proveedor.

## 48. Pestana "Portal de proveedor"; los documentos son adjuntos del contacto

Pedido del usuario el 2026-10-01. Version 17.0.1.2.0.

- **Pestana.** *Puede radicar facturas en el portal* y *No obligado a facturar*
  salen del grupo junto al NIT (#42) y van, con los documentos, en una sola
  pestana **Portal de proveedor** de la ficha del contacto (solo comercial,
  solo Responsable).
- **Documentos.** Camara de comercio, RUT y certificacion bancaria dejan de
  ser campos binarios propios (#44): cada uno es un Many2one a `ir.attachment`
  (`spr_doc_*_id`) con dominio a los PDF adjuntos al mismo contacto. En el
  backend se adjunta el PDF en el chatter y se elige en el campo; desde el
  portal, el archivo se crea como adjunto del contacto comercial, se enlaza al
  campo y va en la nota del chatter. La vista previa es un related a
  `datas` del adjunto (`spr_doc_*_preview`, `pdf_viewer`). La constraint exige
  que sea adjunto del propio contacto y PDF liviano sin contrasena (#47).
  Reemplazar un documento deja el anterior en el chatter como historial.
- **Migracion** (`migrations/17.0.1.2.0/post-migrate.py`): reusa el adjunto
  del campo binario viejo, le quita `res_field` (asi aparece en el chatter), le
  pone el nombre de archivo guardado y lo enlaza. Probada simulando el estado
  de staging.

## 49. Una actividad por validador y "Tomar revision"

Pedido del usuario el 2026-10-02 (QA en Odoo 19).

- **Validadores.** En 19 `res.groups.user_ids` solo trae los miembros
  explicitos del grupo; los que llegan por herencia (Responsable, *Compras:
  administrador*) estan en `all_user_ids`. Con `user_ids` la actividad caia en
  el admin y nadie mas la veia. Ahora se usa `all_user_ids`, solo usuarios
  internos activos (`active and not share`), sin `base.user_root` ni
  `base.user_admin` salvo que sean los unicos (estan en el grupo por
  `security.xml`, no porque revisen facturas).
- **Solo la compania de la solicitud**: un validador sin acceso a ella no
  recibe la actividad (multicompania).
- **Una actividad por validador**, no solo al primero. Sin duplicar: quien ya
  tiene una actividad de revision abierta (tarea automatica) no recibe otra al
  revalidar. Si la solicitud ya tiene revisor, solo el.
- **Sin seguidores de paso.** En 19 `mail.activity.create` suscribe al
  asignado y no hay contexto que lo evite (`mail_activity_quick_update` solo
  evita la notificacion): cada validador quedaba siguiendo la solicitud y
  recibia copia de los correos al proveedor. Al crear las actividades se
  deshacen solo las suscripciones que trajeron; los seguidores previos quedan.
- **Tomar revision.** Campo `reviewer_id` (*Revisor asignado*, con tracking) y
  boton *Tomar revision* para el grupo validador en Borrador, Validando,
  Aprobada y Con observaciones. Asigna al usuario, **borra** las actividades de
  revision de los demas (sin un "Actividad hecha" por cada una) y los
  desuscribe, deja (o crea) la suya, suscribe al revisor (es quien atiende al
  proveedor) y deja una sola nota interna "Revision tomada por X". Se puede
  tomar una que ya tenia otro: no se bloquea; el cambio queda en el chatter por
  el tracking. El formulario avisa "En revision por X" a los demas, la lista
  muestra el revisor y la busqueda trae *Mis revisiones* y *Agrupar por
  revisor*.
- **Toma automatica.** Crear la factura, rechazar (tambien por el asistente),
  cancelar, aceptar la nota debito, cambiar a mano la linea de la orden o el
  cargo adicional de una linea, y revalidar asignan al usuario actual si nadie
  la tenia. No corre en el portal, con el superusuario ni en el emparejamiento
  automatico (contexto `spr_pipeline`).
- **Cierre.** Crear la factura, rechazar, cancelar o una revalidacion que
  termina rechazada cierran la revision: la actividad del revisor (o de quien
  actua) queda hecha y las demas se borran y sus usuarios se desuscriben.
  Volver a borrador no las toca.

## 50. Sin camara de comercio, RUT y certificacion bancaria no se radica

Decision de negocio del 2026-10-02. Si el contacto comercial no tiene los
tres documentos (`spr_doc_chamber_id`, `spr_doc_rut_id`,
`spr_doc_bank_cert_id`), `/my/payment-requests/new` no muestra el formulario
ni procesa el POST (no se confia solo en la interfaz): muestra la lista de lo
que falta y un boton a `/my/account`. El mismo aviso sale en la lista de
solicitudes y en `/my`. El boton *Radicar factura de esta orden* de la orden de
compra del portal lleva a la misma ruta, asi que tambien cae en el aviso. La
creacion desde el backend no se bloquea. En *Mi cuenta* cada documento lleva la
insignia *Requerido para radicar*; el input no es `required`: guardar el resto
de los datos no depende de los documentos y uno ya cargado no se vuelve a
pedir.

*Mi cuenta* mantiene obligatorios telefono, calle, ciudad, pais y codigo postal
(los exige Odoo 19; Colombia tiene `zip_required`). Para que el error se vea, la
zona de un documento con error se pinta en rojo (CSS `:has(input.is-invalid)`)
y, tras un envio con errores, la pagina baja hasta los mensajes de `#errors`
(parche de `saveAddress` del `CustomerAddress` de `portal`, solo en el
formulario del proveedor).

## 51. El JSON tecnico de la validacion es solo para usuarios internos

El ACL de portal deja leer `supplier.payment.request` (lo necesitan la lista y
el detalle del portal), asi que por RPC un proveedor podia leer
`validation_json`, `extracted_json` y `validation_summary`: codigos internos,
hallazgos "ok", montos calculados y datos extraidos. Los tres llevan
`groups="base.group_user"`. El portal y los correos no los leen directo: el
detalle del portal y las plantillas usan `_portal_findings()`, que lee con sudo
y solo devuelve errores y observaciones con su mensaje en espanol.

## 52. Ajustes de Odoo 19 sin cambio funcional

- **Analitica en notas.** En 19 `purchase.order.line._prepare_account_move_line`
  ya no devuelve `analytic_distribution`: la linea de factura la calcula desde
  `purchase_line_id`. Las notas quitan ese vinculo (#33), asi que se quedaban
  sin analitica; ahora la copian de la linea de la orden, como en 17 (solo si
  la tiene).
- **Precision de la cantidad.** La precision decimal se llama `Product Unit` en
  19 (antes `Product Unit of Measure`); con el nombre viejo `precision_get`
  caia en 2 decimales sin error.
- **Factura borrador sin numero.** En 19 `name` es False (ya no "/") hasta
  confirmar: los mensajes usan `validation_rules.move_label`, que sin numero
  toma la referencia del proveedor (su numero de factura) y si tampoco la hay
  el `display_name`. La nota del chatter dice "Factura de proveedor en
  borrador FEQA1001 creada desde la solicitud ..." (o "Nota credito de
  proveedor").
- **Ordenes "done".** El estado no existe en 19 (una orden bloqueada sigue en
  `purchase` con `locked`); se quito de dominios y de `PO_OPEN_STATES`.
- **Migracion 19.0.1.2.0.** El `write` de `ir.ui.view` de 19 no recalcula
  `type` (#15 ya no aplica: las listas son `<list>`): el pre-migrate pasa a
  `list` las vistas del modulo que sigan en `tree` y renombra el xmlid de la
  lista solo si el nuevo no existe; el post-migrate reactiva con el ORM (cada una en
  su savepoint; si no valida, queda inactiva y se avisa en el log) las vistas
  del modulo que el upgrade haya desactivado, salvo `portal_my_home_spr`
  (`customize_show`, puede estar apagada a proposito).

## 53. Datos de facturacion electronica obligatorios en "Mi cuenta"

Con Jorels instalado, el proveedor habilitado debe tener tipo de regimen, tipo
de responsabilidad, municipio y email de facturacion para guardar "Mi cuenta",
igual que los tres documentos son requisito para radicar (#50): contabilidad
necesita esos datos para el documento soporte y la factura electronica. Un
campo que no llega en el POST cuenta como vacio. Sin Jorels los campos no
existen y no se piden. A los usuarios portal que no son proveedores
habilitados el formulario no les cambia.

## 54. Los correos al proveedor tambien le llegan a quien radico

Regresion 17 -> 19. En 19 `_message_compute_real_author` toma como autor al
usuario activo y `_notify_get_recipients` lo excluye de los destinatarios.
Como el mensaje lo publica la accion del proveedor (radicar desde el portal),
quien radico quedaba fuera de "recibimos su factura" y "requiere correccion":
el contacto de una empresa solo lo recibia por el correo de la empresa y una
persona natural (proveedor y quien radica son el mismo contacto) no recibia
nada. `_notify_supplier` publica con el contexto `mail_notify_author_mention`
(documentado en `mail/models/mail_thread.py` de 19): el autor se notifica si
esta entre los destinatarios directos (`partner_ids`), que son la empresa y
quien radico, una vez cada uno. No cambia a quien se le escribe.

## 55. CUFE del proveedor en la factura de proveedor

En la factura y la nota credito de proveedor (`in_invoice`, `in_refund`) se
muestra el CUFE/CUDE del documento del proveedor, solo si tiene valor, de
lectura, con boton de copiar (`CopyClipboardChar`) y el enlace **Consultar en
la DIAN** (`spr_cufe_dian_url`, la misma URL `.../document/searchqr?documentkey=`
que la consulta automatica, tomada de `spr.dian_catalog_url`). Va al final del
grupo izquierdo del encabezado (`group[@id='header_left_group']`) y no junto a
la referencia: Jorels inserta sus campos despues del primer `field[@name='ref']`.
No toca `ei_uuid` de Jorels, que es el CUFE de las facturas que emite la
compania (#2). Las facturas se pueden buscar por CUFE.

## 56. Montos de los hallazgos en formato colombiano

Los hallazgos estan en espanol pero los montos salian `1,547,000.00`.
`_money` usa `tools.format_amount` con el idioma espanol activo (es_CO o
es_419) y la moneda de la solicitud: `$ 1.547.000,00`. Sin un idioma espanol
activo, el mismo formato a mano. Es independiente del idioma de quien valida.

## 57. Notas: solo facturas publicadas en el selector; borrador es observacion

El selector de "factura que corrige" del portal ofrecia facturas en borrador,
que todavia pueden cambiar o borrarse. Ahora solo lista facturas publicadas
del proveedor (sigue el limite de 100). Si el XML de la nota referencia una
factura que en Odoo todavia esta en borrador, la busqueda por el XML la
encuentra igual y la regla `NOTE_ORIGIN` da **observacion** ("aun no esta
contabilizada"), no rechazo: no es culpa del proveedor. Con solo borradores,
el formulario de notas avisa que no hay facturas a las que aplicarla.

## 58. Asteriscos de obligatorio en "Mi cuenta"

Los cuatro datos de facturacion electronica de Jorels (#53) se ven con el
asterisco de obligatorio, como los campos obligatorios del formulario de
direccion de Odoo 19 (label sin `label-optional`; el asterisco lo pone
`portal.scss`). En el navegador no se veia: `address.js`, al cargar y al
cambiar el pais, le quita `required` y pone `label-optional` a todo lo que no
esta en sus `required_fields`. Los inputs llevan `data-spr-required` y el
parche de `_onChangeCountry` en `spr_dropzone.js` se lo devuelve. No se
agregan a `required_fields`: el core los validaria contra los valores de la
direccion, donde no estan. Los tres documentos llevan el asterisco solo si
faltan (uno cargado no se vuelve a pedir) y sin `required` en el input: guardar
el resto no depende de ellos, radicar si (#50). Se quito la insignia
"Requerido para radicar", redundante con el asterisco y el texto de la
seccion.

## 59. El instructivo pide cargar documentos y datos antes de radicar

El instructivo para el proveedor (`mail_template_spr_instructions`) agrega el
paso 2: cargar en *Mi cuenta* la camara de comercio, el RUT, la certificacion
bancaria, los datos de facturacion electronica y la direccion (#50 y #53). La
plantilla es `noupdate`, asi que en las bases de 17 la actualiza el
post-migrate de 19.0.1.2.0, y solo si sigue con el texto original de 17
(se compara la huella del texto visible, no el HTML): una plantilla
personalizada en produccion no se pisa. Las demas plantillas no cambian.

## 60. Destinatarios de las plantillas de correo (`use_default_to`)

En 19 `mail.template.use_default_to` viene en True por defecto (en 17 en
False): con True el composer y el render ignoran `partner_to` y proponen los
destinatarios "sugeridos" del registro, que pueden incluir al autor del ultimo
mensaje (en local el instructivo proponia tambien a Administrator). Las cinco
plantillas del modulo lo dejan explicito en False para usar su `partner_to`,
como en 17. En produccion no cambia nada: las plantillas existen desde 17 con
False y son noupdate. Ademas, cantidades y porcentajes de los hallazgos salen
en formato colombiano como los montos (#56).

## 61. El instructivo se abre con la guia en PDF adjunta

El boton "Enviar instructivo del portal" de la ficha del contacto abria el
asistente de correo con la plantilla cargada pero sin adjuntos: compras tenia
que buscar el PDF y adjuntarlo a mano en cada envio. El comentario de la
plantilla ya lo preveia ("adjuntar la guia en PDF si se tiene") pero nada lo
hacia.

Ahora `action_spr_send_instructions` pasa `default_attachment_ids` con la guia
leida de `static/doc/guia/Instructivo_portal_proveedores_Libertario.pdf`, con
`file_open` de Odoo, que resuelve la ruta contra los `addons_path`. Si el
archivo no esta en disco (un copiado del addon sin `static/doc`), el asistente
se abre igual sin adjunto y se avisa en el log; el texto del instructivo se
sostiene por si solo.

El PDF no viaja en un XML de datos: no se duplica en la base, no ensucia un
`noupdate` y se actualiza reemplazando el archivo en disco.

La primera version pasaba el adjunto como comando `(0, 0, {...})` con el
contenido en base64 dentro del default de contexto. Al abrir y guardar el
asistente desde el formulario en 19, el `create` llegaba con ese dict sin el
`name` y el INSERT en `ir_attachment` revienta con un NotNullViolation (el
dialogo "Falta el valor requerido para el campo 'Nombre'"): los comandos con
`datas` dentro de un default no sobreviven al recorrido cliente-servidor.
Ademas, el core nunca hace eso: `_compute_attachment_ids` crea el adjunto con
`ir.attachment.create` y entrega ids.

Por eso `_spr_instructions_attachment` materializa el PDF en el servidor con
`ir.attachment.create` (patron del core) y el contexto solo lleva `(4, id)`,
un entero que el cliente maneja sin riesgo. La attachment se crea en el mismo
"estacionamiento" que usa el core (`mail.compose.message` con `res_id` 0):
no aparece en ningun chatter, no queda ligada al proveedor si compras cancela
y se reutiliza en cada clic (una sola fila, `ir.attachment` por nombre); si el
PDF cambia en disco se detecta por checksum y se actualiza. Al enviar,
`_prepare_mail_values` copia la attachment al mensaje, como con cualquier
adjunto del asistente.

La plantilla no cambia (es solo texto) y el modulo sigue en 19.0.1.2.0.
