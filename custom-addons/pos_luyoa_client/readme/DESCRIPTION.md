Agrega al POS un botón **Cliente Luyoa** para identificar al cliente escaneando
el **QR de su tarjeta de lealtad digital** (Apple/Google Wallet) con la cámara
del dispositivo, consultarlo en la **API de Luyoa** y asignarlo a la orden para
facturarle.

El flujo completo desde cualquier botón (junto a *Nota*, en el submenú de los
3 puntos y en la pantalla de pago):

1. Se abre la cámara; el cajero apunta al QR de la tarjeta del cliente.
2. El sistema extrae el identificador del cliente de la URL de la tarjeta
   (`…/c/<customerUID>`) y consulta `GET /customer/:customerUID` en Luyoa con
   las credenciales del punto de venta.
3. El popup muestra los datos que devolvió Luyoa (nombre, correo, teléfono,
   sellos/saldo) y el contacto de Odoo que coincide, indicando por qué regla
   coincidió.
4. El cajero confirma. **Asignar cliente** si ya existe en Odoo, o **Crear y
   asignar** si no existe: se crea con los datos básicos de Luyoa (nombre,
   correo y teléfono) y se asigna a la orden.

El contacto de Odoo se busca, en este orden:

1. **Tarjeta ya vinculada**: el identificador de Luyoa guardado en el contacto
   (dato interno, no visible). Una tarjeta solo puede estar en un contacto.
2. **Correo** (sin distinguir mayúsculas).
3. **Nombre y teléfono juntos**.

Solo el nombre o solo el teléfono **no alcanzan** para asignar: dos personas
pueden compartirlos. La primera vez que el cliente se asigna o se crea, su
identificador de Luyoa queda guardado y los próximos escaneos lo encuentran
directo. Si el contacto encontrado ya está vinculado a **otra** tarjeta, no se
asigna ni se crea un duplicado: se pide revisarlo en Contactos.

5. Al asignarse se marca la orden para facturar.

Si el QR no corresponde a un cliente de Luyoa, hay dos contactos en Odoo que
coinciden (el popup lista los candidatos), el contacto está archivado, o falla
la credencial o la conexión, se muestra al cajero un mensaje claro con qué
hacer y **no se asigna nadie**.

Solo se identifica por QR, con la cámara del POS o de la tablet: no hay entrada
manual de identificadores. Las credenciales (Integration UID, Business UID y
token) solo las ve el responsable del POS y nunca llegan al navegador: la
consulta a Luyoa la hace el servidor.
