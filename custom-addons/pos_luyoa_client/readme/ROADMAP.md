## Upgrade pendiente: registrar transacciones en Luyoa

El módulo hoy **solo identifica** al cliente (lectura). El API de Luyoa
expone tres endpoints de escritura para un futuro upgrade, documentados acá
para no tener que volver al spec:

- `POST /transaction` — registrar una compra (suma sellos/saldo según las
  reglas del negocio en Luyoa). Campos: `customerUID` (opcional: sin él la
  transacción se guarda solo para análisis), `businessBranchUID` (obligatorio:
  mapear cada `pos.config` → un branch de Luyoa con `GET /business-branch`),
  `total` (≥ 0), `reference` (nº de ticket, único), `createdAt` (ISO 8601,
  opcional) y `items[]` (`code`, `name`, `quantity` ≥ 1, `priceEach` ≥ 0).
  Respuesta: `{"success": true, "data": "…"}`.
- `POST /transaction/bulk` — hasta 100 transacciones por llamada
  (`{"transactions": [...]}`). Respuesta con `processed` / `successful` /
  `failed` y errores por `reference`: sirve para subir el día completo al
  cierre de caja.
- `POST /reward/redeem/:rewardUID` — canjear un reward del cliente. Cuerpo:
  `{"businessBranchUID": "…"}`. Los rewards disponibles por cliente vienen en
  `GET /customer/:customerUID` (`data.rewards[]`: `uid`, `name`, `type` en
  `FREE_PRODUCT` | `DISCOUNT` | `OTHER`, `expiresAt` en ms y
  `externalReference` para ligarlo a un producto del POS).

Punto de enganche natural: la validación del pago (`validateOrder`) para
`/transaction`, y el cierre de caja para el bulk. La UI ya conoce el
`customerUID` (se guarda en `res.partner.luyoa_customer_uid` al asignar).

## Límites conocidos

- **Sin webhook**: Luyoa no notifica cambios (puntos canjeados en su app,
  por ejemplo); todo lo que el POS muestra es lo que consulta al escanear.
- **Sin historial de transacciones**: el API no expone `GET /transaction`, no
  se puede conciliar desde Odoo.
- **Nombre y teléfono**: el teléfono se compara por dígitos con
  `ILIKE '%<dígitos>%'`; uno guardado en Odoo con espacios (`+52 55 1234 5678`)
  no coincide y el popup ofrece crear el cliente. El correo es la clave
  principal y la tarjeta vinculada resuelve los próximos escaneos.
- **Tarjeta vinculada no visible**: el identificador de Luyoa del contacto no
  se muestra en ninguna vista. Si hubiera que desvincular una tarjeta, hoy se
  hace por base de datos o modo desarrollador.
- **Sin catálogo de rewards**: solo se ven los rewards del cliente escaneado
  (vienen en su respuesta); no hay endpoint de catálogo.
- **Concurrencia**: dos cajas que crean el mismo cliente al mismo tiempo
  pueden dejar un duplicado; la restricción de unicidad impide que la misma
  tarjeta quede en dos contactos, y la próxima consulta informa el resto
  como ambiguo.
