# POS – Información adicional en el ticket

Módulo Odoo 19 que permite configurar, **por punto de venta**, N bloques de información
adicional que se imprimen en el ticket del POS: texto, códigos QR (URL, WiFi, reseña de
Google, WhatsApp, vCard, pago) y códigos de barras.

Los bloques son **repetibles**, **ordenables** (arrastrando), **activables/desactivables**
y con **vigencia por fechas** e **importe mínimo**.

- **Sin librerías JS de terceros.** Los QR y códigos de barras se generan con el endpoint
  nativo `/report/barcode` (ReportLab), el mismo que usa Odoo en los informes PDF.
- **Configuración independiente por `pos.config`.** Cada tienda carga solo sus bloques.

---

## Instalación

El módulo no tiene dependencias externas. Solo depende de `point_of_sale`.

```bash
# Odoo.sh: basta con hacer push del módulo a la rama.
# Local:
odoo -u pos_ticket_customization -d <base_de_datos>
```

Tras instalar, **cierra y reabre la sesión del POS** (o recarga la pestaña) para que el
frontend cargue los nuevos assets y los datos de los bloques.

---

## Dónde se configura

Hay tres accesos, todos sobre el mismo modelo `pos.receipt.custom.block`:

| Ruta | Uso |
|---|---|
| **Punto de Venta → Configuración → Punto de Venta →** abre una tienda | Lista editable en línea, con arrastre para reordenar. Es el sitio principal. |
| **Punto de Venta → Configuración → Ajustes →** bloque *Bills & Receipts* → *Configurar bloques* | Atajo desde los ajustes de la tienda seleccionada. |
| **Punto de Venta → Configuración → Ticket – Información adicional** | Vista global de todas las tiendas, para auditar o agrupar por punto de venta. |

Todo requiere el grupo **Administrador del POS** (`point_of_sale.group_pos_manager`).
Los vendedores (`group_pos_user`) solo tienen lectura, que es lo que necesita el loader
del POS para cargar los bloques al abrir la sesión.

---

## Campos de un bloque

| Campo | Descripción |
|---|---|
| **Punto de venta** | Tienda dueña del bloque. Al eliminar la tienda se eliminan sus bloques (`ondelete='cascade'`). |
| **Secuencia** | Orden de impresión. Se ajusta arrastrando la fila. |
| **Activo** | Desactiva el bloque sin borrarlo. Los inactivos no se cargan en el POS. |
| **Tipo** | Ver la tabla de tipos más abajo. |
| **Posición** | `Cabecera`, `Antes del pie` o `Final del ticket`. |
| **Alineación** | Izquierda, centro o derecha. |
| **Leyenda** | Texto opcional sobre el bloque (traducible). |
| **Contenido** | Texto, URL o valor del código, según el tipo. Admite marcadores dinámicos. |
| **Simbología** | Solo para códigos de barras. |
| **Ancho / Alto (px)** | Tamaño de la imagen del código. |
| **Mostrar valor** | Imprime el valor legible bajo las barras (no aplica a QR). |
| **Imagen** | Para el tipo *Imagen*. |
| **Vigente desde / hasta** | Vigencia opcional. Vacío = sin límite. |
| **Importe mínimo** | Imprime solo si el total con impuestos del pedido ≥ este valor. `0` = sin mínimo. |
| **Cada N pedidos** | `1` = en todos. `10` = en uno de cada diez. Ver abajo. |
| **Desplazamiento** | En qué pedido del ciclo cae. Solo visible si *Cada N pedidos* > 1. |

---

## Tipos de bloque

| Tipo | Qué imprime | Qué rellenar |
|---|---|---|
| `Texto libre` | Texto tal cual, respetando saltos de línea | *Contenido* |
| `Texto legal` | Igual, con tipografía más pequeña (leyendas DIAN/CFDI, aviso de datos) | *Contenido* |
| `Separador` | Línea divisoria punteada | — |
| `Imagen` | Imagen/logo adicional en base64 | *Imagen* |
| `QR de URL` | QR que abre una URL | *Contenido* = la URL |
| `QR de texto` | QR con texto arbitrario (datos de facturación, resolución DIAN…) | *Contenido* |
| `Código de barras` | Código lineal legible por lector | *Contenido* + *Simbología* |
| `QR de reseña en Google` | QR al formulario de reseña | *Contenido* = Place ID **o** URL completa |
| `QR de WhatsApp` | QR a `wa.me` con mensaje prellenado | *Número*, *Mensaje* |
| `QR de WiFi` | QR que conecta al WiFi de la tienda | *SSID*, *Seguridad*, *Contraseña* |
| `QR de contacto (vCard)` | QR que guarda el contacto de la tienda | Campos *vCard* |
| `QR de pago / propina` | QR a un link de pago (Nequi, Bancolombia, PSE, propina) | *Contenido* = la URL |

