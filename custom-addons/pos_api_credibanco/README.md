# POS API Credibanco

Cobro con datáfono Credibanco desde el Punto de Venta de **Odoo 19**, a través de
un puente WebSocket que corre en el equipo de la caja.

El cobro está conectado al **framework de terminales de pago del núcleo**
(`use_payment_terminal = "credibanco"`), que es lo que aporta:

- Un único pago electrónico en curso por terminal (aviso del propio Odoo).
- Estados `waiting / retry / done / reversed` en la línea de pago.
- Botón de reversión sobre un pago ya aprobado: la acción del botón es del core,
  pero **lo que hace el módulo** es registrar una línea negativa compensatoria
  (ver *Anulaciones y devoluciones*).
- Validación automática del pedido cuando el terminal lo deja pagado
  (`auto_validate_terminal_payment`).

## Dónde vive el puente

- PC de desarrollo: `/media/desarrollo/Datos HDD1/odoocontaniers/api_credibanco`
- Docker Hub: `soportedevlibertario/api_credibanco`

## Configuración (método de pago)

En **Punto de Venta → Configuración → Métodos de pago**, crear/editar el método:

| Campo | Valor |
|---|---|
| **Integración** | Terminal (se pone solo al elegir Credibanco) |
| **Usar terminal de pago** | Credibanco |
| **Nombre de la terminal** | Prefijo con el que el bridge conoce al aparato (`tcpIp.ini`), p. ej. `dataf001` |
| **Host del datáfono** | IP/host visible **desde el navegador de la caja**, no desde el servidor |
| **Puerto** | `8080` por defecto |
| **Espera de respuesta (s)** | 100 por defecto: el bridge se rinde a los 90 s (`tef.ini`), así que el primero en cansarse debe ser el datáfono y su error debe verse como lo que es |

> **El número de caja (posición 42) no se configura.** Se compone al cobrar como
> `idDeSesión + idDelCajero`, concatenados sin separador, tal y como siempre lo
> envió la integración certificada de Odoo 17. Credibanco certifica esa
> serialización: un campo editable en el método de pago habría sido un punto de
> divergencia con lo que el adquirente espera ver. Lo que realmente viajó al
> aparato se guarda en `pos.payment.credibanco_cash_register` para que la
> anulación y la recuperación hagan eco del valor exacto (regla 2 de la interfaz
> del terminal). Si la concatenación pasa de los 10 caracteres del protocolo, el
> cobro se refusar con un mensaje claro: nunca se trunca, porque un número de
> caja recortado podría emparejarse con la venta de otra caja.

### Impuestos: por grupo, sin configuración

El módulo **no tiene campos de impuestos**. El servidor clasifica cada impuesto de
venta por el nombre de su **grupo** (`account.tax.group`), leído con el idioma
desactivado para que una traducción no cambie el resultado:

| Grupo | Va a |
|---|---|
| `IVA…` | posición 41 (IVA) |
| `INC…` (Impuesto Nacional al Consumo: el “IAC” del datáfono en restaurantes) | posición 82 |
| cualquier otro (`R ICA…`, `R IVA…`, `CREE`, `Bienes Cubiertos`…) | no viaja |
| importe negativo o `has_negative_factor` | no viaja, aunque su grupo sea IVA |

Esto sustituye a los ids fijos de la versión 17 (`9`, `10`, `61`), que en otra carta
significan otra cosa: en esta base de datos el id 61 era una **retención de ICA
negativa** y habría viajado como `-87`. Un pedido con impuestos positivos y ninguno
reconocido se refusar con el nombre de los grupos vistos, en lugar de mandarle ceros
al banco.

La propina se toma del producto de propina del propio punto de venta (campo estándar
`tip_product_id`), no de un campo de este módulo.

Los valores se envían al navegador por `_load_pos_data_fields()` en
`pos.payment.method`. En Odoo 19 el antiguo
`pos.session._loader_params_pos_payment_method` ya no existe: dejarlo puesto no
falla, simplemente el POS se queda sin host, puerto ni nombre.

