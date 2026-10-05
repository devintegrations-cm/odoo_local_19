## Dependencias

- **Obligatorias** (Odoo 19 Community): `purchase`, `account`, `portal` y `mail`. Python: `lxml`,
  que ya viene en la imagen de Odoo.
- **Jorels** (`l10n_co_edi_jorels`), opcional y fuera de `depends`. Si está instalado, *Mi cuenta*
  pide al proveedor **tipo de régimen**, **tipo de responsabilidad**, **municipio** y **email de
  facturación**, todos obligatorios, y los guarda en la empresa. Además, la cuenta de cobro se
  emite como documento soporte electrónico al confirmar la factura. Sin Jorels esos campos no
  aparecen y nada falla.
- **pypdf**, opcional. Sirve para contar páginas y para detectar PDF con contraseña. Sin pypdf la
  contraseña se detecta por la marca `/Encrypt` del archivo: lo probamos en local, que no lo
  tiene, y un PDF cifrado fue rechazado. Odoo.sh trae pypdf. Está en `requirements.txt` del
  módulo; Odoo.sh solo lee el `requirements.txt` de la raíz del repositorio, así que la línea hay
  que copiarla allí. No está en `external_dependencies` a propósito: si faltara, bloquearía la
  instalación.

## Instalar

- Instalar **Portal de facturas de proveedor** desde *Aplicaciones* o con
  `-i supplier_invoice_portal`.
- El módulo crea los grupos **Validador** y **Responsable**, la secuencia de solicitudes, las
  plantillas de correo y el menú *Compras › Solicitudes de pago de proveedor*. También agrega la
  pestaña **Portal de proveedor** en la ficha del contacto y el bloque de Ajustes.

## Actualizar desde Odoo 17

Los scripts de `migrations/` se ejecutan solos al actualizar y se pueden correr más de una vez.

- **17.0.1.1.0**: una solicitud pasa de una orden (`purchase_id`) a varias (`purchase_ids`); se
  copia la orden a la tabla nueva y se recrea la plantilla de correo de recibido.
- **17.0.1.2.0**: los documentos del proveedor dejan de ser campos binarios y pasan a ser adjuntos
  del contacto. Se reusa el adjunto existente y se le pone su nombre de archivo.
- **19.0.1.2.0**: el pre-migrate pasa a `list` las vistas del módulo que sigan como `tree` y
  renombra el xmlid de la lista si el nuevo no existe. El post-migrate reactiva las vistas del
  módulo que el upgrade haya dejado inactivas; la que no valide queda inactiva y se avisa en el
  log.