---

## Marcadores dinámicos

Disponibles en *Contenido*, *Leyenda* y *Mensaje de WhatsApp*. Se resuelven en el
momento de imprimir, antes de generar el QR o el código de barras:

| Marcador | Valor |
|---|---|
| `{order_name}` | Nombre/referencia del pedido |
| `{total}` | Total con impuestos, ya formateado con la moneda |
| `{date}` | Fecha y hora del pedido |
| `{cashier}` | Cajero |
| `{table}` | Mesa (vacío si `pos_restaurant` no está instalado) |
| `{partner_name}` | Cliente |
| `{tracking_number}` | Número de seguimiento del pedido |
| `{store_name}` | Nombre del punto de venta |

Un marcador **desconocido se deja intacto** (`{foo}` se imprime literal). Es
deliberado: así el error de configuración se ve en la pantalla de recibo antes de
imprimir, en lugar de dejar un hueco silencioso en el ticket del cliente.

---

## Frecuencia: imprimir cada N pedidos

Para un QR de reseña o una promoción no suele interesar imprimirlo en todos los tickets.
Con **Cada N pedidos = 10**, el bloque sale en los pedidos **10, 20, 30…** del turno.

El conteo usa `sequence_number`, el número de pedido **dentro de la sesión de caja**.
Esto tiene tres consecuencias que conviene tener claras:

- **Se reinicia al abrir caja.** Cada turno vuelve a empezar en 1. Con volúmenes de
  cafetería (cientos de pedidos por turno) esto es irrelevante, pero si un punto de venta
  hace menos de N pedidos por turno, el bloque **no saldría nunca**. Ajusta N a lo que
  realmente vende la tienda en un turno.
- **Es estable al reimprimir.** El número se asigna una sola vez y se guarda con el
  pedido, así que una reimpresión muestra exactamente los mismos bloques que el ticket
  original. No hay sorpresas para el cliente ni para el cajero.
- **Funciona sin conexión.** No hace falta consultar al servidor para saber si toca.

### Desplazamiento

Si configuras varios bloques con la misma frecuencia, sin desplazamiento **caerían todos
en el mismo ticket** (el 10, el 20…), dejando el resto sin nada. El desplazamiento
reparte el ciclo:

| Bloque | Cada N | Desplazamiento | Sale en los pedidos |
|---|---|---|---|
| QR de reseña | 10 | 0 | 10, 20, 30… |
| Promo del mes | 10 | 5 | 5, 15, 25… |
| QR de WiFi | 1 | 0 | todos |

Debe cumplirse `0 ≤ desplazamiento < N`; se valida al guardar.

---

## Ejemplos de configuración

### Reseña en Google

| Campo | Valor |
|---|---|
| Tipo | `QR de reseña en Google` |
| Posición | `Final del ticket` |
| Leyenda | `¿Cómo estuvo tu café? Déjanos tu reseña ⭐` |
| Contenido | `ChIJN1t_tDeuEmsRUsoyG83frY4` (Place ID) o la URL corta de la ficha |
| Ancho / Alto | `150` / `150` |

Si el contenido empieza por `http`, se usa tal cual; si no, se construye
`https://search.google.com/local/writereview?placeid=<contenido>`.

### WiFi de la tienda

| Campo | Valor |
|---|---|
| Tipo | `QR de WiFi` |
| Posición | `Antes del pie` |
| Leyenda | `WiFi gratis: escanea para conectarte` |
| SSID | `Libertario_Invitados` |
| Seguridad | `WPA/WPA2` |
| Contraseña | `cafe2026` |

Genera el payload estándar `WIFI:T:WPA;S:Libertario_Invitados;P:cafe2026;;`.
Los caracteres reservados (`\ ; , : "`) se escapan automáticamente, así que una
contraseña con `;` funciona sin tocar nada.

### Link de pago / propina

| Campo | Valor |
|---|---|
| Tipo | `QR de pago / propina` |
| Posición | `Final del ticket` |
| Leyenda | `¿Te atendimos bien? Deja propina aquí` |
| Contenido | `https://pagos.libertariocoffee.com/propina?ref={order_name}` |

### WhatsApp con el número de pedido

