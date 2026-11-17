# Soporte de operaciones de inventario (`stock_operation_support`)

Permite adjuntar a una operacion de inventario el **comprobante de entrega**
—la remision firmada a mano— digitalizarlo con IA de vision y verificar que lo
que dice el papel corresponde a lo que dice el sistema.

- **Odoo:** 19.0 (port mecanico; ver limitaciones en `readme/ROADMAP.md`)
- **Dependencias Odoo:** `stock`, `mail`
- **Dependencias Python:** ninguna propia (`requests` ya viene en Odoo)

El modulo es independiente de `supplier_invoice_portal`: no lo importa ni lo
necesita. Comparte con el las mismas ideas de diseno y el mismo puente local de
CLI para pruebas, pero se instala y se despliega solo.

## Que hace

En cualquier operacion de inventario aparece el boton **Agregar soporte de
operacion**. Desde ahi se adjunta la foto de la remision y se valida:

```
Operacion de inventario (stock.picking)
   |  boton "Agregar soporte de operacion"
   v
stock.operation.support  --> pipeline de validacion
      |- 1. IA de vision: la foto se transcribe a JSON
      |- 2. Emparejamiento de lineas (codigo -> descripcion)
      |- 3. Reglas duras (cantidades, partes, firmas, duplicados)
      \- 4. Veredicto + JSON de resultados + aviso en el chatter de la operacion
```

Principios que no se negocian:

1. **La IA digitaliza y propone; las reglas deciden.** La IA transcribe la foto
   y, cuando las unidades no coinciden, propone a que producto va cada linea y
   cuanto vale la unidad del papel. Si la entrega esta bien lo deciden reglas
   deterministas, para que una diferencia de inventario se pueda explicar sin
   depender de un modelo.
2. **La respuesta de la IA nunca crea ni modifica registros.** Se guarda como
   JSON, se vuelca a campos editables y pasa por las reglas.
3. **Nada de esto bloquea el almacen.** Un soporte con errores no impide
   validar la operacion. Lo unico que el modulo hace por su cuenta es validar
   una recepcion cuyo soporte **cuadra exacto** (ver *Validacion automatica*).
4. **Cualquier fallo del servicio es degradado, no fatal.** Si la IA no
   responde, el soporte queda en captura manual y la operacion sigue.

## Instalacion

Copiar el modulo a la carpeta de addons e instalarlo desde *Aplicaciones*. No
requiere paquetes de sistema ni dependencias Python nuevas.

```bash
cd odoodkr17
docker run --rm --network odoodkr17_webnet \
  -v "$PWD/config:/etc/odoo" \
  -v "$PWD/addons:/mnt/extra-addons/custom-addons" \
  odoo:17.0 odoo -c /etc/odoo/odoo.conf -d spr_check \
  -i stock_operation_support --stop-after-init --without-demo=all
```

## El comprobante es un adjunto de la operacion

Las fotos de los soportes ya se adjuntan a las recepciones (en staging hay mas
de 16 mil). Por eso el soporte no guarda su propio archivo: el campo
**Comprobante** (`attachment_id`) apunta a un adjunto de la operacion.

- *Agregar soporte de operacion* propone la foto o PDF mas reciente de la
  operacion; se puede elegir otro de sus adjuntos.
- Si se sube un archivo desde el soporte (campo *Archivo*), queda adjunto a la
  operacion y el Comprobante apunta a el. Subir el mismo archivo otra vez no
  cambia nada; subir otro distinto borra lo leido del anterior.
- No se acepta un adjunto de otra operacion.
- La migracion `17.0.1.4.0` paso los archivos que los soportes guardaban por su
  cuenta a la operacion correspondiente, sin copiarlos.

## Configuracion

Bloque *Soporte de operaciones* dentro de *Inventario -> Configuracion ->
Ajustes*.

