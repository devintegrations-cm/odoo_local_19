# Clara Purchase Bridge

Base de solo lectura de los módulos de tarjetas corporativas Clara. Desde la versión 2.0.0 **no registra nada**: ningún método del módulo crea, confirma ni modifica órdenes de compra, y no se envía nada a Clara.

## Qué contiene

- **Tabla de titulares** (`clara.analytic.rule`, Compras › Configuración › Analítico por titular Clara): el área y la cuenta analítica (centro de costo) de cada titular de tarjeta, y un valor por defecto por área. El dashboard de Clara (`clara_connector`) la lee para mostrar el área y el centro de costo de cada tarjeta y transacción. Solo «Clara / Administrador» la edita; «Clara / Lectura» la consulta.
- **Grupos de acceso**, compartidos con el conector:
  - **Clara / Lectura**: ve todo el menú Clara (tarjetas, transacciones, trazabilidad, sincronizaciones) y no puede crear, editar ni borrar ningún registro. Lo reciben automáticamente los usuarios de Contabilidad y Finanzas (cualquier rol del módulo de Contabilidad).
  - **Clara / Administrador**: configura la API, ejecuta «Sincronizar ahora» y edita la tabla de titulares. Lo reciben los administradores del sistema.
- **Rastro de las órdenes registradas por versiones anteriores**: los campos Clara de la orden de compra (transacción, titular, comercio, cobro, decisión) se conservan en solo lectura, con la pestaña «Clara» del formulario y el filtro «Desde Clara». La columna de cédula de esas versiones se elimina: los módulos no vuelven a guardarla.

## Cómo se reconoce al titular

En este orden, sin adivinar:

1. **Uuid de Clara** (`cardholder_uuid`): viene en cada tarjeta y transacción; es la llave más fuerte.
2. **Correo** (`cardholder_email`): viene en cada tarjeta.
3. **Nombre normalizado exacto** (sin mayúsculas ni tildes). Si hay más de una regla con ese nombre, o la regla tiene otro uuid, no se asigna regla.
4. **Regla del área** (`area`), para quien no tiene regla propia o cuya regla no decide nada.

Una regla con cuenta analítica da el centro de costo; una de «varios centros de costo» solo da el área. Las reglas sembradas vienen de la tabla «Consolidado de tarjetas Clara» (corte 29/09/2026) sin uuid: el uuid se ve en cada tarjeta y transacción del dashboard.

**Cargar la tabla:** en la lista (editable en línea para administradores) o con la importación estándar de Odoo con las columnas `kind`, `name`, `cardholder_uuid`, `cardholder_email`, `area`, `analytic_name`, `multi_cost_center`; después, «Buscar cuentas por nombre» enlaza cada analítico estándar con la cuenta de Odoo que se llame así (ignora el prefijo `[INST]` y el sufijo ` - Libertario Coffee Roasters SAS`).

## Migración a 2.0.0

- Se borran las vistas del flujo de órdenes y sus parámetros (revisor, usuario del bot, contacto de Contabilidad, reglas de Expansión, tolerancias).
- Se elimina el índice único «una orden viva por transacción»: nada crea órdenes.
- No se toca ninguna orden ni transacción existente.

## Migración a 2.0.1

- Se eliminan de la base las columnas de cédula de versiones anteriores (`purchase_order.clara_cardholder_vat`, `clara_analytic_rule.cardholder_vat` y `clara_analytic_rule.vat_key`), solo si existen. No se toca ninguna otra columna ni tabla.

## Pruebas

```bash
odoo -d <base> -i clara_purchase_bridge --test-enable --test-tags /clara_purchase_bridge --stop-after-init
```
