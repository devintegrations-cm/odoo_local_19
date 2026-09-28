Envía **alertas de costos de productos a Telegram**. Cada producto puede tener un **costo de
referencia** y un **porcentaje de diferencia permitido**; una acción planificada diaria revisa todos
los productos y manda a uno o varios chats de Telegram la lista de los que tienen el costo por
fuera de ese umbral.

Sirve para detectar a tiempo un costo mal cargado o un cambio de precio de compra que no se
esperaba, sin tener que revisar los productos uno por uno.

Las alertas salen por un **bot de Telegram** propio del negocio. El módulo guarda la conexión (token
del bot y chats destino) y ofrece además una acción para enviar un mensaje de prueba y otra para
calcular la diferencia de productos puntuales.