| Ajuste | Parametro | Por defecto |
|---|---|---|
| Tolerancia de cantidad (%) | `sos.qty_tolerance_pct` | 0 |
| Tolerancia de cantidad (unidades) | `sos.qty_tolerance_abs` | 0 |
| Verificar quien entrega y quien recibe | `sos.party_check` | activado |
| NIT de la compania | `sos.company_nit` | el de la compania activa |
| Exigir constancia de recibido | `sos.signature_check` | activado |
| Validar la recepcion si el soporte cuadra exacto | `sos.auto_validate` | activado |
| Leer el comprobante con IA de vision | `sos.vision_enabled` | desactivado |
| Proveedor / URL / API key / modelo / timeout | `sos.vision_*` | `anthropic` / `claude-opus-5-5` / 90 s |
| Conexion de prueba por CLI local | `sos.vision_cli_*` | desactivado / `claude-empresa` / 240 s |

Las dos tolerancias se combinan con el criterio mas permisivo: pasa si la
diferencia esta dentro del porcentaje **o** dentro de las unidades. En 0 y 0 no
se admite ninguna diferencia, que es lo razonable en inventario.

Las API keys se guardan en `ir.config_parameter`, se muestran enmascaradas y
nunca se escriben en el log.

> Los cuatro Boolean de Ajustes se guardan a mano como `"True"`/`"False"` en vez
> de usar `config_parameter`. Odoo borra el parametro cuando un Boolean de
> Ajustes queda en False, y entonces "ausente" se confundiria con "activado" —
> el mismo problema que ya se corrigio en `supplier_invoice_portal`.

## Quien entrega y quien recibe

Las dos partes del documento se deducen del tipo de operacion, no se preguntan:

| Tipo de operacion | Entrega | Recibe |
|---|---|---|
| Recepcion (`incoming`) | el contacto de la operacion (proveedor) | la compania |
| Entrega (`outgoing`) | la compania | el contacto de la operacion (cliente) |
| Interna (`internal`) | la compania | la compania |