| Campo | Valor |
|---|---|
| Tipo | `QR de WhatsApp` |
| Número | `573001234567` |
| Mensaje | `Hola, escribo por mi pedido {order_name} de {store_name}` |

El mensaje se codifica **después** de resolver los marcadores, así que acentos y
espacios en el nombre de la tienda no rompen el enlace.

### Leyenda legal DIAN solo en compras grandes

| Campo | Valor |
|---|---|
| Tipo | `Texto legal` |
| Contenido | `Resolución DIAN 18764000000000 de 2025. Régimen común.` |
| Importe mínimo | `200000` |
| Vigente hasta | `31/12/2026` |

---

## Notas de impresión térmica

- **El ticket se rasteriza a 512 px de ancho** (`.pos-receipt-print`) antes de mandarlo a
  la impresora. Mantén los QR entre **120 y 200 px** para que sean legibles tanto en
  58 mm como en 80 mm. Un QR de 300 px no mejora nada y consume papel.
- **Los códigos de barras lineales** quedan mejor apaisados: ~`300 × 60` px. El módulo
  ajusta ese tamaño por defecto al elegir el tipo *Código de barras*.
- **Los códigos van incrustados en el ticket, no enlazados.** Al abrir la sesión el
  módulo descarga de `/report/barcode` todos los códigos cuyo valor no depende del
  pedido y los guarda como `data:` URI. A partir de ahí el ticket se imprime sin
  hablar con el servidor. Esto no es una optimización, es obligatorio: ver
  *Por qué se incrustan las imágenes* más abajo.
- **Bloques con marcadores dinámicos:** su valor solo se conoce al imprimir, así que
  su código se descarga en ese momento (`PrinterService.print()` lo espera antes de
  rasterizar). Si en ese instante no hay conexión, el bloque **imprime la misma
  información en texto**: el SSID y la clave del WiFi, la URL de la reseña, el
  teléfono de la vCard… Nunca queda un hueco en blanco.
- **Nada bloquea la impresión.** Como las imágenes son `data:` URI, el
  `loadAllImages()` del core resuelve al instante; una imagen que no se pudo generar
  se descarta antes de llegar a la plantilla, en vez de dejar la impresión esperando
  a una petición que no va a responder.
- **Epson ePOS / ESC-POS:** compatible. Solo se añaden `<div>`, `<img>` y texto, que es
  lo que `htmlToCanvas` sabe rasterizar. Las imágenes son del mismo origen que Odoo, así
  que no contaminan el canvas.
- **58 mm:** las imágenes llevan `max-width: 100%` y `height: auto`, de modo que un
  código configurado demasiado ancho se reescala en lugar de recortarse.
- **Tope de 1000 px por lado.** `ir.actions.report.barcode()` rechaza
  `ancho × alto > 1 200 000` px², y el endpoint traduce ese error a una respuesta
  HTTP 200 con cuerpo HTML: el `<img>` saldría roto sin ningún error en el log. El
  modelo valida el tamaño al guardar para que eso no llegue nunca al ticket.

### Por qué se incrustan las imágenes

Al mandar el ticket a la impresora térmica, el core lo rasteriza con
`htmlToCanvas`, que cachea cada recurso descargado por URL **borrando todo lo que va
detrás de `?`** (`getCacheKey`, en
`point_of_sale/static/src/app/utils/html-to-image.js`; solo conserva la query string
si le pasan `includeQueryParams`, cosa que el POS nunca hace).

Todos los códigos de este módulo son `/report/barcode/?...`, así que **comparten
clave de caché**: sin incrustarlos, el primer código que se rasterice se imprimiría
en todos los demás bloques y en todos los tickets del turno — el QR del WiFi donde
debería ir el de la reseña, y así. La caché es un objeto de módulo que no se limpia
nunca, y el fallo no se ve en pantalla (allí son `<img>` normales), solo en papel y
en el recibo enviado por correo.

Un `data:` URI hace que `embedImageNode()` salga por su `return` inicial y no toque
esa caché. De paso resuelve que `/report/barcode` no mande `Cache-Control`, `ETag`
ni `Last-Modified`, así que el navegador revalidaría contra el servidor en cada
impresión.

---

## Decisiones técnicas

1. **Modelo hijo `pos.receipt.custom.block` en vez de campos escalares en `pos.config`.**
   Es lo que permite N bloques ordenables, con validación por tipo y vigencia propia.

