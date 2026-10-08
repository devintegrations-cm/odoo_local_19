Genera desde la lista de pagos el archivo .xlsx que se copia en la macro PAB de Bancolombia para
dispersar pagos a proveedores (tipo de pago **220**) o de nómina (tipo **225**).

- **Dos acciones en los pagos.** *Generar fichero de dispersión Bancolombia* (220) y *Generar
  fichero de dispersión Bancolombia - Nómina* (225), en el menú *Acciones* de la lista de pagos.
- **Tipo de transacción.** Campo nuevo en la cuenta bancaria del proveedor (*Abono a cta de
  Ahorros*, *Abono cta Corriente*, *Pago en Efectivo*, etc.). Al elegir la cuenta en el pago, el
  tipo se copia solo; se puede cambiar a mano en el pago.
- **Validaciones antes de generar.** Un solo diario, diario con cuenta origen, tipo de transacción,
  cuenta destino y banco con código. Si algo falta, avisa qué pago y no genera nada.
- **Columnas configurables.** Cada columna del cuerpo del archivo es una fórmula en Python que se
  edita en *Configuración*, sin tocar código.
- **Historial.** Cada archivo generado queda guardado en *Dispersiones bancarias* con sus pagos.

Depende de `account_payment_dispersion`, que aporta el código de banco, el tipo de cuenta y el
historial de dispersiones.