## Protocolo (transcrito del bridge de Credibanco)

El bridge (`soportedevlibertario/api_credibanco`, fuera de este módulo a propósito) define
el contrato en sus recursos. Lo que el código de este módulo asume, literalmente:

| Operación | Campos que pide (`INPUT_FIELDS`) | Campos que devuelve (`OUTPUT_FIELDS`) |
|---|---|---|
| Compra `01` | 40, 41, **42**, **53**, 81, 82, 83, 84 | 0, 1, 40, 41, 42, **80**, 43, …, 53, …, 83, 85…88 |
| Anulación `02` | **42**, **43**, **53**, 83, 87, 88 | 0, 1, 40, 41, 80, 43, …, 89, 90 (**sin 42/53**) |
| Recuperación `00` | **42**, **53** | 0, 1, 40, 41, 80, 43, …, 89, 90 (**sin 42/53**) |

- **Límites** (`fields.ini`): 40/41/81/82/84 = 12 numérico, **42 = 10 alfanumérico**,
  **53 = 10 alfanumérico**, 43 = 6 numérico, **83 = 12 alfanumérico**. El bridge
  rellena cada campo a su longitud (`TefFields.formatField`), así que el POS **no
  rellena ni recorta nada**: si un valor pasa del límite, se refusar el cobro con
  nombre, valor y longitud en pantalla. Un campo mal formado llega del datáfono
  como `10 CAMPO_NO_CORRESPONDE`, que ahora se muestra como lo que es.
- **La respuesta es un objeto JSON** indexado por posición (el bridge serializa un
  `LinkedHashMap`), no un array. `parseAnswer` acepta las dos formas: asumir sólo una
  hacía que una respuesta válida se viera como "error de trama".
- **Timeout**: el bridge se cansa a los 90 s (`tef.ini: LONG_TIMEOUT`), por eso el
  timeout del POS es **100 s** por defecto: el primero en rendirse debe ser el
  datáfono, con su código, no el navegador.
- **Números de transacción**: un `ir.sequence` **por método de pago Credibanco**
  (el método es la caja configurada; ojo, `pos.payment.method` se enlaza a los PDV
  con many2many, así que "un método" no equivale necesariamente a "un aparato").
  Se reservan en bloques de 25 para poder cobrar sin conexión; agotado el bloque sin
  conexión, se refusar en vez de repetir un número. El relleno a 6 dígitos es
  presentación, no requisito del protocolo.
- **Un socket por navegador y una petición en vuelo**, y la respuesta sólo se acepta
  si trae el 42/53 (compra) o el 43 (anulación de una venta aprobada) de **esta**
  petición: el bridge actual responde con `broadcast()` a todas las sesiones
  conectadas, así que dos cajas sobre el mismo bridge pueden verse las respuestas.
  El arreglo de fondo es del bridge (responder a la `session` que envió); la
  correlación del POS es la segunda capa, y no puede cubrir anulación ni
  recuperación porque esas respuestas no repiten 42/53.

### Pendiente de confirmar con el datáfono real

1. En la respuesta de una compra **no existe el campo 81**: el importe que se guarda
   hoy es el 40 (igual que en 17). Falta confirmar si el 40 ya incluye la propina o
   si la propina viene en el **80**. Hasta confirmarlo con una compra real con
   propina, el código **no adivina** (ver `TODO` en `_applyApprovedSale`).
2. El relleno de la posición 42 (`sessionId + cashierId`) puede exceder los 10
   caracteres del protocolo con ids grandes. Hoy se refusar el cobro con mensaje
   claro (como en 17). Falta confirmar con Credibanco si tienen una convención
   alternativa para cajas con muchas sesiones/cajeros.
3. Los dos códigos de E/S del bridge (`MSG_CODE_1`, `MSG_CODE_2`): no se mapearon a
   propósito porque no está confirmado su código en la respuesta.