2. **Carga al frontend por el loader estándar del POS.** En Odoo 19 se usa el contrato
   `pos.load.mixin`: el modelo hereda `pos.load.mixin` y define `_load_pos_data_domain()`
   y `_load_pos_data_fields()`, y `pos.session` añade el modelo en
   `_load_pos_data_models()`. El `domain` filtra por `config_id` de la sesión: cada tienda
   carga solo lo suyo. Nótese que un `One2many` en `pos.config` **no** habría bastado:
   `_load_pos_data_search_read` de `pos.config` devuelve solo los IDs.

3. **Query string en lugar de ruta en `/report/barcode`.** El core expone el helper
   `qrCodeSrc()`, que usa la forma de ruta `/report/barcode/QR/<valor>`. Aquí se usa
   `/report/barcode/?barcode_type=..&value=..` porque Werkzeug des-escapa el segmento
   `<path:value>` antes de enrutar, y un valor con `/` o saltos de línea —justo lo que
   contienen los payloads de vCard, WiFi y las URLs con path— puede romper el enrutado.
   La query string codifica cualquier byte sin ambigüedad. Ambas rutas están declaradas
   en el mismo controlador nativo (`web/controllers/report.py`), así que no se pierde
   nada nativo.

4. **Nombres de simbología de ReportLab, no los "comerciales".** El selector usa
   `Standard39` e `I2of5`, no `Code39` ni `ITF`: estos últimos no son nombres válidos de
   widget de ReportLab. Con ellos, `createBarcodeDrawing()` lanza `KeyError`, que
   `ir.actions.report.barcode()` **no captura** (su `except` solo atrapa `ValueError` y
   `AttributeError`), así que el endpoint devuelve **HTTP 500 y el ticket se imprime con
   la imagen rota**. Verificado ejecutando `barcode('Code39', 'ABC123')` en esta
   instancia: `KeyError('Code39')`. Las etiquetas de la interfaz sí muestran los nombres
   comerciales.

5. **Validación de EAN-8 / EAN-13 al configurar.** Aquí el fallo es el contrario y más
   sutil: con una longitud o dígito de control incorrectos, `barcode()` **sí** convierte
   el tipo a Code128 (`ir_actions_report.py`, rama `check_barcode_encoding`) e imprime un
   código de simbología distinta a la configurada, sin ningún error. Se valida al
   configurar con `odoo.tools.barcode.check_barcode_encoding`, y se omite si el valor
   lleva marcadores dinámicos, porque su valor real solo se conoce al imprimir.

6. **Clases de alineación propias.** El core solo define `pos-receipt-center-align` y
   `pos-receipt-right-align`, y esta última es `float: right` —pensada para importes en
   línea, no para bloques—. `pos-receipt-left-align` directamente no existe. Se definen
   `o_ptc_align_left/center/right` en el SCSS del módulo.

7. **Campos dedicados para WiFi, WhatsApp y vCard** en lugar de sobrecargar `content`
   con un mini-formato. Hace la configuración auto-explicativa y evita errores de
   sintaxis del usuario en el payload del QR.

8. **Los payloads se construyen en el frontend**, no en un campo calculado del servidor.
   Así la resolución de marcadores y la codificación URL ocurren en el orden correcto
   (primero resolver, luego codificar) y en un único sitio.

9. **`config_id` fuera de la lista editable.** En un `One2many` embebido, incluir el
   campo inverso —que es `required`— hace que el cliente lo valide como vacío y bloquee
   el guardado. La vista global usa una lista aparte, no editable, donde sí se muestra.

10. **Regla multi-compañía** (`security/pos_receipt_custom_block_rules.xml`) sobre el
    `company_id` heredado del punto de venta: con 14 tiendas y varias compañías
    (Colombia/México), ninguna debe ver ni cargar la configuración de otra.

11. **No se toca la restricción de Odoo sobre `receipt_header` / `receipt_footer`**
    (`pos.config.write`, solo admin). Los campos de este módulo son independientes y los
    gobierna `group_pos_manager`.

---

## Estructura

```
__manifest__.py
models/
  pos_receipt_custom_block.py     # modelo, validaciones, contrato de campos con el POS
  pos_config.py                   # One2many + acción para abrir los bloques
  pos_session.py                  # loader del modelo hijo hacia el frontend
  res_config_settings.py          # contador + botón en Ajustes
views/
  pos_receipt_custom_block_views.xml
  pos_config_view.xml
  res_config_settings_views.xml
security/
  ir.model.access.csv
  pos_receipt_custom_block_rules.xml
static/src/
  utils/receipt_block_utils.js                              # URLs de código, payloads, marcadores
  app/services/pos_store.js                                 # PosStore.setup: carga y resolución de bloques
  app/services/printer_service.js                           # prerresolución de códigos en PrinterService.print
  app/screens/receipt_screen/receipt_screen.js              # patch de _sendReceiptToCustomer
  app/screens/receipt_screen/receipt/order_receipt.js       # OrderReceipt.setup + getter customReceiptBlocks
  app/screens/receipt_screen/receipt/order_receipt.xml      # herencia de la plantilla
  app/screens/receipt_screen/receipt/order_receipt.scss
```

