# POS Restrict Delete Ordered Order Line - Odoo 19

Restringe la eliminacion/reduccion de lineas de orden del POS que fueron
enviadas a cocina, con permisos basados en empleados.

## Modulo

- **Nombre:** Restrict erase POS order line
- **Version:** 19.0.1.0.0
- **Categoria:** Point of Sale
- **Autor:** Libertario Coffee Roasters
- **Licencia:** LGPL-3
- **Dependencias:** pos_restaurant

## Funcionalidad

- Protege lineas de orden despues de enviarlas a cocina
- Permisos por empleado para override
- Badge "En preparacion" con botones +/- en cada linea
- Restriccion al reducir por debajo de la cantidad ordenada
- Soporte para Split Bill

## Instalacion

1. Copiar el modulo a la carpeta de addons
2. Reiniciar Odoo
3. Actualizar lista de apps
4. Instalar "Restrict erase POS order line"

## Configuracion

1. Ir a: **Point of Sale > Configuration > Point of Sale**
2. Abrir la configuracion del POS
3. En **"Log in with Employees"** (requiere pos_hr), agregar empleados
4. Dejar vacio = todos pueden (comportamiento por defecto)

## Uso en el POS

1. Agregar productos a la orden
2. Hacer clic en "Order" (enviar a cocina)
3. Aparecen cantidades ordenadas con badge y botones +/-
4. Intentar reducir por debajo de lo ordenado:
   - **Con permiso:** funciona
   - **Sin permiso:** popup de error
5. Botones +/- para ajustes rapidos

## Comportamiento

- Puede AUMENTAR cantidad (siempre permitido)
- No puede REDUCIR por debajo de lo ordenado (salvo permiso)
- Popup de error si el usuario no tiene permiso
- Datos persisten entre recargas y sesiones

## Detalles Tecnicos

### Modelos Python

- `pos.config` - Campo `able_del_pol_employee_ids` (Many2many a hr.employee)
- `pos.order.line` - Campo `ordered_quantities` (Float, almacenado)
- `res.config.settings` - Campo `pos_able_del_pol_employee_ids`

### JavaScript (Odoo 19)

- `models.js` - Patch de PosOrderline.setQuantity() y PosOrder.removeOrderline(),
  ordena la restriccion y bloquea eliminacion de lineas ordenadas
- `pos_store.js` - Patch de PosStore: captura ordered_quantities al enviar a cocina
  (submitOrder/pay) y expone referencia compartida
- `orderline.js` - Componente UI con botones +/- que operan sobre el modelo
- `split_bill_screen.js` - Actualiza ordered_quantities despues de dividir cuenta

### Templates

- `orderline.xml` - Extension de point_of_sale.Orderline con badge y botones

### Estilos

- `orderline.scss` - Estilos para botones +/- y badge

## Migracion de Odoo 17 a 19

| Area | Odoo 17 | Odoo 19 |
|------|---------|---------|
| Data loading | `_order_line_fields()`, `_export_for_ui()` | `_load_pos_data_fields()` via pos.load.mixin |
| JS data model | `@point_of_sale/app/store/models` | `@point_of_sale/app/models/pos_order_line` |
| JS UI component | `@point_of_sale/app/generic_components/orderline/orderline` | `@point_of_sale/app/components/orderline/orderline` |
| usePos hook | `@point_of_sale/app/store/pos_hook` | `@point_of_sale/app/hooks/pos_hook` |
| Error popup | `ErrorPopup` via popup service | `AlertDialog` via dialog service |
| Action button | `ActionpadWidget.submitOrder()` | `PosStore.submitOrder()` / `PosStore.pay()` |
| Split bill | `SplitBillScreen.proceed()` | `SplitBillScreen.createSplittedOrder()` |
| Session loader | `_loader_params_pos_order_line()` | Eliminado (cada modelo define _load_pos_data_fields) |

## Compatibilidad

- Odoo 19.0 Community y Enterprise
- pos_restaurant (requerido)
- pos_loyalty (compatibles con lineas de reward)
- pos_hr (opcional, necesario para permisos por empleado)

## Testing Checklist

### Backend:
- [ ] Campo "Employees able to erase order lines" visible en config del POS
- [ ] Agregar/quitar empleados y guardar

### POS:
- [ ] Abrir sesion POS
- [ ] Agregar productos y enviar a cocina
- [ ] Badge "En preparacion" visible con botones +/-
- [ ] Reducir cantidad sin permiso -> popup error
- [ ] Reducir cantidad con permiso -> funciona
- [ ] Botones +/- funcionan correctamente
- [ ] Recargar pagina -> datos persisten

### Restaurant:
- [ ] Split Bill -> cantidades se actualizan en ambas ordenes
- [ ] Lineas de reward no muestran badge de ordenado

## Archivos

pos_restrict_del_ordered_order_line/
├── init.py
├── manifest.py
├── README.md
├── models/
│   ├── init.py
│   ├── pos_config.py
│   ├── pos_order.py
│   └── res_config_settings.py
├── static/
│   └── src/
│       ├── css/
│       │   └── orderline.scss
│       ├── js/
│       │   ├── models.js
│       │   ├── orderline.js
│       │   ├── pos_store.js
│       │   └── split_bill_screen.js
│       └── xml/
│           └── orderline.xml
└── views/
    ├── pos_order_view.xml
    └── res_config_settings_views.xml

## Autor

**Libertario Coffee Roasters**
https://www.libertariocoffee.com
Migrado a Odoo 19: Septiembre 2026

## Licencia

LGPL-3