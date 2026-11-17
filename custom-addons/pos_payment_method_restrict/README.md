# POS Payment Method Restrict

Módulo para Odoo 19 que permite definir una **lista blanca de métodos de pago**
por cliente en el Punto de Venta. Cada restricción se vincula a una
configuración de POS específica y puede exigir datos adicionales en un popup,
marcar la orden para factura (electrónica) y/o generar entregas de inventario.

## Comportamiento

| Situación | Resultado en el POS |
|---|---|
| Sin cliente seleccionado | Solo se muestran los métodos sin restricción |
| Cliente autorizado para 1+ métodos | Solo se muestran esos métodos |
| Cliente sin restricción asignada | Se muestran todos los métodos no restringidos |

Los métodos **no listados** en ninguna restricción permanecen disponibles para
todos los clientes.

## Configuración

El interruptor general y la edición de restricciones están en:

1. **Ajustes → Punto de Venta** → sección **Restricciones por cliente**.
   - Activar **Restricciones por cliente** (flag maestro: si está apagado, el
     POS muestra todos los métodos y la sección queda oculta).
   - Agregar restricciones: método de pago, clientes autorizados y acciones
     automáticas.

2. Alternativa: menú **Punto de Venta → Configuración → Restricciones de pago**.

Se puede **configurar incluso con la sesión del POS abierta**; los cambios se
reflejan al recargar o al cambiar de cliente en el POS.

### Por restricción

| Campo | Efecto |
|---|---|
| **Método de pago** | Método que se restringe |
| **Clientes autorizados** | Lista blanca (vacía = bloqueado para todos) |
| **Crear factura** | `to_invoice=True` al seleccionar el cliente |
| **Crear factura electrónica** | `to_ei_invoice=True` (requiere módulo DIAN) |
| **Crear entrega de inventario** | Genera stock.picking al validar |
| **Campos del popup** | Datos que el cajero debe capturar al pagar (texto corto/largo, entero; requeridos o no) |

Los flags `to_invoice`/`to_ei_invoice` solo se **activan** cuando la restricción
lo exige; el módulo nunca los desactiva, por lo que no interfiere con otros
módulos que fuerzan factura (electrónica).

## Funcionalidades

- **Filtro en vivo**: el método se muestra/oculta según el cliente de la orden
  (getter `payment_methods_from_config` recalculado en cada lectura).
- **Popup de datos**: al usar un método con campos configurados, se pide la
  información antes de añadir la línea de pago; los valores quedan guardados en
  la orden (`restriction_data` JSON + `restriction_id`).
- **Detección de duplicados**: al confirmar el popup se consultan las órdenes
  del día con la misma restricción y valores coincidentes (solo advierte, no
  bloquea).
- **Reportes**: menú **Punto de Venta → Informes → Convenios y restricciones**
  con órdenes del día/mensual y consumo de productos por convenio.
- **Factura agrupada**: acciones de servidor en la lista de órdenes para crear
  factura agrupada normal o electrónica (DIAN) por cliente.

## Arquitectura

```
models/pos_payment_customer_restriction.py  — restricción: config + método + partners + flags
models/pos_payment_restriction_field.py     — campo configurable del popup (field_key autogenerado)
models/pos_config.py                        — _load_pos_data_read inyecta _payment_restrictions al POS
models/pos_order.py                         — restriction_data/restriction_id, campos hotel,
                                              _should_create_picking_real_time, factura agrupada,
                                              check_restriction_duplicate
models/res_config_settings.py               — sección de ajustes + persistencia de la One2many

static/src/js/payment_method_restrict.js    — parches: PosOrder.serializeForORM (re-inyecta
                                              restriction_id), PosStore.selectPartner (re-aplica
                                              flags), PaymentScreen (filtro por cliente, popup,
                                              duplicados)
static/src/js/payment_restriction_popup.js  — popup como Component + Dialog web
static/src/xml/payment_restriction_popup.xml

views/pos_config_views.xml                  — vistas de restricción, menú y sección en Ajustes
views/pos_hotel_report_views.xml            — pestaña en la orden, búsqueda/lista y reportes
data/pos_order_server_actions.xml           — acciones "Factura agrupada" y "Factura electrónica agrupada"
```

El dict plano de restricciones viaja al frontend como campo extra
`_payment_restrictions` de `pos.config` (clave con prefijo `_`: el store JS
crea el getter automático). Como `pos.payment.customer.restriction` no se carga
en el store, `restriction_id` se re-inyecta en `serializeForORM`.

## Instalación

1. Copiar el módulo en el directorio de módulos de tu instancia Odoo 19.
2. Actualizar la lista de aplicaciones y buscar **POS Payment Method Restrict**.
3. Instalar y activar la restricción en *Ajustes → Punto de Venta*.

## Compatibilidad

- Odoo 19.0 Community y Enterprise
- No requiere módulos adicionales fuera de `point_of_sale`
- `to_ei_invoice` y la factura electrónica agrupada requieren el módulo
  de facturación electrónica DIAN correspondiente

## Licencia

LGPL-3 — ver <https://www.gnu.org/licenses/lgpl-3.html>