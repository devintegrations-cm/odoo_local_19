## Límites conocidos

- **Los datos de la DIAN no son del cliente que está en la caja.** El servicio de adquirentes
  devuelve lo que registraron otros emisores. El cajero tiene que confirmar nombre y correo con el
  cliente; el popup no lo puede verificar.
- **Guardar orden oculto en todas las cajas.** El botón nativo *Guardar orden* (`fa-upload`) se
  quita de la pantalla de producto y de la barra de acciones aunque la caja tenga desmarcado
  *Factura electrónica: validación DIAN del cliente*.
- **Sin desasignar cliente con «Ocultar botón de cliente».** Con ese ajuste y la validación DIAN
  marcados, el POS no ofrece forma de quitar el cliente de la orden: solo se puede reemplazar por
  otro validado o descartar la orden.
- **Otro tipo de documento muestra los datos de la DIAN.** En el aviso *Existe en Odoo como …*, el
  popup igual muestra nombre y correo que la DIAN devolvió para el número con el tipo consultado,
  que puede ser una persona distinta del contacto de Odoo. Evaluar ocultar ese bloque en
  `type_mismatch`.
- **Pantallas chicas:** con un cliente asignado, el botón **FE** de la barra de acciones queda
  reducido al ícono y "…".
- Cada validación de un cliente existente vuelve a consultar a la DIAN (por diseño del
  requerimiento). Si el volumen de cajas lo pide, evaluar una caché corta por documento.
- El buscador de existentes compara las variantes canónica `NIT-DV`, sin DV y sin guion, pero no NIT
  guardados con puntos (`900.123.456-8`). Si aparecen en producción, agregar esa variante.

## Mejoras pendientes (no bloquean)

- **Timeout de Edipo:** hoy es de 20 s. Pasarlo a 5 s de conexión y 10 s de lectura
  (`timeout=(5, 10)`) para que la caja no quede esperando.
- **Crear sin municipio:** bloquear *Crear y asignar* si la compañía no tiene municipio. Hoy el
  cliente nuevo se crea con el municipio vacío.
- **Teclado:** que Enter dispare *Validar en DIAN* y que el foco inicial quede en el número.
- **Modificar datos:** limpiar el correo digitado al volver al formulario, para que no quede
  arrastrado a otro documento.
- **Índice sobre `edi_sanitize_vat`:** decidir según el volumen de contactos en producción. La
  búsqueda de existentes filtra por ese campo en cada consulta.
- **Concurrencia:** dos cajas que crean el mismo cliente al mismo tiempo pueden dejar un duplicado,
  que la próxima consulta informará como *Hay más de un contacto con este documento*.
- **Rotación del token Edipo:** el `api_key` quedó expuesto en sesiones de trabajo previas.
  Rotarlo antes de producción (decisión del equipo).
- **Mapeo de más campos de Edipo:** si `/acquirer` devuelve municipio, régimen o responsabilidad
  del adquirente, usarlos en lugar de los valores por defecto.
- Ícono del módulo (`static/description/icon.png`): falta y requiere arte.
