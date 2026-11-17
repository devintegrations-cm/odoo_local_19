# Purchase Order Price Validation - Odoo 19

## Descripción

Módulo para Odoo 19 que valida variaciones de precio unitario en órdenes de compra y recepciones de inventario, comparándolas con el costo establecido del producto y un porcentaje de variación permitido.

## Características

### ✅ Validación en Órdenes de Compra
- Valida precios al confirmar órdenes de compra
- Valida precios al editar líneas de orden
- Previene confirmación de órdenes con precios en 0
- Previene confirmación cuando la variación excede el límite permitido

### ✅ Validación en Recepciones de Inventario
- Valida precios al validar recepciones de entrada
- Solo aplica a operaciones de tipo "incoming"
- Misma lógica de validación que órdenes de compra

### ✅ Configuración Flexible
- Activar/desactivar validación en compras independientemente
- Activar/desactivar validación en recepciones independientemente
- Configuración por producto del porcentaje de variación permitido

### ✅ Control de Permisos
- Usuarios regulares: Ven advertencias, no pueden aprobar
- Administradores de inventario: Pueden aprobar variaciones

### ✅ Interfaz Mejorada
- Wizards con mensajes HTML formateados
- Tablas con información detallada de variaciones
- Colores y estilos para mejor visualización

## Instalación

1. Copiar el módulo a la carpeta de addons de Odoo 19
2. Actualizar la lista de aplicaciones
3. Instalar el módulo "Purchase Order Price Validation"

## Configuración

### Configuración General
**Ruta:** Inventario → Configuración → Ajustes → Validación de Precios

- **Validar variación de precios en Órdenes de Compra** (activado por defecto)
- **Validar variación de precios en Recepciones de Inventario** (activado por defecto)

### Configuración por Producto
**Ruta:** Inventario → Productos → Productos → [Producto] → Información General

- **Porcentaje de variación:** Define el % máximo de variación permitido (por defecto: 10%)

## Uso

### Ejemplo 1: Orden de Compra con Variación
1. Producto con costo de $100 y variación permitida del 10%
2. Crear orden de compra con precio unitario de $120 (20% de variación)
3. Al confirmar, aparece wizard mostrando:
   - Producto
   - Variación permitida: 10%
   - Variación generada: 20%
   - Costo actual: $100
   - Costo ingresado: $120
4. Administrador puede aprobar o cancelar

### Ejemplo 2: Recepción con Precio en 0
1. Crear recepción de inventario
2. Agregar producto con precio unitario = 0
3. Al validar, aparece wizard de advertencia
4. Usuario regular no puede continuar
5. Administrador puede aprobar

## Estructura de Archivos

```
purchase_price_validation/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── purchase_order.py
│   ├── stock_picking.py
│   ├── product_template.py
│   ├── confirmation_variation_wizard.py
│   ├── warning_variation_wizard.py
│   └── res_config_settings.py
├── views/
│   ├── purchase_order_views.xml
│   ├── product_template_views.xml
│   ├── confirmation_variation_wizard.xml
│   ├── warning_variation_wizard.xml
│   └── res_config_settings_views.xml
├── security/
│   └── ir.model.access.csv
├── UPGRADE_NOTES_V19.md
├── CONFIGURATION_GUIDE.md
└── README.md
```

## Dependencias

- `purchase` - Módulo de compras de Odoo
- `product` - Módulo de productos de Odoo
- `stock` - Módulo de inventario de Odoo

## Versión

- **Versión del módulo:** 19.0.1.1.0
- **Versión de Odoo:** 19.0
- **Licencia:** LGPL-3

## Autor

**Libertario Coffee Roasters**
- Website: https://www.libertariocoffee.com

## Soporte

Para más información, consultar:
- `UPGRADE_NOTES_V19.md` - Notas de actualización desde Odoo 17
- `CONFIGURATION_GUIDE.md` - Guía detallada de configuración

## Changelog

### v19.0.1.1.0
- Migración a Odoo 19
- Reemplazado `product.type == 'product'` por `product.type == 'consu'` (tipo de producto cambiado en Odoo 19)
- Reemplazado `move_ids_without_package` por `move_ids` (campo eliminado en Odoo 19)

### v17.0.1.1.0
- Migración a Odoo 17
- Agregada validación en recepciones de inventario
- Agregada configuración para activar/desactivar validaciones
- Mejorada interfaz de wizards con HTML formateado
- Cambiado tipo de campo de mensaje de Text a Html
