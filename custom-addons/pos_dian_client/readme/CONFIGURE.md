## Requisitos

- Módulo `l10n_co_edi_jorels` instalado, con la **facturación electrónica habilitada** en la
  compañía. Si no lo está, el popup responde "La facturación electrónica no está habilitada en esta
  compañía".
- **Token Edipo** en la compañía: *Ajustes › Facturación electrónica colombiana*, campo
  **Edipo api key** (`api_key`). Es el mismo que usa la instancia para facturar. Sin él, el popup
  responde "No está configurado el token de Edipo"; si el token no es válido, avisa que no está
  autorizado.
- **Municipio de la compañía** (campo *Municipality* de facturación electrónica). Los clientes nuevos
  y los existentes que no tienen municipio toman el de la compañía. Si la compañía tampoco lo tiene,
  el cliente existente se informa como incompleto y no se asigna, y el cliente nuevo **se crea sin
  municipio** (ver *Known issues / Roadmap*).
- **Permisos del cajero:** usuario del Punto de Venta. Para *Crear y asignar* o *Asignar y
  actualizar* necesita además permiso de creación y edición de contactos; sin él, el popup lo
  informa y no escribe nada.

## Activar el botón en cada caja

En *Punto de Venta › Configuración › Puntos de venta*, abrir la caja y, en la pestaña
**Configuración**, marcar **Factura electrónica: validación DIAN del cliente**. El ajuste viene
marcado de forma predeterminada; desmarcarlo oculta los botones *Factura electrónica* en esa caja.
El botón *Guardar orden* queda oculto igual, con el ajuste marcado o no.

A continuación está **Ocultar botón de cliente** (viene desmarcado). Al marcarlo, el botón
nativo *Cliente* desaparece de la pantalla de producto (escritorio y móvil) y de la pantalla de
pago, donde *Factura electrónica* toma su lugar junto a *Recibo/Factura*. El cliente se gestiona entonces solo con
*Factura electrónica*, que muestra debajo el nombre del cliente ya asignado.

**Solo tiene efecto si «Factura electrónica: validación DIAN del cliente» también está marcado.**
Si se desmarca la validación DIAN, el botón *Cliente* vuelve a aparecer aunque *Ocultar botón de
cliente* siga marcado.

**Atención:** con esta opción activa no hay forma de desasignar un cliente desde la interfaz del
POS.

![Punto de Venta › Configuración › Puntos de venta › (caja) › Configuración: 1. «Factura electrónica: validación DIAN del cliente»; 2. «Ocultar botón de cliente», que solo aplica con el 1 marcado](../static/description/01_configuracion.png)

La caja puede tener una sesión abierta mientras se cambia el ajuste. El POS lo toma la próxima vez
que se carga.

## Opcional

La URL del servicio se cambia con el parámetro de sistema `jorels.edipo.api_url` (por defecto
`https://edipo.jorels.com`).
