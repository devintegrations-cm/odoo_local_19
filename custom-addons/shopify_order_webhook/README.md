# Shopify Order Webhook

Módulo Odoo 17 que integra Shopify con Odoo en dos direcciones:

* **Recibe webhooks** de órdenes de Shopify (`orders/create`, `orders/paid`,
  etc.) y los convierte en órdenes de venta, facturas y pagos.
* **Consulta la Admin API** de Shopify (GraphQL) para simular el mapeo,
  importar pedidos manualmente y mapear productos.

Todo con configuración **por compañía** y disparadores de facturación
flexibles.

* **Versión**: 17.0.1.9.2
* **Categoría**: Sales/Sales
* **Dependencias Odoo**: `base`, `sale`, `sale_management`, `sale_stock`,
  `account`, `stock`, `mail`, `crm`, `l10n_co_edi_jorels`
* **Dependencias Python**: `python-dateutil`, `requests`

---

## Tabla de contenido

1. [Características](#características)
2. [Instalación](#instalación)
3. [Configuración](#configuración)
4. [URL del webhook](#url-del-webhook)
5. [Flujo de procesamiento](#flujo-de-procesamiento)
6. [Precios e impuestos](#precios-e-impuestos)
7. [Disparadores de facturación](#disparadores-de-facturación)
8. [Admin API: consulta, simulación, importación y mapeo](#admin-api-consulta-simulación-importación-y-mapeo)
9. [Mapeos configurables](#mapeos-configurables)
10. [Multi-compañía](#multi-compañía)
11. [Seguridad y verificación HMAC](#seguridad-y-verificación-hmac)
12. [Idempotencia](#idempotencia)
13. [Notificaciones y entrega](#notificaciones-y-entrega)
14. [Arquitectura técnica](#arquitectura-técnica)
15. [Script de prueba](#script-de-prueba)
16. [Limitaciones conocidas](#limitaciones-conocidas)

---

## Características

### Recepción de webhooks
* Endpoint HTTP `POST /shopify/order/<company_id>` que acepta el payload
  JSON de Shopify.
* Verificación obligatoria de firma `X-Shopify-Hmac-SHA256` (timing-safe)
  con secret por compañía (sin secret, el webhook rechaza todo con 401).
* Búsqueda o creación automática del partner por VAT, email o teléfono.
* Resolución del producto por **mapeo explícito** (variante/SKU), luego
  por SKU, y por último creación de un consumible placeholder.
* Resolución de impuestos compatibles con la compañía (filtra `taxes_id`
  por `company_id`, evitando errores de "Incompatible companies").
* **Ajuste de precios** según cómo vienen de Shopify (impuestos incluidos
  o no) y la configuración del impuesto en Odoo.
* Línea de **envío** opcional usando un producto configurable.
* **Idempotencia** por `shopify_order_id` + `company_id` (advisory lock +
  constraint UNIQUE).
* **Tres disparadores de facturación**: al confirmar, al validar la
  entrega, o tras N horas (cron).
* Registro automático opcional de pago entrante con reconciliación.
* Notificaciones a responsables de almacén y contabilidad, con etiqueta
  de entrega en PDF.
* Descripción de Shopify reflejada en la **entrega** (no la genérica del
  producto).
* Vendedor, equipo de ventas y producto de envío **por defecto**.

### Admin API (independiente del webhook)
* Autenticación **`client_credentials`** (Client ID + Secret del Dev
  Dashboard); token cacheado ~24 h.
* **Simulación dry-run** de las últimas 10 órdenes (valida el mapeo sin
  guardar nada).
* **Importación manual** de pedidos desde un menú dedicado.
* **Mapeo de productos** Shopify → `product.product`.

### Configuración
* 100 % **por compañía**: cada compañía tiene su propio secret, almacén,
  diario, mapeos, credenciales API, etc.

---

## Instalación

1. Copia o clona la carpeta `shopify_order_webhook` dentro del
   `addons_path` configurado en `odoo.conf`.
2. Asegúrate de tener `python-dateutil` y `requests` en el entorno
   (ambos vienen con Odoo).
3. Reinicia el servicio de Odoo.
4. Ve a **Apps** → **Update Apps List**.
5. Busca **Shopify Order Webhook** y haz clic en **Install**.

---

## Configuración

La configuración vive en:

> **Settings → Sales → Shopify Connector**

Todos los campos se guardan en `res.company` (almacenamiento
per-compañía). Con varias compañías, switchea con el selector superior y
configura cada una por separado.

### Estructura del formulario

```
┌─ Habilitar Shopify Webhook (master toggle)
│   ├─ Secreto del Webhook
│   ├─ URL del Webhook (computado, copiable con un click)
│   ├─ ☐ Activar logging de depuración
│   │
│   ├─ Columna izquierda
│   │   ├─ VENTAS
│   │   │   ├─ Precios de Shopify (impuestos incluidos / no)
│   │   │   ├─ Lista de Precios por Defecto
│   │   │   ├─ Cuenta Analítica
│   │   │   ├─ Etiqueta por defecto
│   │   │   ├─ Vendedor por defecto
│   │   │   ├─ Equipo de ventas por defecto
│   │   │   ├─ Producto de envío por defecto
│   │   │   └─ Mapeo de etiquetas por origen (editable list)
│   │   │
│   │   └─ INVENTARIO
│   │       └─ ☐ Registro automático de entrega
│   │           ├─ Almacén
│   │           └─ Responsable de Almacén
│   │
│   └─ Columna derecha
│       └─ CONTABILIDAD
│           ├─ ☐ Creación automática de facturas
│           │   ├─ Generar la factura (al confirmar / al entregar / diferido)
│           │   ├─ Horas de retraso (solo si trigger = diferido)
│           │   ├─ Diario de Facturas
│           │   ├─ Responsable de Contabilidad
│           │   └─ ☐ Registro automático de pago
│           │       └─ Mapeo de métodos de pago (editable list)
│
└─ API de Shopify (bloque independiente)
    └─ ☐ Activar consulta a la API de Shopify
        ├─ Dominio de la tienda (*.myshopify.com)
        ├─ Client ID + Client Secret (Dev Dashboard)
        ├─ Token manual (opcional, apps custom heredadas)
        ├─ Versión de la Admin API
        └─ [Botón] Simular últimas 10 órdenes
```

### Campos relevantes (selección)

| Campo | Tipo | Descripción |
|---|---|---|
| `shopify_enable_webhook` | Boolean | Si está OFF, la URL responde 403. |
| `shopify_webhook_secret` | Char | Secret para verificar HMAC. Vacío = el webhook rechaza toda solicitud (401). |
| `shopify_price_tax_mode` | Selection | `included` / `excluded`: cómo vienen los precios de Shopify. |
| `shopify_default_price_list_id` | Many2one | Lista de precios aplicada a la orden. |
| `shopify_account_analytic_id` | Many2one | Cuenta analítica de líneas de orden/factura. |
| `shopify_default_tag_id` | Many2one (`crm.tag`) | Etiqueta por defecto. |
| `shopify_default_user_id` | Many2one (`res.users`) | Vendedor por defecto. |
| `shopify_default_team_id` | Many2one (`crm.team`) | Equipo de ventas por defecto. |
| `shopify_shipping_product_id` | Many2one (`product.product`) | Producto para la línea de envío. |
| `shopify_warehouse_id` | Many2one | Almacén de la orden. |
| `shopify_auto_invoice` | Boolean | Activa la facturación. |
| `shopify_invoice_trigger` | Selection | `on_confirm` / `on_delivery` / `delayed`. |
| `shopify_invoice_delay_hours` | Integer | Horas de espera con `trigger = delayed`. |
| `shopify_auto_payment` | Boolean | Registro automático de pago entrante. |
| `shopify_enable_api` | Boolean | Activa el bloque de credenciales Admin API. |
| `shopify_shop_url` | Char | Dominio `*.myshopify.com`. |
| `shopify_client_id` / `shopify_client_secret` | Char | Credenciales del Dev Dashboard (grant `client_credentials`). |
| `shopify_admin_api_token` | Char | Token manual opcional (apps custom heredadas). |
| `shopify_api_version` | Char | Versión de la Admin API (AAAA-MM). |
| `shopify_source_tag_mapping_ids` | One2many | Tabla `source_name` → etiqueta. |
| `shopify_payment_mapping_ids` | One2many | Tabla gateway Shopify → diario Odoo. |

---

## URL del webhook

Cada compañía tiene su propio endpoint:

```
POST {web.base.url}/shopify/order/{company_id}
```

El campo **URL del Webhook** en Settings la muestra ya formada y con
botón de copiar.

### Configurar en Shopify

En **Shopify Admin → Settings → Notifications → Webhooks**:

1. Crea un webhook **Order creation** (o el evento que necesites).
2. Formato: **JSON**.
3. URL: pega la del campo *URL del Webhook*.
4. Copia el **Webhook signing secret** y pégalo en *Secreto del Webhook*.

---

## Flujo de procesamiento

```
POST /shopify/order/<company_id>
        │
        ▼
1.  Validar compañía y que shopify_enable_webhook = True
2.  Verificar HMAC (sin secret configurado → 401)
3.  Parsear JSON
4.  Idempotencia: si shopify_order_id ya existe → 200 'skipped'
        (advisory lock + UNIQUE como defensa en profundidad)
5.  Cargar configuración desde res.company
6.  Resolver almacén (fallback: primero de la compañía)
7.  Buscar/crear partner (por VAT / email / teléfono)
8.  Construir líneas de orden:
        ├─ Resolver producto (mapeo por variante/SKU → SKU → placeholder)
        ├─ Filtrar impuestos por compañía
        ├─ Ajustar precio según "Precios de Shopify" + price_include
        ├─ Línea de envío (producto de envío configurado)
        └─ Aplicar distribución analítica
9.  Crear sale.order (vendedor/equipo por defecto) y confirmar
10. Si auto_invoice, según trigger:
        ├─ on_confirm  → _shopify_process_invoice() inmediato
        ├─ on_delivery → stock.picking._action_done dispara la factura
        └─ delayed     → shopify_invoice_scheduled_at = now + N h
11. Si auto_delivery → notifica a almacén + etiqueta PDF
12. Responde 200 con {'status': 'success', 'order_id': N}
```

---

## Precios e impuestos

Shopify normalmente envía precios **con impuesto incluido**, mientras que
en Odoo el impuesto puede estar configurado como incluido o no. El campo
**Precios de Shopify** (`shopify_price_tax_mode`) más el flag
`price_include` del impuesto deciden cómo se ajusta `price_unit` para que
el total de la orden coincida siempre con el de Shopify:

| Shopify \ Odoo | `price_include=True` | `price_include=False` |
|---|---|---|
| Impuestos incluidos | pasa igual | **divide** el impuesto (→ neto) |
| Impuestos no incluidos | suma el impuesto (→ con IVA) | pasa igual |

Solo se convierten impuestos **porcentuales**; los de monto fijo se dejan
para que Odoo los aplique.

---

## Disparadores de facturación

El campo `shopify_invoice_trigger` define **cuándo** se factura. Solo
aplica si `shopify_auto_invoice = True`.

* **`on_confirm`** (por defecto): factura, postea y notifica al recibir el
  webhook. Si `auto_payment` está activo, también paga y reconcilia.
* **`on_delivery`**: cuando el picking pasa a `done`, el override de
  `stock.picking._action_done()` dispara `_shopify_process_invoice()`.
  Soporta entregas parciales.
* **`delayed`**: marca `shopify_invoice_scheduled_at = now + N h`; un cron
  horario factura las órdenes vencidas y limpia el timestamp.

```sql
WHERE is_shopify_order = True
  AND shopify_invoice_scheduled_at <= NOW()
  AND state IN ('sale', 'done')
  AND invoice_status != 'invoiced'
```

---

## Admin API: consulta, simulación, importación y mapeo

El bloque **API de Shopify** es independiente del webhook. Usa el grant
**`client_credentials`**: con Client ID + Client Secret del Dev Dashboard,
Odoo solicita el token a `POST /admin/oauth/access_token` y lo **cachea
~24 h** (también acepta un token manual `shpat_…`).

> **Requisitos**: la app del Dev Dashboard debe estar **instalada** en la
> tienda (custom distribution) y tener los scopes `read_orders` y
> `read_products` (`read_customers` es opcional — el nombre del cliente se
> toma de la dirección de la orden).

### Simulación (dry-run)
Botón **Simular últimas 10 órdenes** en Settings: trae las 10 órdenes más
recientes vía GraphQL y construye las ventas dentro de un SAVEPOINT que se
**revierte siempre**. Abre un wizard con líneas, impuestos y totales — no
guarda nada. Valida el mapeo antes de operar en vivo.

### Importación manual
Menú **Ventas → Pedidos de Shopify** (`shopify.order.import`):

* **Sincronizar desde Shopify** trae los pedidos recientes a una caché.
* **Registrar en Odoo** (por fila o en lote) crea la `sale.order`
  confirmada real, reusando exactamente la lógica del webhook y
  respetando la idempotencia.

### Mapeo de productos
Menú **Ventas → Productos → Mapeo de productos Shopify**
(`shopify.product.mapping`):

* **Sincronizar** trae el catálogo (productos + variantes, paginado).
* Asigna a cada variante su `product.product` (edición inline y múltiple).
* Filtros por estado Odoo (mapeado / sin mapear) y estado Shopify
  (ACTIVE / DRAFT / ARCHIVED).
* El webhook y la importación consultan este mapeo (por `variant_id`,
  luego SKU) antes de su búsqueda/creación por defecto.

---

## Mapeos configurables

### Etiquetas por origen (`shopify.source.tag.mapping`)

| Campo | Tipo | Descripción |
|---|---|---|
| `sequence` | Integer | Prioridad. Menor = primero. |
| `source_pattern` | Char | Substring case-insensitive en `source_name`. |
| `tag_id` | Many2one (`crm.tag`) | Etiqueta a aplicar. |
| `company_id` | Many2one | Compañía dueña del mapeo. |

Itera por `sequence` y devuelve la primera coincidencia; si ninguna,
aplica `shopify_default_tag_id`.

### Métodos de pago (`shopify.payment.journal.mapping`)

| Campo | Tipo | Descripción |
|---|---|---|
| `shopify_gateway` | Char | Identificador (e.g. `shopify_payments`, `paypal`). |
| `journal_id` | Many2one (`account.journal`) | Diario bank/cash de la compañía. |
| `company_id` | Many2one | Compañía dueña del mapeo. |

Busca un mapping cuyo `shopify_gateway` esté entre los
`payment_gateway_names` de la orden; fallback al primer diario bank/cash.

---

## Multi-compañía

Todos los campos están en `res.company` y expuestos en
`res.config.settings` vía `related='company_id.xxx'`. El selector de
compañía cambia la configuración mostrada sin pisar las demás, y los
Many2one filtran por `company_id` para restringir las opciones a la
compañía activa.

---

## Seguridad y verificación HMAC

El controlador implementa `X-Shopify-Hmac-SHA256` con
`hmac.compare_digest` (timing-safe):

1. Lee `request.httprequest.data` (raw body).
2. Calcula `base64(hmac.new(secret, raw_body, sha256).digest())`.
3. Compara contra el header; si no coincide → `401 Invalid HMAC signature`.

Si la compañía no tiene secret, la solicitud se rechaza con
`401 Webhook secret not configured` (desde 19.0.1.9.3; en 17 se aceptaba
sin autenticar). Para desarrollo, configure un secret de prueba.

Las credenciales de la Admin API (token cacheado) se guardan en
`res.company`; el Client Secret y el token manual se muestran como campos
password en la UI.

---

## Idempotencia

Clave por `shopify_order_id` (numérico, inmutable) + `company_id`, con
defensa en profundidad:

1. `pg_advisory_xact_lock` serializa webhooks concurrentes del mismo
   pedido.
2. Búsqueda previa que corta en caliente si el pedido ya existe.
3. Constraint `unique(shopify_order_id, company_id)` como garantía final
   (capturada para responder `skipped` en vez de fallar).

Cubre reintentos de Shopify, reenvíos manuales, doble registro desde el
menú de importación, y carreras webhook/importación.

---

## Notificaciones y entrega

* La notificación de almacén (al crear el picking) y la de contabilidad
  (al postear la factura) usan **`message_post`**: dejan traza en el
  chatter del documento **y** notifican por inbox/email a los
  responsables configurados.
* Se adjunta una **etiqueta de entrega en PDF** (formato 1/8 de carta) con
  la dirección de Shopify.
* La **descripción del producto en la entrega** (`description_picking`)
  refleja la de la línea de venta tal como llegó de Shopify.

---

## Arquitectura técnica

```
shopify_order_webhook/
├── __manifest__.py
├── __init__.py
├── README.md
├── controllers/
│   └── controllers.py          ← ShopifyOrderController (endpoint HTTP)
├── data/
│   └── ir_cron.xml             ← cron horario para trigger 'delayed'
├── models/
│   ├── res_company.py          ← config per-company + cliente Admin API
│   ├── res_config_settings.py  ← related= + simulación (dry-run)
│   ├── sale_order.py           ← _shopify_process_invoice y métodos asoc.
│   ├── stock_picking.py        ← hook _action_done (trigger on_delivery)
│   ├── stock_move.py           ← descripción de Shopify en la entrega
│   ├── shopify_order_import.py     ← consulta/importación manual de pedidos
│   ├── shopify_product_mapping.py  ← mapeo variante Shopify → product.product
│   ├── shopify_order_simulation.py ← wizard de resultado de la simulación
│   ├── shopify_payment_mapping.py
│   └── shopify_source_tag_mapping.py
├── report/
│   └── report_shopify_delivery_label.xml   ← etiqueta de entrega PDF
├── security/
│   └── ir.model.access.csv     ← ACLs para los modelos
├── static/description/         ← index.html + capturas
├── test/
│   └── send_test_order.py      ← script para invocar el endpoint
└── views/
    ├── res_config_settings_views.xml
    ├── shopify_order_import_views.xml      ← menú "Pedidos de Shopify"
    ├── shopify_product_mapping_views.xml   ← menú "Mapeo de productos"
    └── shopify_order_simulation_views.xml
```

### Modelos clave

| Modelo | Tipo | Propósito |
|---|---|---|
| `res.company` | extend | Configuración Shopify + cliente Admin API (token, GraphQL, mapper). |
| `res.config.settings` | TransientModel inherit | UI Settings + simulación dry-run. |
| `sale.order` | extend | `is_shopify_order`, `shopify_order_id`, lógica de facturación. |
| `stock.picking` | extend | Override `_action_done` para trigger `on_delivery`. |
| `stock.move` | extend | Copia la descripción de Shopify a la entrega. |
| `shopify.order.import` | nuevo | Caché + importación manual de pedidos. |
| `shopify.product.mapping` | nuevo | Mapeo variante Shopify → `product.product`. |
| `shopify.order.simulation` | nuevo (transient) | Resultado del dry-run. |
| `shopify.source.tag.mapping` | nuevo | Mapeo `source_name` → `crm.tag`. |
| `shopify.payment.journal.mapping` | nuevo | Mapeo gateway → `account.journal`. |

### Métodos destacados

| Método | Modelo | Descripción |
|---|---|---|
| `_shopify_get_access_token()` | `res.company` | Token vía `client_credentials` (cacheado 24 h) o manual. |
| `_shopify_fetch_last_orders(limit)` | `res.company` | Últimas órdenes por GraphQL → payload tipo webhook. |
| `_shopify_fetch_products(max)` | `res.company` | Catálogo paginado → una fila por variante. |
| `_build_order_vals(...)` | controlador | Mapea el payload a los vals de `sale.order` (compartido). |
| `action_shopify_simulate_last_orders()` | `res.config.settings` | Dry-run de las últimas 10 órdenes. |
| `_register_order(controller)` | `shopify.order.import` | Crea la `sale.order` real (idempotente). |
| `_shopify_process_invoice()` | `sale.order` | Crea+postea+notifica (+paga) la factura. |

---

## Script de prueba

`test/send_test_order.py` emula un webhook contra Odoo local; el payload
de ejemplo está en `test/test_shopify_data.json`.

La configuración se toma de variables de entorno (el secret **no** se
versiona; use el de la compañía de pruebas, nunca el de producción):

```bash
export SHOPIFY_TEST_ODOO_URL="http://localhost:8104"
export SHOPIFY_TEST_COMPANY_ID=1
export SHOPIFY_TEST_WEBHOOK_SECRET="<secret de la compañía de pruebas>"
cd shopify_order_webhook/test
python3 send_test_order.py
```

Salida en éxito:

```json
{ "status": "success", "order_id": 36 }
```

Salida si ya existía (idempotencia):

```json
{ "status": "skipped", "reason": "already_processed", "order_id": 36, "order_name": "S00036" }
```

---

## Limitaciones conocidas

* **Solo creación de orden**: el webhook no procesa reembolsos,
  cancelaciones ni cambios de estado del pago.
* **Productos placeholder como `consu`**: si una variante no está mapeada
  ni existe por SKU, se crea un `product.product` consumible (no
  storable) para evitar errores de routing en `action_confirm`.
* **Matching de partner por email**: puede colapsar dos clientes Shopify
  con el mismo email a un solo `res.partner`.
* **Tope de sincronización**: la importación trae las últimas ~50 órdenes
  y el mapeo hasta ~1000 productos por sincronización (ampliable).
* **`client_credentials` requiere app instalada**: si la app del Dev
  Dashboard no está instalada en la tienda, el grant devuelve
  `app_not_installed`.
* **`l10n_co_edi_jorels` como dependencia dura**: si tu instancia no es
  Colombia, reemplaza la dependencia y elimina el `'ei_is_valid': True`
  en `_shopify_post_invoice`.
```
