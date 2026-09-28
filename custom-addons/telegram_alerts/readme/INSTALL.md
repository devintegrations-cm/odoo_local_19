## Dependencias

- Módulos de Odoo: `base` y `product`. No depende de otros módulos de este repositorio.
- Librería de Python `requests`, que ya viene con Odoo (en la imagen `odoo:19.0` está la versión
  2.31.0). No hay que instalar nada adicional.
- **API de Telegram para bots.** El servidor de Odoo debe poder salir a internet hacia
  `https://api.telegram.org`. Hace falta un bot creado con **@BotFather** (que entrega el token) y
  que ese bot pueda escribir en cada chat destino: el usuario tiene que haberle iniciado una
  conversación, o el bot tiene que estar agregado al grupo.

## Pasos de instalación

Instalar **Telegram Alerts** desde *Aplicaciones*. La instalación crea:

- el menú **Telegram Alerts › Configuration**;
- una conexión de ejemplo llamada *Alertas Costos* con Custom ID `cost_alert`;
- los campos *Reference Cost* y *Percentage Difference Cost* en el producto;
- tres acciones de servidor (*Calculate Difference Percentage*, *Send Cost Differences* y *Send
  Telegram Alert*) y la acción planificada diaria *Send Cost Differences*, activa desde el
  momento de la instalación.

Después de instalar, revisar la conexión *Alertas Costos* (ver *Configuración*) antes de que corra
la acción planificada.

## Migración desde Odoo 17

El nombre técnico del módulo, del modelo `telegram.alerts.config` y de los campos de producto
(`reference_cost`, `percentage_difference_cost`) no cambian respecto de 17, así que los datos se
conservan sin script. Cambios de la migración: la vista de lista usa `<list>` en lugar de
`<tree>`, la acción planificada ya no lleva `numbercall` (en 19 se repite hasta que se desactiva)
y se quitaron los archivos de ejemplo del andamiaje de Odoo (`models/models.py`, controlador,
`views/views.xml`, `views/templates.xml` y `demo/demo.xml`), que en 17 estaban completamente
comentados. La etiqueta del campo *Percentage Difference Cost* corrigió su ortografía.