## Flujo de caja

1. Pantalla de pago → tocar el método Credibanco. Se crea la línea con el saldo y
   el cajero puede ajustarlo con el teclado (pago parcial).
2. Botón **Enviar** de la línea → popup de resumen con TOTAL / IVA / IAC /
   PROPINA para confirmar.
3. Se arma la trama (con checksum LRC) y se envía al `ws://host:puerto/ws`.
4. El cliente oprime el botón verde del datáfono. Si el terminal aprueba:
   - el importe de la línea pasa a ser lo que realmente cobró el terminal
     (`40 + 81`, incluye la propina que el cliente dejó en el dispositivo);
   - se guardan el número de aprobación y el identificador de transacción;
   - la respuesta completa queda almacenada y se materializa en filas legables
     en la ficha del pago.
5. Si el terminal no da respuesta final (`03`), el cobro queda **pendiente**: la
   interfaz ofrece recuperarlo (TECLA 3 → TECLA 9) y, si la página se recargó en
   medio, la recuperación se ofrece al volver a abrir la pantalla de pago.

**Nunca se reintenta a ciegas.** Ante ausencia de respuesta la venta queda
marcada como pendiente en la línea y el cajero recibe la instrucción de
recuperar, porque cobrar dos veces es peor que cobrar tarde.

## Anulaciones y devoluciones

- Cancelar una línea en curso (aún sin respuesta del aparato) envía la anulación
  (tipo `02`); si el terminal no la confirma, la línea sigue pendiente y el aviso
  lo dice. Ésa sí usa el flujo del núcleo.
- Anular un pago **aprobado** es deliberadamente distinto del botón nativo de
  Odoo 19:
  1. se envía la trama `02` con las posiciones guardadas en ese pago
     (`42/43/53/83/87/88`, eco de lo enviado, no recálculo);
  2. si el datáfono aprueba, se crea **una línea de pago negativa** en el mismo
     método con el importe exacto de la venta aprobada (neteo con el positivo
     que queda intacto);
  3. la línea positiva **no se toca**: conserva su importe y su número de
     aprobación original, y el botón de revertir desaparece (`can_be_reversed`),
     así que no puede anularse dos veces;
  4. la línea negativa carga las mismas referencias de la venta que anula
     (`credibanco_anulation_of` guarda el uuid de la original) y la respuesta
     del `02`.
- **Por qué no la reversión nativa de 19.** El core pone el pago aprobado a
  `amount 0` + estado `reversed`; en el cierre de sesión `_create_payment_moves`
  salta los importes a cero, así que **no queda ningún asiento que conciliar**.
  La línea negativa de 17 deja dos movimientos (`+X` y `-X`), que netean a 0
  pero son visibles en la contabilidad y en el extracto, y era lo que venía
  cuadrando la operación desde antes de la migración.
- La línea de anulación **no puede borrarse** con la papelera: no tiene estado
  electrónico y el botón aparecería, pero `PaymentScreen.deletePaymentLine` está
  parchado para refusar el borrado de una línea con `credibanco_anulation_of`.
  Borrarla dejaría la venta pagada en Odoo mientras el adquirente mantiene la
  devolución.
- Consecuencia a tener presente: tras una anulación el pedido queda **sin saldar**
  (la suma de pagos es 0 frente a un total de X), igual que en 17. El cajero debe
  volver a cobrarlo o descartar la orden.

> El `sendPaymentReversal` del terminal devuelve `false` **a propósito** incluso
> cuando la anulación fue aprobada: `true` haría que el core pusiera el importe a
> cero, y el cambio (línea creada, `+X` conservada) se perdería. Si alguien lo
> ve como un bug, leer `sendPaymentReversal` y esta sección antes de tocarlo.

## Datos que quedan en Odoo

