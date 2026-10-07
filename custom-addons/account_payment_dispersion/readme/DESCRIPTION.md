Base de la dispersión de pagos a proveedores para Colombia. Deja en Odoo los datos que necesita un
archivo de dispersión bancaria y guarda el historial de las dispersiones hechas.

- **Bancos colombianos.** Carga 68 bancos de Colombia con su **Código** de banco, un campo nuevo
  distinto del BIC que es el que piden los archivos de dispersión.
- **Tipo de cuenta.** Agrega el campo **Tipo de cuenta** (*Sin cuenta*, *Cuenta corriente*, *Cuenta
  de ahorro*, *Cuenta nómina*) a las cuentas bancarias de los contactos.
- **Pagos a proveedor.** El pago saliente muestra el tipo de cuenta de la cuenta bancaria del
  proveedor, sin tener que abrirla.
- **Historial de dispersiones.** Un registro por dispersión con el archivo generado, el diario y los
  pagos incluidos, en solo lectura.

Este módulo no genera archivos por sí solo: los generan los módulos de cada banco
(`bancolombia_payment_dispersal`, `banco_de_occidente_payment_dispersal`), que se apoyan en él.
