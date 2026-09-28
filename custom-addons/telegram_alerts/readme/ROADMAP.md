## Limitaciones conocidas

- **Los datos de instalación pisan la configuración.** `data/telegram_config.xml` y la acción
  planificada de `data/server_actions.xml` no están en `noupdate`. Al actualizar el módulo se
  restauran el token, los chats y el mensaje de *Alertas Costos*, y la acción planificada vuelve a
  quedar activa cada 1 día aunque se hubiera apagado o cambiado.
- **Token real en el repositorio.** `data/telegram_config.xml` trae un token de bot y dos chat id
  reales, que se cargan en cualquier base donde se instale el módulo. Mientras eso siga así, una
  base de pruebas con la acción planificada activa puede enviar mensajes a los chats reales.
- **Permisos abiertos.** `security/ir.model.access.csv` da lectura, escritura, creación y borrado
  del modelo `telegram.alerts.config` sin grupo, es decir, a todos los usuarios; el menú tampoco
  tiene grupo. El token se enmascara en pantalla (`password="true"`), pero cualquier usuario puede
  leerlo por la API.
- **Sin tiempo límite ni reintentos.** `send_message` llama a Telegram con `requests.get` sin
  `timeout`. Si Telegram no responde, el proceso queda esperando. No hay reintentos: un fallo se
  informa como error y el siguiente intento es la próxima ejecución diaria.
- **El token aparece en los errores.** El token va dentro de la URL del pedido y
  `raise_for_status()` arma el mensaje de error con esa URL, así que queda visible en el diálogo de
  error y en el log del servidor.
- **Un fallo corta el envío.** `resp.raise_for_status()` lanza una excepción en el primer chat que
  falla y los chats siguientes no reciben el mensaje.
- **Errores técnicos al usuario.** Si falta la conexión se lanza `ValueError`, no `UserError`, así
  que el usuario ve un error del servidor en lugar de un aviso.
- **Textos sin traducir.** Etiquetas, menús, nombres de acciones y el mensaje de *Calculate
  Difference Percentage* están en inglés y el módulo no tiene carpeta `i18n`; el encabezado del
  resumen diario está en español dentro del código.
- *Calculate Difference Percentage* no incluye el nombre del producto en el mensaje y toma la
  primera conexión que encuentra, no la `cost_alert`.
- El ícono `static/description/icon.png` mide 1024x1024 px; la convención del proyecto es
  100x100 px.

## Componentes

- `models/telegram_alerts.py`: modelo `telegram.alerts.config` (la conexión) y el envío
  (`send_message`, `send_alert`, `send_alert_test`) a `https://api.telegram.org/bot<token>/sendMessage`,
  en texto plano.
- `models/product_template.py`: campos `reference_cost` y `percentage_difference_cost` en
  `product.template`, la validación 0–1 y los métodos `calculate_difference_percentage` y
  `send_cost_differences(identifier)`.
- `views/telegram_alerts_views.xml`: lista, formulario, acción y menú **Telegram Alerts ›
  Configuration**.
- `views/product_view.xml`: los dos campos dentro del grupo `group_standard_price` del formulario
  de producto.
- `data/server_actions.xml`: las tres acciones de servidor y la acción planificada diaria.
- `data/telegram_config.xml`: la conexión *Alertas Costos* (`cost_alert`).

## Notas para mantenimiento

- El Custom ID `cost_alert` está escrito en dos lugares de `data/server_actions.xml` (acción de
  servidor y acción planificada). Si se renombra, hay que cambiar los dos.
- La acción planificada corre con el usuario *OdooBot*, que es quien lee los costos de los
  productos.
- El módulo no tiene tests automáticos. Para probar sin enviar a chats reales, usar un bot y un
  chat de prueba en la conexión, o apagar la acción planificada en la base de pruebas.
