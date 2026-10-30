## Ajustes del módulo

*Compras › Configuración › Ajustes*, bloque **Portal de facturas de proveedor**. Ese menú es de
*Administración / Ajustes*: un *Compras: Administrador* sin ese permiso no lo ve.

![Compras › Configuración › Ajustes › Portal de facturas de proveedor: diarios, producto de flete, NIT, verificación de emisor y receptor, cierre de fin de mes y grupo validador](../static/description/36_ajustes_modulo.png)


- **Diario por defecto** (`spr.default_journal_id`): diario de compras donde se crean las
  facturas borrador.
- **Diario de documento soporte** (`spr.support_journal_id`): diario con la resolución DIAN de
  documento soporte. Ahí se registran las cuentas de cobro. Sin este diario, *Crear factura* no
  funciona para una cuenta de cobro.
- **Producto de flete** (`spr.freight_product_id`): producto de servicio para los fletes que la
  factura cobra y la orden no tiene. Sin él, *Crear factura* no funciona para una factura con
  flete.
- **Tope del flete (%)** (`spr.freight_max_pct`): aparece con el producto de flete. Si los fletes de
  la factura superan ese porcentaje del subtotal de la mercancía, la solicitud queda *Con
  observaciones*. Se comparan las dos bases, sin IVA. Por defecto 10 %; 0 = sin tope.
- **Tolerancia de montos**: diferencia admitida entre la factura y lo pendiente de la orden. Pasa
  si está dentro del porcentaje **o** del monto absoluto. Por defecto 0,5 % o 1.000. La misma
  tolerancia porcentual vale para el **precio unitario** de cada línea: es la regla de negocio
  vigente. Un precio de 12.050 contra 12.000 de la orden (0,42 %) pasa sin observación.
- **NIT de la compañía**: dejarlo vacío si el NIT está bien puesto en la ficha de la compañía.
- **Verificar emisor y receptor**: activo por defecto. Compara el NIT del emisor con el proveedor
  y el del adquiriente con la compañía.
- **Cierre de radicación de fin de mes**: activo por defecto, con **hora de corte** a las 12:00.
  El último día hábil del mes, desde esa hora, el portal no recibe documentos hasta el día 1. Tiene
  en cuenta los festivos de Colombia.
- **Grupo validador**: el grupo cuyos usuarios reciben la actividad de revisión.
- **IVA como producto**: apagado por defecto. Activo, las líneas van con el impuesto exento y el
  IVA entra como una línea del producto de mayor valor IVA.
- **Verificar el CUFE en el catálogo DIAN**: apagado por defecto, porque la DIAN pide captcha.
- **OCR del PDF**, **Emparejamiento por IA** y **Conexión de prueba por CLI**: servicios externos
  opcionales. Ver `README.md` del módulo.

El **tope del flete** aparece debajo del producto de flete, solo cuando hay producto elegido. Con
el tope en 10 %, un flete de 15.000 sobre una mercancía de 200.000 (7,5 %) pasa; con el tope en
5 %, la misma factura queda *Con observaciones*.

![Compras › Configuración › Ajustes › Portal de facturas de proveedor: producto de flete y Tope del flete (%)](../static/description/39_ajustes_tope_flete.png)

## Diario para los eventos RADIAN

Solo con la facturación electrónica de Jorels instalada. En *Facturación › Configuración ›
Diarios* (*Contabilidad › Configuración › Diarios* con la contabilidad completa), abrir el diario de
compras de las facturas electrónicas de proveedores y marcar **Eventos RADIAN de receptor**, en la
pestaña *Asientos contables*. La casilla la ve el administrador de contabilidad.

![Facturación › Configuración › Diarios › Facturas de Proveedores: casilla Eventos RADIAN de receptor](../static/description/38_diario_eventos_radian.png)

- Las facturas publicadas en ese diario muestran el botón **Generar eventos RADIAN**. En un diario
  sin la casilla el botón no aparece.
- Si hay varios diarios de compras (gastos, importaciones…), se marca solo el de las facturas
  electrónicas. No se marca por nombre ni se deduce: es un paso de la puesta en producción.
- No se puede marcar en un diario que no sea de compras ni en el de documento soporte: Odoo no deja
  guardar. Una factura en un diario con resolución de documento soporte nunca muestra el botón,
  aunque el diario esté marcado.
- La compañía necesita la facturación electrónica activa, el token de Edipo y, en ambiente de
  pruebas, el TestSetId (*Ajustes › Facturación electrónica*).

### Datos del firmante

Los eventos salen firmados por quien pulsa el botón. En su contacto (*Ajustes › Usuarios*, abrir
el usuario y su contacto, o *Contactos*) tienen que estar:

