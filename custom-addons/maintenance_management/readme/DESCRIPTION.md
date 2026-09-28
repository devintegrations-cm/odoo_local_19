Amplía la aplicación **Mantenimiento** de Odoo para llevar la trazabilidad de los equipos de las
tiendas (neveras, molinos, máquinas de espresso) y el control de cada intervención:

- **Equipos identificados**: cada equipo recibe un número de activo consecutivo (`ACT00001`…), un
  número de serie automático si no se digita uno, la tienda donde está y el cliente asociado (por
  ejemplo, un equipo en comodato).
- **Código QR y hoja de vida**: el QR del equipo abre una página del portal con su ficha técnica,
  indicadores (MTBF, MTTR, costo acumulado) y el historial de mantenimientos. Se imprime como
  etiqueta PDF para pegarla en el equipo.
- **Solicitudes más completas**: referencia consecutiva (`INC00001`…), condición del equipo,
  ubicación del mantenimiento, diagnóstico y un reporte imprimible *Orden de Mantenimiento*.
- **Checklist por categoría**: los ítems de una plantilla se copian a cada solicitud del equipo, y
  la solicitud no se puede cerrar mientras queden ítems sin marcar.
- **Costos**: líneas de costo por solicitud, cargadas a mano o traídas de una orden de compra, con
  el total por solicitud y el acumulado por equipo.

Existe para que el área de mantenimiento sepa qué equipo hay en cada tienda, qué se le hizo y
cuánto costó, y para que un técnico pueda consultar la historia del equipo escaneando su QR.
