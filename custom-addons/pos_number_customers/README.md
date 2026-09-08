# Ask Number of Customers

Pregunta **el número de clientes** de un pedido antes de validarlo, en un
restaurante con `pos_restaurant`.

## Configuración (Ajustes → Punto de Venta → Interfaz)

| Campo | Descripción | Por defecto |
|---|---|---|
| **Número de clientes** | Activa la pregunta al validar el pago | Falso |
| **Mínimo / Máximo** | Rango aceptado | 1 / 20 |

El rango se valida en servidor (`pos.config.number_customers_min/max`): antes eran
los números `1` y `20` escritos dentro del JavaScript.

## Cómo se aplica en Odoo 19

`static/src/app/utils/order_payment_validation.js` parcha
**`OrderPaymentValidation.askBeforeValidation()`**, el gancho documentado del núcleo
para interrumpir la validación (devolver `false` la aborta).

En la versión de 17 se parcheaba `Order.pay()`, que ya no existe, y sólo cubría la
pantalla de pago: la **validación rápida** de la pantalla de productos y el flujo
`fastPayments` la saltaban, así que el pedido se validaba sin preguntar. Ahora
todas las rutas pasan por el mismo punto, que es además el que usa `l10n_es_pos`
para su propio requisito previo.

El valor se guarda con `order.setCustomerCount()`, el mismo campo que usan las
mesas del restaurante, por lo que tickets y reportes siguen funcionando. Si el
cajero cancela la pregunta, el pedido **no** se valida: se queda en pantalla de
pago para reintentar.

## Limpieza

- `security/ir.model.access.csv` estaba huérfano: no está en `data` y referenciaba
  un modelo (`pos_customer_number.pos_customer_number`) que el módulo no define.
  Eliminado.
- El archivo `static/src/js/product_screen.js` no parcheaba ninguna pantalla: era
  el modelo del pedido. Renombrado a la ruta real de 19.
- Campos de `res.config.settings` con prefijo `pos_` (TransientModel compartido).

## Pruebas

`tests/test_number_customers_config.py` (5): rangos por defecto, rechazo de rango
absurdo (mínimo < 1, máximo < mínimo) y escritura efectiva desde Ajustes.

## Licencia / Autor

LGPL-3 — Libertario Coffee Roasters
