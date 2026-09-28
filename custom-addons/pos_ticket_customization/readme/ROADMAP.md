## Limitaciones conocidas

- **`{order_name}` en restaurante.** Toma el valor de `getName()` del pedido, que en
  `pos_restaurant` devuelve el nombre de la mesa ("T 5") o el texto de venta directa, no la referencia. En la
  captura de uso se ve así.
- **Recibo básico.** Los bloques *Antes del pie* se insertan junto a `div.before-footer`, que en la
  plantilla de Odoo 19 está dentro de `t-if="!props.basic_receipt"`; en un recibo básico no salen.
- **Bloques archivados en el formulario de la tienda.** El campo `custom_receipt_block_ids` lleva
  `context="{'active_test': False}"`, pero la lista embebida solo muestra los activos. Se ven y se
  reactivan desde el menú global o desde *Configurar bloques*.
- **El contador de Ajustes cuenta solo los activos**, aunque la etiqueta dice *Bloques
  configurados*.
- La frecuencia se reinicia en cada sesión de caja (usa `sequence_number`).
- Las etiquetas de la interfaz están en español dentro del código y no hay `i18n/`.
- No hay vista previa del bloque en el formulario: el resultado se ve en el POS.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_receipt_custom_block.py`: el modelo `pos.receipt.custom.block` (hereda
  `pos.load.mixin`), sus validaciones y la lista de campos que se envían al POS
  (`POS_LOADED_FIELDS`).
- `models/pos_session.py`: agrega el modelo en `_load_pos_data_models()`. El dominio de carga solo
  trae los bloques activos de la tienda de la sesión.
- `models/pos_config.py`: el One2many `custom_receipt_block_ids` y la acción que abre los bloques de
  una tienda.
- `models/res_config_settings.py`: el contador y el botón de *Ajustes*.
- `views/`: la sección en el formulario de `pos.config`, la opción en *Ajustes › Recibos y
  facturas*, las listas, el formulario, la búsqueda y el menú global.
- `security/`: permisos por grupo y regla multicompañía sobre el `company_id` heredado de la tienda.
- `static/src/utils/receipt_block_utils.js`: URLs de `/report/barcode`, payloads de WiFi, vCard,
  WhatsApp y reseña, marcadores y texto de respaldo.
- `static/src/app/services/pos_store.js`: parche de `PosStore`; carga los bloques, filtra por
  vigencia, importe y frecuencia, resuelve marcadores e incrusta las imágenes como `data:` URI.
- `static/src/app/services/printer_service.js`: parche de `PrinterService.print()` que incrusta los
  códigos antes de rasterizar.
- `static/src/app/screens/receipt_screen/receipt_screen.js`: parche de `_sendReceiptToCustomer()`
  para el envío por correo.
- `static/src/app/screens/receipt_screen/receipt/order_receipt.js`, `.xml` y `.scss`: `setup()` y el
  getter `customReceiptBlocks` de `OrderReceipt`, la herencia de la plantilla
  `point_of_sale.OrderReceipt` y los estilos (clases `o_ptc_*`).

## Notas para mantenimiento

- **Puntos de anclaje en la plantilla.** La herencia usa `//ReceiptHeader` (after),
  `//div[hasclass('before-footer')]` (before) y `//div[hasclass('after-footer')]` (inside). Los tres
  existen en `point_of_sale.OrderReceipt` de Odoo 19. La herencia se resuelve en el navegador: si una
  versión futura quita alguno, la instalación no avisa y el error aparece al abrir el POS.
- **`OrderReceipt` no tiene `setup()` en Odoo 19.** El parche define uno para tener `this.pos` con
  `usePos()`. Si el core agrega su propio `setup()`, el parche debe llamar a `super.setup()`.
- **Por qué se incrustan las imágenes.** Al imprimir, `htmlToCanvas` cachea cada recurso por URL
  **sin la query string** (`getCacheKey` en `point_of_sale/static/src/app/utils/html-to-image.js`).
  Todos los códigos son `/report/barcode/?...`, así que sin incrustarlos el primer código se
  repetiría en todos los bloques. Con `data:` URI esa caché no interviene. En la reimpresión de la
  captura, los dos QR del ticket llegaron como `data:image/png;base64`.
- **Simbologías.** Los valores del selector son nombres de ReportLab (`Standard39`, `I2of5`), no
  `Code39` ni `ITF`: con un nombre inválido `ir.actions.report.barcode()` lanza `KeyError`, el
  endpoint responde 500 y el ticket sale con la imagen rota.
- **Tope de 1000 px por lado.** `ir.actions.report.barcode()` rechaza imágenes de más de 1 200 000
  px²; el endpoint lo devuelve como HTTP 200 con HTML y el `<img>` sale roto sin error en el log. La
  validación del modelo lo evita.
- **Query string en `/report/barcode`.** Se usa `?barcode_type=..&value=..` en lugar de la forma de
  ruta, porque los payloads de WiFi, vCard y URLs llevan `/` y saltos de línea.
- **Tests.** `tests/test_receipt_custom_block.py` (22 tests: validaciones, carga al POS, campo
  imagen, integración con `pos.config` y el contrato con `barcode()` del core) y
  `static/tests/receipt_block_utils_tests.js` (QUnit, funciones de `receipt_block_utils.js`). Los
  parches del POS no tienen test automático: se validan en el navegador.
