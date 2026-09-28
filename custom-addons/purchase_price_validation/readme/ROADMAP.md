## Limitaciones conocidas

- **Las casillas de Ajustes no desactivan nada.** Los campos tienen `default=True` y el módulo lee
  el parámetro con valor por defecto `'True'`; al desmarcar, Odoo borra el parámetro y ambos lo
  vuelven a leer como activo. Solo se desactiva escribiendo `False` en el parámetro (ver *Uso ›
  Solución de problemas*).
- **Alcance más amplio que en Odoo 17.** En 17 solo se revisaban productos *Almacenables*. En 19 el
  filtro es `type == 'consu'`, que incluye también los *Bienes* sin *Rastrear inventario*
  (antes *Consumibles*). La equivalencia exacta sería filtrar por `is_storable`.
- **Moneda y unidad de medida en compras.** La orden compara `price_unit` de la línea contra
  `standard_price` sin convertir moneda ni unidad (ver *Uso › Solución de problemas*). La recepción
  sí usa el precio ya convertido.
- **Recepciones manuales.** Sus movimientos tienen precio 0 y siempre disparan el aviso.
- **Un solo registro.** `button_confirm` y `button_validate` usan `self.id` y
  `self.picking_type_id.code`; con varios registros y diferencias falla con error de Odoo.
- **Bloqueo al guardar.** El `write` de la orden bloquea a los usuarios sin
  `stock.group_stock_manager` incluso con la orden en borrador. La creación no se revisa.
- **Se pierde la validación analítica.** El botón *Confirmar orden* de Odoo envía
  `validate_analytic=True` en el contexto, y con eso se exigen los planes analíticos obligatorios.
  Al confirmar desde el asistente ese contexto no llega, así que la orden se confirma sin esa
  revisión.
- **Permisos amplios en compras.** `security/ir.model.access.csv` da lectura y creación de
  `purchase.order` a todos los usuarios internos (`base.group_user`). Odoo solo da lectura a
  Inventario y Contabilidad, y creación a Compras. Viene así desde 17.
- **Textos fijos en español**, sin marcar para traducción. Los montos del asistente no usan el
  formato de moneda (`$ 20000.00`) y el porcentaje de la tabla de precio 0 sale con un decimal.
  Las dos opciones de Ajustes comparten el mismo texto de ayuda.
- **Nombres de producto sin escapar.** El mensaje del asistente se arma como HTML con los nombres
  tal cual y el campo tiene `sanitize=False`.
- `static/description/icon.png` mide 750x750 px, no los 100x100 de los módulos del core.

## Componentes

- `models/product_template.py`: el campo `porcent_variation` (*Porcentaje de variación*).
- `models/res_config_settings.py` y `views/res_config_settings_views.xml`: las dos opciones, en el
  bloque *Productos* de los ajustes de Inventario, guardadas como `ir.config_parameter`.
- `models/purchase_order.py`: extiende `write` (bloqueo al guardar líneas) y `button_confirm`
  (asistente); `_continue_confirmation` retoma la confirmación estándar.
- `models/stock_picking.py`: extiende `button_validate` solo para operaciones `incoming`.
- `models/confirmation_variation_wizard.py` y `models/warning_variation_wizard.py`, con sus vistas:
  los dos asistentes (con y sin botón *Confirmar*).
- `views/product_template_views.xml`: el campo en la ficha, dentro del grupo del costo.
- `views/purchase_order_views.xml`: herencia vacía, sin efecto.

## Notas para mantenimiento

- `get_list_products_variation` y `_generate_variation_message` están duplicados en
  `purchase.order` y `stock.picking`. Un cambio en la regla hay que hacerlo en los dos.
- Los métodos extendidos (`write`, `purchase.order.button_confirm`,
  `stock.picking.button_validate`) existen en Odoo 19 con la misma firma.
- `_continue_confirmation` de la orden escribe en el log con nivel `error` en un flujo normal.
- El módulo no tiene tests automáticos.