- **Puesto de trabajo**: es el cargo del firmante.
- **Número de identificación**: tipo y número reales. El 222222222222 que Jorels pone a los
  usuarios nuevos no sirve.
- **Primer nombre** y **Apellido**, en la pestaña *Información postal*.

![Contacto del usuario firmante: puesto de trabajo, tipo y número de identificación, primer nombre y apellido](../static/description/40_firmante_radian.png)

Si falta alguno, el botón no envía nada y muestra la lista de lo que falta (ver *Eventos RADIAN* en
el uso).

## Habilitar un proveedor

Se hace en la ficha de la **empresa**, o de la persona natural que no pertenece a ninguna empresa.
La ficha debe tener el NIT. En un contacto hijo la pestaña no aparece: ese contacto radica a
nombre de su empresa. La pestaña la ven solo los usuarios del grupo **Responsable**.

![Contactos › proveedor › Portal de proveedor: casillas, documentos y botón del instructivo](../static/description/01_proveedor_habilitado.png)

- **Puede radicar facturas en el portal** (`portal_invoice_enabled`). Sin esta casilla, el
  proveedor entra al portal pero no ve *Radicar facturas*.
- **No obligado a facturar (documento soporte)** (`spr_support_document`). Marcarla solo para
  quien radica cuentas de cobro: le agrega el tipo *Cuenta de cobro* y no le pide XML.
- **Documentos del proveedor**: cámara de comercio, RUT y certificación bancaria. Normalmente los
  carga el proveedor desde *Mi cuenta*. Desde el backend se adjunta el PDF en el chatter y se
  elige en el campo. Debajo se ve la vista previa de cada uno.
- La pestaña **Facturación electrónica** (Jorels) muestra los datos que el proveedor completa en
  *Mi cuenta*.

![Contacto › Facturación electrónica: régimen, responsabilidad, municipio y email que completa el proveedor](../static/description/04_datos_jorels.png)

## Dar acceso al portal

- En la empresa, pestaña *Contactos*, crear un contacto hijo con correo para cada persona que va a
  radicar. Luego, en ese contacto, ir a *Acción › Otorgar acceso al portal*. Es el asistente
  estándar de Odoo y requiere permisos de administración: un *Compras: Administrador* recibe
  "No tiene suficientes permisos".

![Contacto › Acción › Otorgar acceso al portal: asistente estándar de Odoo para dar acceso al contacto que va a radicar](../static/description/37_otorgar_acceso_portal.png)

- Odoo envía la invitación y el usuario define su clave. Si hay varias bases sin `dbfilter`, el
  enlace hay que abrirlo después de entrar a `/web/login?db=<base>`.

![Invitación al portal que recibe el contacto](../static/description/03_invitacion_portal.png)

- Pulsar **Enviar instructivo del portal** en la ficha de la empresa, pestaña *Portal de
  proveedor*. Se abre el correo con el paso a paso y **dos PDF ya adjuntos**: el instructivo
  generado con el nombre y el NIT de la compañía, la hora de corte y, para quien no está obligado a
  facturar, la cuenta de cobro en lugar del XML; y la guía del portal. Solo hay que revisar los
  destinatarios y enviar.

![Contacto › Portal de proveedor › Enviar instructivo del portal: destinatario, los dos PDF adjuntos y Enviar](../static/description/02_instructivo.png)

## Permisos

- **Validador**: ve las solicitudes, valida, empareja líneas a mano, toma la revisión y crea la
  factura borrador.
- **Responsable**: lo anterior, más rechazar, aprobar a mano una solicitud con observaciones,
  aceptar notas débito, devolver a borrador, cancelar y habilitar proveedores. *Compras:
  Administrador* es Responsable sin asignarlo.
- **Generar eventos RADIAN**: cualquier usuario de facturación que pueda publicar facturas, aunque
  no tenga el grupo de facturación electrónica de Jorels.
- Los botones y pestañas del portal en contactos, órdenes y facturas (*Solicitudes*, *Portal de
  proveedor*, documentos) solo los ven Validador y Responsable. Un usuario sin esos grupos, como un
  cajero del punto de venta, lee el contacto sin errores de acceso.
- Los grupos se asignan en la ficha del usuario, sección *Portal de facturas de proveedor*.
- **Requisito con Jorels: los validadores deben tener *Facturación electrónica / Usuario*.** El
  personal de contabilidad y compras que revisa solicitudes tiene ese acceso. Sin él, *Crear
  factura* sí crea el borrador, pero al abrirlo Odoo muestra "Error de acceso … Eventos del
  Radian", y tampoco se puede confirmar.
- El proveedor (usuario del portal) solo ve las solicitudes de su empresa.
