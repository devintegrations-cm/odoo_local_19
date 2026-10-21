1. Con una orden abierta, toque el botón **Cliente Luyoa**:

   - En desktop: el icono cuadrado junto al botón *Nota*, o *Cliente Luyoa* en el submenú de los 3 puntos.
   - En pantallas pequeñas: el botón *Luyoa* de la barra de acciones (junto a *Cliente*).
   - En la pantalla de pago: el logo de Luyoa sobre el teclado numérico.

![Pantalla de la orden: botón Cliente Luyoa junto a Nota](../static/description/02_boton_orden.png)

2. Se abre la cámara; apunte al QR de la tarjeta digital del cliente
   (Apple/Google Wallet). Si cancela la cámara, el popup queda abierto para
   reintentar.
3. Revise los datos mostrados (cliente de Luyoa y contacto de Odoo) y toque
   **Asignar cliente** o **Crear y asignar**. La orden queda con el cliente
   asignado y marcada para facturar.

Si el cliente ya existe en Odoo, el popup muestra los dos lados y por qué
coincidieron (tarjeta escaneada, correo, o nombre y teléfono):

![Cliente de Luyoa que ya existe en Odoo: Asignar cliente](../static/description/03_cliente_encontrado.png)

Si no existe, se ofrece crearlo con su nombre, correo y teléfono de Luyoa:

![Cliente de Luyoa que no existe en Odoo: Crear y asignar](../static/description/04_cliente_nuevo.png)

Cuando el QR no es de una tarjeta de Luyoa, o falla la credencial o la
conexión, el popup explica el motivo y ofrece **Escanear de nuevo** o
**Reintentar**; no se asigna nadie:

![QR que no corresponde a un cliente de Luyoa](../static/description/05_qr_invalido.png)

El mismo flujo se abre desde la pantalla de pago:

![Pantalla de pago: logo de Luyoa sobre el teclado numérico](../static/description/06_boton_pago.png)

Con dos contactos de Odoo que matchean al mismo cliente, el popup lista los
candidatos y no deja asignar hasta resolverlo en *Contactos*. Un contacto
archivado, o uno ya vinculado a otra tarjeta de Luyoa, también bloquea la
asignación con el aviso correspondiente.