El NIT se compara **ignorando el formato y el digito de verificacion**
(`services/vision_adapter.same_nit`): el comprobante suele traerlo sin DV y
`res.partner.vat` lo guarda pegado ('900123456-7'). Como los NIT no tienen largo
fijo (8 o 9 digitos de persona juridica, cedulas de 6 a 10), **no se recorta a 9
a ciegas**: son iguales si coinciden digito a digito o si uno es el otro mas
exactamente un digito al final. Es el mismo criterio de
`supplier_invoice_portal` (su DECISIONS #3), a proposito: dos modulos que
discrepen sobre si dos NIT son el mismo serian peor que cualquiera de los dos
criterios por separado.

La razon social se compara de forma suave (solapamiento de palabras) porque en
las remisiones se abrevia mucho; una diferencia grande es observacion, nunca
error.

Antes de comparar se descarta la **forma societaria** (`SAS`, `S.A.S.`, `LTDA`,
`S.A.`, `& CIA`...) y los tokens de una sola letra
(`services/line_matcher.similarity_company`). Sin eso, *CAFES DEL SUR S.A.S.*
y *CAFES DEL SUR SAS* —la misma empresa— se parecian menos que dos empresas
distintas, porque los puntos de `S.A.S.` dejan `s a s` suelto al normalizar.
Salio en la primera prueba de punta a punta y marcaba observacion en cada
soporte.

## Reglas de validacion

Corren todas en cada validacion (`services/support_rules.py`). El veredicto es
*No paso las validaciones* si hay algun **error**, *Con observaciones* si solo
hay **observaciones**, *Aprobado* si todo esta correcto.

| Codigo | Nivel | Que revisa |
|---|---|---|
| `QTY_OVER_OPERATION` | error | El soporte respalda **mas** cantidad que la operacion |
| `QTY_UNDER_OPERATION` | error | El soporte respalda **menos** cantidad que la operacion |
| `QTY_MISSING_IN_DOCUMENT` | observacion | La operacion tiene un movimiento que el soporte no menciona |
| `SIGNATURE_RECEIVER_MISSING` | error / observacion | No hay constancia de recibido; en una factura es observacion (ver *Que firmas se exigen*) |
| `SIGNATURE_*_NOT_REQUIRED` | correcto | Ese tipo de documento no la exige |
| `SERVICE_LINES` | correcto | Lineas que no son mercancia (envio, domicilio, bolsa): no se comparan |
| `SIGNATURE_*_UNCLEAR` | observacion | Parece haber firma pero no se ve con claridad |
| `SENDER_NIT` / `RECEIVER_NIT` | error | El NIT del documento no es el de la parte que corresponde (en un tiquete de caja, el de quien recibe es observacion) |
| `SENDER_NAME` / `RECEIVER_NAME` | observacion | La razon social no se parece a la registrada (con el NIT correcto, solo si no comparte nada) |
| `*_NIT_MISSING` / `*_NIT_UNKNOWN` | observacion | No se pudo leer el NIT, o no hay NIT registrado con que comparar |
| `LINES_MATCHED` | observacion | Hay lineas del soporte sin movimiento asociado |
| `UOM_UNKNOWN` | observacion | Ni Odoo ni la IA saben pasar la unidad del papel a la del movimiento; esa linea no se compara |
| `UOM_CONVERSION_UNVERIFIED` | observacion | La IA propuso un factor que no esta escrito en la linea ni en un empaque del producto |
| `UOM_CONVERTED` / `LINE_MATCHED_BY_AI` | correcto | Como se convirtio la unidad, o que linea asocio la IA y por que |
| `NO_LINES` | error | El soporte no tiene ninguna linea |
| `REMISSION_DUPLICATE` | error | Ese numero de remision, del mismo NIT de quien entrega, ya respalda otra operacion |
| `REMISSION_REF_MISSING` | observacion | No se pudo leer el numero de la remision |
| `PICKING_CANCELLED` | error | La operacion esta cancelada |
| `PICKING_DRAFT` | observacion | La operacion esta en borrador: las cantidades pueden cambiar |
| `LOW_LEGIBILITY` | observacion | La foto quedo poco legible (confianza < 0.5) |
| `MANUAL_CAPTURE_REQUIRED` | observacion | Sin lectura ni captura: las reglas de cantidades y firmas no corren |
| `MANUAL_CAPTURE` | correcto | No hubo lectura, pero se capturo a mano y las reglas corrieron sobre eso |
| `DOCUMENT_WARNING` | observacion | Lo que anoto la IA al leer (cantidad tachada, dato ilegible) |
| `RULE_CRASHED` | error | Una regla revento; el resto siguio corriendo |

### Que firmas se exigen

Prueba con 14 fotos reales de staging (2026-10-07): los soportes de la compania
casi nunca son remisiones. Son facturas electronicas y tiquetes de caja de
supermercado; el "recibido" es una anotacion a mano en cualquier parte del
papel (orden de compra, nombre, fecha: "P44358 / Antonio Valencia / 28-09") y
ningun proveedor firma. La IA clasifica el documento (`document_type`, editable)
y la regla depende de eso:

| Tipo de documento | Constancia de recibido | Firma de quien entrega |
|---|---|---|
| Remision | exigida (error si falta) | no se exige |
| Factura electronica | exigida, como observacion si falta | no se exige |
| Otro o sin tipo | exigida (error si falta) | no se exige |
| Tiquete de caja (POS) | no se exige: es compra en punto de venta | no se exige |

La constancia de recibido es cualquier marca manuscrita: firma, nombre, fecha
o numero de orden de compra, este o no en una casilla. Lo impreso no cuenta.

### Contra que cantidad se compara

No es lo mismo discutir contra lo pedido que contra lo recibido, asi que la
regla dice cual uso:

- Si el movimiento ya se marco como hecho, o la operacion esta validada, se
  compara contra la cantidad **registrada** (`move.quantity`): es lo que
  realmente entro.
- Si todavia no, contra la cantidad **esperada** (`move.product_uom_qty`).

Varias lineas del papel pueden apuntar al mismo movimiento (entregas partidas en
la remision): se **suman** antes de comparar. Lo que se suma es la cantidad ya
pasada a la unidad del movimiento (ver *Unidades distintas*).

### Emparejamiento de lineas

Primero lo determinista, despues la IA solo para lo que quede:

1. Lo que se emparejo a mano (`match_method = manual`) no se toca, ni siquiera
   al revalidar. Se reconoce **por contenido** (codigo, descripcion, cantidad),
   no por posicion: reordenar el documento no mueve el emparejamiento.
2. **Por codigo**: referencia interna, codigo de barras y codigo del proveedor
   en *Compra -> Proveedores* del producto.
3. **Por descripcion**: solapamiento de palabras, sin tildes ni signos, o que la
   descripcion contenga el nombre completo del producto. Por debajo de 0.6 no
   se empareja por esta via.
4. **Por IA**: las lineas que siguen sin producto y las que estan en una unidad
   que Odoo no sabe convertir van a una llamada de solo texto (mas barata que
   la de la foto). La IA solo asocia lineas sin producto con confianza de 0.6
   o mas, y no cambia lo que ya se emparejo por codigo o descripcion. Lo que
   hizo la IA no se recalcula al revalidar; si con *Volver a leer la foto*.

### Unidades distintas

Cada linea lleva un **factor de unidad**: cuantas unidades del movimiento vale
una unidad del papel. La cantidad que se compara es *cantidad x factor*.

| Caso | Quien lo resuelve | Estado de la conversion |
|---|---|---|
| Sin unidad en el papel | se asume la del movimiento, solo si cuenta en Unidades | Misma unidad |
| `UND`, `KG`, `GR`, `LT`, `DOCENA`... de la misma familia que el movimiento (en Odoo 19: misma unidad de referencia, `_has_common_reference`) | Odoo (`uom._compute_quantity`), sin IA | Convertida por Odoo |
| `CAJA`, `BULTO`, `PACA`, o una unidad de otra familia | la IA propone el factor | con respaldo / sin respaldo |
| La persona escribe el factor en la linea | a mano; se conserva al revalidar y al volver a leer | Factor puesto a mano |

Dos protecciones, porque un factor equivocado mueve inventario:

- **A la IA no se le mandan las cantidades de la operacion.** Ve las lineas del
  papel y los productos con su unidad y sus empaques, pero no cuanto se pidio.
  Si lo viera, podria proponer justo el factor que hace cuadrar las cifras.
- **El factor tiene que estar respaldado**: escrito en la linea ("caja x 24",
  "bulto 25 kg") o en un empaque registrado del producto (en Odoo 19 los
  empaques son unidades de medida del producto: campo *Empaques*, `uom_ids`,
  de la misma familia que su unidad). Si no, la linea queda *sin respaldo*, el soporte en
  *Con observaciones* y la recepcion no se valida sola hasta que una persona
  confirme o corrija el factor.

La **libra** no se convierte sola a proposito: en Colombia suele ser de 500 g
y la `lb` de Odoo es de 453,6 g. Si los proveedores la usan, conviene crear la
unidad propia en Odoo (por nombre exacto se reconoce) o registrar el empaque.

## Validacion automatica

Con *Validar la recepcion si el soporte cuadra exacto* activado (por defecto),
una recepcion se valida sola al terminar la validacion del soporte si:

- es una **recepcion** (no entregas ni internas) y esta **Lista**;
- el soporte quedo **Aprobado** (sin errores ni observaciones);
- cada movimiento tiene lineas en el soporte y la cantidad convertida es
  **exactamente** la pedida: una diferencia que la tolerancia deja pasar no
  marca error, pero tampoco valida sola;
- ninguna unidad quedo sin conversion o sin respaldo;
- ningun producto lleva **lote o numero de serie** (Odoo pediria los lotes).

La recepcion se valida con las cantidades pedidas, que son las del papel. Si
Odoo pide algo mas al validar (un asistente, un dato que falta) no se fuerza
nada: la recepcion queda como estaba y el motivo queda en el chatter. El
mensaje de "validada automaticamente" queda en la recepcion y en el soporte.

## Contrato de la IA de vision

Con el proveedor `anthropic` se llama la Messages API
(`POST https://api.anthropic.com/v1/messages`) con un **bloque de imagen** y
**salida estructurada** (`output_config.format` de tipo `json_schema`), asi la
respuesta llega como JSON valido contra el esquema sin limpiar texto. Un PDF
viaja como bloque `document` en vez de `image`.

Se usa `requests` en vez del SDK `anthropic` porque la imagen `odoo:17.0` no lo
trae y el modulo no agrega dependencias Python. El modelo por defecto es
`claude-opus-5-5`; se cambia en Ajustes.

**Respuesta esperada** (el mismo dict que produce el adaptador, mas
`confidence`, `provider` y `raw`):

```json
{
  "remission_ref": "REM-00123",
  "issue_date": "2026-09-10",
  "sender":   {"nit": "900123456", "dv": "7", "name": "CAFES DEL SUR SAS"},
  "receiver": {"nit": "901234567", "dv": "8", "name": "LIBERTARIO COFFEE"},
  "lines": [
    {"description": "Cafe verde excelso", "code": "CAFE-001",
     "quantity": 100.0, "unit": "KG"}
  ],
  "signatures": {
    "sender":   {"present": true, "confidence": 0.92, "name": "Juan Perez",
                 "id_number": "", "note": ""},
    "receiver": {"present": true, "confidence": 0.88, "name": "Ana Gomez",
                 "id_number": "", "note": ""}
  },
  "confidence": 0.9,
  "raw_warnings": []
}
```

Solo viajan la imagen y, como contexto de vocabulario, los nombres de las
partes esperadas y los productos de la operacion. El *prompt* le dice
explicitamente al modelo que **transcriba lo que dice el documento** aunque no
coincida con ese contexto: la pista es para leer mejor, no para que confirme lo
que queremos oir.

Formatos: JPG, PNG, WEBP, GIF y PDF. Antes de enviarla, la foto se **reduce
sola** (`vision_adapter.prepare_image`, con Pillow, que ya viene en Odoo): se
endereza segun el EXIF, se lleva a 1600 px por el lado largo y se manda como
JPEG. Una foto de celular de 8 MB queda en unos cientos de KB y se sigue
leyendo bien. El comprobante guardado en Odoo no se toca: queda el original
como evidencia.

El limite de la API (5 MB en base64, unos 3,7 MB de archivo) solo lo alcanza
ya un PDF pesado; en ese caso, o con otro formato, el soporte queda en captura
manual con el motivo escrito. Las fotos HEIC de iPhone no se aceptan: el
navegador del celular normalmente las convierte a JPEG al subirlas.

Con el proveedor `http` se llama un servicio propio (n8n, FastAPI) que reciba
`multipart/form-data` con `file` y `hint` y devuelva ese mismo JSON.

### Conexion de prueba por CLI local

Con la IA habilitada, la casilla **Conexion de prueba por CLI local** cambia la
API de Anthropic por el puente `anthropic_cli_bridge`, igual que en
`supplier_invoice_portal`. Sirve para probar en desarrollo con la suscripcion
que uno ya tiene, sin API key. No es para produccion. Si la CLI configurada no
acepta imagenes, el puente responde con error y el soporte queda en captura
manual, como cualquier otro fallo.

## Captura manual, revalidar y volver a leer

Si la IA esta apagada, no responde o lee mal, todo el formulario es editable:
numero, fecha, partes, firmas y lineas. **Las reglas leen siempre el
formulario**, no la respuesta de la IA, asi que un soporte capturado a mano
completo puede quedar *Aprobado*. Es el mismo criterio de
`supplier_invoice_portal`: el servicio externo puede faltar, el trabajo no se
detiene.

Que hace cada boton:

| Boton | Lee la foto | Que pasa con lo escrito en el formulario |
|---|---|---|
| **Validar / Revalidar** | solo si todavia no hay una lectura buena | la lectura solo llena lo vacio; lo corregido a mano se queda |
| **Volver a leer la foto** | siempre | se reemplaza por lo que lea la IA, salvo las lineas emparejadas a mano |
| Cambiar la foto (en borrador) | en la siguiente validacion | se borra: otra foto es otro documento |

Asi, si la IA leyo 90 donde decia 100, se corrige la linea y se revalida sin
volver a pagar una lectura ni perder la correccion.

Marcar a mano la casilla de una firma la deja con confianza 100 %: es una
persona confirmando, mirando la foto, que el trazo esta.

## Grupos de seguridad

| Grupo | Puede |
|---|---|
| **Operario** (`group_sos_user`) | Adjuntar el comprobante de una operacion y validarlo |
| **Responsable** (`group_sos_manager`) | Todo lo anterior, mas configurar, borrar soportes y ver el JSON tecnico |

*Inventario / Usuario* implica *Operario* e *Inventario / Administrador* implica
*Responsable*: quien ya maneja el inventario queda con el rol que le corresponde
sin asignarlo a mano.

El JSON tecnico (`extracted_json`, `validation_json`) solo lo ve el
*Responsable*: puede contener datos de terceros.

## Tests

```bash
docker run --rm --network odoodkr17_webnet \
  -v "$PWD/config:/etc/odoo" -v "$PWD/addons:/mnt/extra-addons/custom-addons" \
  odoo:17.0 odoo -c /etc/odoo/odoo.conf -d spr_check \
  -i stock_operation_support --test-enable \
  --test-tags /stock_operation_support --stop-after-init --without-demo=all
```

`tests/test_vision_adapter.py` cubre la normalizacion (NIT, numeros en formato
colombiano y anglosajon, fechas, respuestas incompletas), la deteccion del tipo
de archivo, el cuerpo de la peticion (imagen antes del texto, PDF como
documento) y todos los fallos del servicio: red, timeout, 401, JSON basura,
rechazo del modelo y `max_tokens`. `tests/test_support_flow.py` recorre el flujo
con ORM: cantidades de mas y de menos, tolerancias, firmas, partes segun el tipo
de operacion, captura manual, emparejamiento manual conservado, remision
duplicada y que **la operacion se valida igual** aunque el soporte quede
rechazado. Ningun test hace red: la IA se inyecta simulada.

## Decisiones

- **Modulo aparte y no dentro de `supplier_invoice_portal`.** Ese modulo es de
  facturas de proveedor, no depende de `stock` y tiene su propia fecha de
  entrega. Meterle inventario encima habria cambiado su alcance y su riesgo.
- **Vision en vez de OCR de texto.** Los comprobantes son fotos de papeles
  firmados a mano: no hay texto seleccionable, y ademas hay que juzgar si una
  casilla tiene trazo de firma. Eso un OCR de texto no lo hace.
- **Advierte, no bloquea.** Si el soporte bloqueara `button_validate`, una
  caida del servicio de IA frenaria el almacen. El aviso queda en la cabecera de
  la operacion y en el chatter, y la persona decide.
- **Validar solo cuando cuadra exacto** (2026-10-07, pedido del usuario). Es lo
  unico que el modulo hace con el inventario por su cuenta, y por eso las
  condiciones son estrictas: exacto, aprobado, recepcion, sin lotes.
- **En la operacion manda el soporte mas reciente.** Si la primera foto salio
  rechazada y despues se subio la buena, la cabecera muestra la buena: el
  operario no puede borrar la vieja y el aviso no debe quedarse para siempre.
- **La IA empareja solo lo que lo determinista no resuelve** (2026-10-07,
  pedido del usuario; antes no usaba IA). Codigo y descripcion siguen primero
  porque son reproducibles; la IA entra para unidades del proveedor y lineas
  sin parecido, sin ver las cantidades y con el factor verificado contra el
  papel o los empaques.
- **Tolerancias en 0 por defecto.** En inventario, una unidad de mas o de menos
  es justo lo que hay que ver.

## Fuera del alcance

- Firma digital o biometrica (esto verifica firmas manuscritas en una foto, no
  las certifica).
- Reconocer *de quien* es la firma: se detecta el trazo y se lee el nombre
  escrito al lado, no se compara contra una firma registrada.
- Soportes que cubran varias operaciones a la vez.
- Crear o corregir movimientos desde el comprobante: el modulo no cambia lo
  pedido. Lo unico que escribe es la validacion de una recepcion que cuadra
  exacto, con las cantidades pedidas.