Estilo de parcheo Odoo 19: los 4 JS se registran con `patch(PosStore/PrinterService/...)`
sobre las clases de `@point_of_sale/...`; se usa `usePos()` (que ya resuelve
`PosStore/order.printer env`) en el `setup()` de `OrderReceipt`, y las fechas de los
modelos relacionales llegan como luxon `DateTime` (se comparan con `DateTime.now().startOf("day")`).

---

## CHANGELOG

### 19.0.1.0.0

- Migración a Odoo 19. El frontend se reestructura a `static/src/app/...` y se parchea
  con las clases de `@point_of_sale/...` (`patch()` + `usePos()`, sin archivos
  `overrides/`).
- El loader del POS pasa del patrón `_pos_ui_models_to_load` / `_loader_params_*` /
  `PosStore._processData` al contrato `pos.load.mixin`
  (`_load_pos_data_domain`, `_load_pos_data_fields`, `_load_pos_data_models`).
- Las fechas de `pos.receipt.custom.block` se deserializan como luxon `DateTime` en el
  cliente; la vigencia se compara contra `DateTime.now().startOf("day")`.
- Vistas adaptadas a Odoo 19: `<group>` sin `string`/`expand` en la vista de lista, y
  `view_mode: 'list,form'` (no `'tree,form'`) en la acción de `pos.config`.

### 17.0.1.0.0

- Modelo `pos.receipt.custom.block` con 12 tipos de bloque, 3 posiciones, 3 alineaciones,
  vigencia por fechas, importe mínimo y frecuencia (“cada N pedidos”, con desplazamiento
  para repartir varios bloques entre tickets distintos).
- Carga por tienda al frontend del POS mediante el loader estándar.
- Generación de QR y códigos de barras con el endpoint nativo `/report/barcode`, sin
  librerías JS de terceros.
- Marcadores dinámicos resueltos en el momento de imprimir.
- Códigos incrustados como `data:` URI: el ticket se imprime sin conexión y cada
  bloque conserva su propio código al rasterizar.
- Texto de respaldo por tipo de bloque cuando un código no se puede generar.
- Configuración desde el formulario de `pos.config`, desde Ajustes del POS y desde un
  menú global de auditoría.
- Regla multi-compañía y ACLs para `group_pos_user` (lectura) y `group_pos_manager`.

## Tests

```bash
# Python (22 tests): constraints, loader del POS, campo imagen, integración con pos.config
odoo -d <bd> -i pos_ticket_customization --test-enable \
     --test-tags /pos_ticket_customization --stop-after-init

# JavaScript (QUnit): las funciones puras de receipt_block_utils.js
#   Web → Ajustes → Activar modo desarrollador → Ejecutar tests JS
#   Filtro: "pos_ticket_customization"
```

Dos de los tests de Python no prueban este módulo sino su **contrato con el core**, y
son los que más valor tienen a la hora de actualizar Odoo:

- `test_max_side_stays_within_core_limits`: comprueba que `MAX_CODE_SIDE` sigue por
  debajo de lo que acepta `ir.actions.report.barcode()`. Si el core endureciera sus
  límites, el tope dejaría de proteger y el ticket volvería a salir con la imagen rota.
- `test_every_barcode_type_is_a_real_reportlab_widget`: genera un código de cada
  simbología del selector. Un nombre que no exista en ReportLab (`Code39` en vez de
  `Standard39`, `ITF` en vez de `I2of5`) provoca un `KeyError` que `barcode()` no
  captura, así que el endpoint responde 500.

### Pendiente / posibles mejoras

- `i18n/`: no se incluye `.pot`. Las cadenas de Python y de las vistas están en español
  (idioma de operación). Genera la plantilla con
  `odoo -d <bd> --i18n-export=i18n/pos_ticket_customization.pot --modules=pos_ticket_customization`
  si necesitas traducir a otro idioma.
- Vista previa del bloque en el formulario de configuración (renderizar el QR en el
  backend antes de imprimir).
