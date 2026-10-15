Agrega al POS un botón **Factura electrónica** para que el cajero valide ante la DIAN al cliente
que pide factura electrónica **antes** de asignarlo a la orden. Consulta el registro de adquirentes
de la DIAN a través del servicio **Edipo de Jorels**, con el mismo token (`api_key`) con el que la
compañía factura.

Con el resultado, el cajero ve el nombre que registró la DIAN, el documento tal como se guardará
(p.ej. `890903938-8`) y el correo, y decide:

- **Asignar** al cliente que ya existe en Odoo. Si le faltan datos de facturación, se completan solo
  los campos **vacíos**. Nunca se pisan valores existentes, salvo que el cajero marque
  *Reemplazar nombre y correo con los datos de la DIAN*.
- **Crear y asignar** al cliente que la DIAN confirma y no existe en Odoo. Se crea con el nombre tal
  como lo devuelve la DIAN, régimen *No responsable de IVA*, responsabilidad *No aplica – Otros*,
  el municipio de la compañía y país Colombia. Si la DIAN no tiene correo, el popup se lo pide al
  cajero.
- **No asignar a nadie** si la DIAN no confirma el documento, si el número existe en Odoo con otro
  tipo de documento o si hay un error de configuración o de conexión. Cada caso muestra un mensaje
  distinto para que no se confunda un "no registrado" con una falla del servicio.

Una vez asignado el cliente, la orden queda marcada para **Factura**.

**Importante:** los datos que devuelve la DIAN los registraron los emisores que ya le facturaron a
ese cliente, y pueden estar desactualizados o ser de otra persona. El cajero tiene que confirmar el
nombre y el correo con el cliente antes de asignar.

**Efecto colateral:** el módulo **oculta siempre** el botón nativo *Guardar orden* (ícono de
subida, `fa-upload`) en la pantalla de producto y en la barra de acciones de pantallas chicas, esté
activo o no el botón *Factura electrónica* en esa caja.

**Ocultar botón de cliente (por caja, opcional):** el segundo ajuste de configuración retira el
botón nativo *Cliente* de la vista de orden (escritorio y móvil) y de la vista de pago (donde
*Factura/Recibo* pasa a ocupar todo el ancho). El cliente se gestiona entonces solo con *Factura
electrónica*, que muestra debajo el nombre del cliente ya asignado. Con esta opción activa no hay
forma de desasignar un cliente desde la interfaz.
