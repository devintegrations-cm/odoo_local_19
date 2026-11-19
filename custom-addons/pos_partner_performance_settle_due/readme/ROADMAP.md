## Limitaciones conocidas

- **No hay control de límite de crédito en el POS** en las cajas con la opción activada:
  `pos_settle_due` bloquea la venta a un cliente que supera su límite usando la deuda cargada. Hoy
  no aplica: la compañía tiene desactivado el límite de crédito (`account_use_credit_limit`) y
  ningún contacto tiene límite (verificado en staging, 2026-11-18). Si se activa, desmarcar la
  opción en las cajas que lo necesiten.
- **No se puede probar en local** (no hay `pos_settle_due`): se prueba en staging.
- **Depende del código de `pos_settle_due`** (`setAllTotalDueOfPartners`, `get_all_total_due`, la
  condición `total_due !== undefined` del recálculo tras la venta y los campos `total_due`,
  `invoices_amount_due` y `pos_orders_amount_due`). Si una actualización de Enterprise los cambia,
  la intercepción dejaría de funcionar **sin dar error**. Para evitarlo, los tests del módulo
  comprueban que todo eso sigue existiendo y fallan si no: correrlos en staging después de cada
  actualización de Enterprise.