| Campo | Uso |
|---|---|
| `pos.payment.credibanco_approval_number` | Código de autorización (posición 1) |
| `pos.payment.transaction_id` | Identificador de transacción (posición 2), derivado de la respuesta guardada |
| `pos.payment.credibanco_response` | Respuesta cruda en JSON posición → valor |
| `pos.payment.credibanco_pending_sale` | **Posiciones** de la venta enviada sin respuesta final (base de la recuperación) |
| `pos.payment.credibanco_cash_register` | Valor enviado en la posición 42 |
| `pos.payment.credibanco_number_transaction` | Valor enviado en la posición 53 |
| `pos.payment.credibanco_operator` | Valor enviado en la posición 83 |
| `pos.payment.credibanco_anulation_of` | uuid de la línea que esta anulación compensa (presente sólo en líneas de anulación) |
| `pos.payment.credibanco` (O2M) | Desglose legible, generado desde la respuesta; posiciones sin etiqueta se ignoran |
| wizard `credibanco.extra.info.wizard` | Alta manual de un concepto por un responsable |

Si `pos_voucher_num` está instalado, el número de aprobación se copia también a
su campo `vaucher_num` (que es lo que muestran sus vistas contables). La
integración es por valor, no por dependencia del manifest: por eso este módulo se
puede instalar sin `pos_voucher_num`.

## Probar sin datáfono

```bash
python3 tools/credibanco_fake_terminal.py --port 8080 --name dataf001 --outcome approved
```

Simulador con sólo la librería estándar (handshake, tramas enmascaradas, validación
de LRC). Resultado configurable: `approved`, `rejected`, `no-answer` (fuerza el
timeout y la recuperación), `recover-then` (primera venta queda `03` y la
recuperación la aprueba), `bad-lrc`.

```bash
python3 tools/credibanco_fake_terminal.py --selftest   # coherencia de tramas y LRC
```

Para usarlo: configurar el método de pago con `Host del datáfono = 127.0.0.1` (o
la IP del equipo que lo corre) y el mismo nombre.

## Estructura

| Archivo | Rol |
|---|---|
| `static/src/app/utils/payment/credibanco_protocol.js` | Trama, checksum LRC, parseo de respuesta, mensajes por código. Puro, sin OWL |
| `static/src/app/utils/payment/credibanco_transport.js` | WebSocket con timeout y abort |
| `static/src/app/utils/payment/credibanco_terminal.js` | `PaymentInterface` + `register_payment_method("credibanco", ...)`; compone el 42 y registra la anulación como línea negativa |
| `static/src/app/components/popups/text_list_popup/` | Popup de confirmación de valores |
| `static/src/app/screens/payment_screen/payment_screen.js` | Ofrece recuperar la venta pendiente al abrir la pantalla y refusar el borrado de líneas de anulación |
| `models/pos_payment_methods.py` | Campos, selección de terminal, restricciones, carga al POS |
| `models/pos_payment.py`, `models/pos_payment_credibanco.py` | Persistencia y materialización de la respuesta |
| `migrations/19.0.1.0.0/pre-migration.py` | Convierte el antiguo `enable_pos_credibanco` en la selección de terminal |
| `tools/credibanco_fake_terminal.py` | Simulador de datáfono (utilidad de desarrollo, no la importa Odoo) |
| `tests/test_pos_payment_method.py` | 15 pruebas de configuración y persistencia |

## Pendiente

- Validar el protocolo con el datáfono físico en cada tienda antes de habilitar el
  método (número de dígitos de cada campo, posición de la referencia).
- Confirmar en producción que las tramas de anulación usan las posiciones
  correctas (`42, 43, 53, 83, 87, 88`) con el modelo de terminal real.
- Revisar el nombre del cajero que se envía (posición 83): hoy viaja el primer
  token del nombre; falta confirmar qué espera el banco para la conciliación.
- `doc/historial_17/` guarda las notas de la migración anterior y de
  `TEXT_LIST_POPUP`; se pueden borrar cuando este módulo esté comiteado.

## Licencia

LGPL-3

## Autor

Libertario Coffee Roasters
