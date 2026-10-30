## Hallazgos abiertos de la prueba en navegador (Odoo 19, 2026-10-02)

- **Mi cuenta: el navegador avisa un campo a la vez.** Odoo 19 valida primero en el navegador
  (`reportValidity`): marca el primer campo obligatorio vacío y no muestra la lista de errores en
  rojo. La lista del servidor aparece solo en los errores que el navegador no detecta, como un
  archivo que no es PDF.

## Verificar en staging

- **Documento soporte electrónico**: confirmar una cuenta de cobro en el diario de documento
  soporte y comprobar que Jorels lo emite ante la DIAN. En local la factura queda *Registrada*
  con la advertencia "NO ha sido validado con la DIAN".
- **Municipios de Jorels**: el selector de *Mi cuenta* tiene unas 1.100 opciones; revisar que sea
  usable con los datos reales.
- **pypdf**: comprobar que esté instalado (Odoo.sh lo trae) y que la línea de
  `requirements.txt` esté en la raíz del repositorio. En local no está, y un PDF con contraseña se
  rechazó igual, por la marca `/Encrypt`.
- **Analítica en notas**: la orden de la prueba no tenía analítica. Falta ver un reembolso cuya
  orden sí la tenga.
- **Eventos RADIAN ante la DIAN real**: generar los eventos de una factura de proveedor con el
  token de Edipo y el TestSetId de staging (o en producción) y un firmante con documento, nombre,
  apellido y cargo reales. Confirmar que quien los genera no necesita el grupo de facturación
  electrónica de Jorels y que la DIAN acepta los tres.
- **Diario de RADIAN en producción**: marcar *Eventos RADIAN de receptor* solo en el diario de
  facturas electrónicas de proveedores (`CHECKLIST_PRODUCCION.md`).

## Pendiente de documentar

- **Pantalla de cierre de fin de mes** en el portal: solo se ve el último día hábil del mes,
  después de la hora de corte.
- **Icono** `static/description/icon.png` de 100×100: falta y necesita arte.
- **Validar con IA**: falta la captura del botón y de la acción de la lista; necesita el servicio de
  IA configurado.
- **Capturas del backend anteriores a 19.0.1.3.0** (lista, filtros, actividades, tomar revisión,
  validación, datos extraídos, factura, notas, documento soporte y rechazo): son de Odoo 19, pero
  todavía no muestran los botones *Validar con IA*, *Aprobar* y *Órdenes de compra* ni la pestaña
  *Orden de compra*. Hay que recapturarlas.

## Límites conocidos

- **Los eventos RADIAN no se generan al publicar**: hay que pulsar el botón en cada factura. Si un
  evento falla, el botón ya no vuelve a aparecer y los que faltan se crean desde *Eventos DIAN*.
- **Una orden de más de 12 meses no se radica por el portal**: la registra contabilidad en el
  backend.
- **La tolerancia porcentual (0,5 % por defecto) vale también para el precio unitario.** Es la
  regla de negocio vigente: un precio de 12.050 contra 12.000 (0,42 %) no deja la observación
  `PRICE_UNIT_MISMATCH`.
- **Con Jorels, los validadores necesitan *Facturación electrónica / Usuario*** para abrir y
  confirmar las facturas que crea el módulo. Ver *Permisos* en la configuración.

- La numeración `SPR/…` es interna. La factura usa la secuencia del diario y, en el documento
  soporte, la resolución DIAN.
- Una orden con una radicación en curso (no rechazada ni cancelada), o que ya tiene factura, no
  acepta otra factura. Lo que falte o sobre se radica como nota.
- OCR del PDF y emparejamiento por IA dependen de servicios externos; sin ellos, una factura sin
  XML se captura a mano.
