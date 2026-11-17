# Guía corta · Planta (tablero de solicitudes)

Para el equipo de la planta de tostión. Todo está en la aplicación **Planta** del menú principal.

## Solicitudes de tiendas (kanban)

- Cada tarjeta es una solicitud: tienda o cliente, canal, líneas de café por tipo, insumos, días esperando,
  avance del alistamiento y, si aplica, la alerta de café verde.
- Colores de etapa: **amarillo** Nueva, **azul** En alistamiento, **verde** Lista para despachar, **gris**
  Entregada, **rojo** Cancelada. Por defecto se ven las abiertas; el panel izquierdo filtra por planta, canal y
  etapa.
- Una solicitud nueva suena y avisa en Conversaciones; el tablero se actualiza solo, sin recargar.

## Chuleos y etapas

- Abre la solicitud › pestaña **Planta**. Cada línea × presentación (Paz 200 en grano, Paz Preparación 2.5, Vaso
  9 oz…) tiene un chuleo. Marcarlo es solo una guía: no cambia cantidades, movimientos ni inventario; queda
  quién lo marcó y cuándo.
- Con el primer chuleo la solicitud pasa a **En alistamiento**; con todos, a **Lista para despachar**. La barra de
  etapas permite fijar una etapa a mano; se respeta hasta que los chuleos cambien.
- Las solicitudes Listas y Despachadas salen del consolidado activo y se ven con los filtros «Listas para
  despachar» y «Despachadas».

## Consolidado (la hoja)

- Pestañas **PEDIDOS TIENDAS**, **OTROS PEDIDOS** y **ATTENZA**, con el selector «Por alistar / Listas / Despachadas
  / Todos». Las filas se arman solas por línea de café × gramos × molienda; las columnas son las tiendas (una
  tienda nueva aparece con su primera solicitud). Los kits de Attenza siguen con sus componentes.
- Columnas de la derecha: TOTAL BOLSAS, INVENTARIO (existencias en Odoo; el jefe puede digitar un valor), POR
  FABRICAR, TOSTAR y TOTAL NETO X TOSTAR por línea. Un inventario negativo en Odoo se muestra en **0** con el
  aviso «falta registrar producción/empaque»; en «Preparación» se ven granel y bolsas por separado.
- En cada celda hay un chuleo (☐ ◐ ☑) para marcar el alistamiento de esa fila para esa tienda.
- Debajo: **Insumos pedidos** (vasos, tapas, bolsas Kraft, papel, postales… en unidades, con stock y por comprar),
  **Café verde** (por línea: merma, kg a tostar, verde necesario, verde en planta, saldo; y por solicitud en
  orden de llegada: verde alcanza, amarillo por debajo del mínimo, rojo falta) e **Insumos por fabricar** (de las
  listas de materiales, si existen).
- «Descargar Excel» entrega las tres pestañas con los mismos bloques.

## Plan de tostión

- Por producto (las referencias equivalentes suman en su maestra) y planta: pedido, en planta, por fabricar,
  kg a tostar. El inventario negativo nunca suma. «Comparar con la hoja» muestra los totales de ambos y por qué
  pueden diferir.

## Remisión

- Botón de impresora en la tarjeta, «Remisión» en el formulario o varias desde la lista: una hoja carta con logo,
  número, fecha, referencia externa, venta, canal, tienda o cliente, el detalle completo (café e insumos, con
  kg solo para café), la dirección de entrega, observaciones y firmas. Una solicitud cancelada sale con la banda
  **CANCELADA**.

## Validar entrega

- «Validar entrega» en la tarjeta, la lista o el formulario. Si todo está chuleado (o las cantidades están
  puestas) y hay stock, valida directo y deja nota en el chatter; si faltan cantidades o stock, muestra qué se
  entregaría completo y qué falta, y pide confirmación. Al validar, la solicitud pasa a Entregada.

## Permisos

- El equipo de planta usa el grupo estándar **Inventario / Usuario**: tablero, hoja, plan, chuleos, remisión y
  validar entrega.
- La persona responsable usa **Inventario / Administrador** (y el derecho de Ajustes para la pantalla de
  configuración): canales, tipos y líneas, productos de planta, asistentes, filas y columnas, inventario
  digitado y ajustes. El módulo no crea grupos propios.

## Para el jefe de planta (Inventario / Administrador)

- **Productos de planta**: tipo, línea, gramos, molienda y «cuenta en consolidado» de cada producto; «Clasificar
  productos» propone y «Referencias duplicadas» agrupa las variantes (con código de barras, copias) en su
  maestra sin borrar nada.
- **Líneas de café**: orden, color, merma de tostión y mínimo de café verde. **Canales**: reglas por almacén,
  lista de precios, equipo, etiqueta o cliente. **Kits y excepciones**: filas manuales de la hoja. **Columnas de
  la hoja**: alias, orden y ocultar.
- **Ajustes › Planta**: almacenes de planta, personal que recibe las alertas, palabras del clasificador, gramaje
  de preparación, merma y mínimos por defecto, estado del análisis IA (la clave vive en el servidor).
