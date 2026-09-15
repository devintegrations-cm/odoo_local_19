# Guía de Configuración - Validación de Precios

## Acceso a la Configuración

Para acceder a la configuración del módulo:

1. Ir a **Inventario → Configuración → Ajustes**
2. Desplazarse hasta la sección **"Validación de Precios"**
3. Encontrará dos opciones configurables:

## Opciones de Configuración

### 1. Validar variación de precios en Órdenes de Compra

- **Activado por defecto:** Sí
- **Descripción:** Valida que el precio unitario en las órdenes de compra no exceda la variación permitida del producto
- **Cuándo se aplica:** Al confirmar una orden de compra o al editar líneas de orden

**Comportamiento cuando está activado:**

- Si el precio unitario es 0, muestra advertencia
- Si la variación del precio excede el porcentaje permitido, muestra advertencia
- Los administradores de inventario pueden aprobar las variaciones
- Los usuarios regulares no pueden confirmar órdenes con variaciones

**Comportamiento cuando está desactivado:**

- Las órdenes de compra se confirman sin validación de precios
- No se muestran advertencias ni wizards de confirmación

### 2. Validar variación de precios en Recepciones de Inventario

- **Activado por defecto:** Sí
- **Descripción:** Valida que el precio unitario en las recepciones de inventario no exceda la variación permitida del producto
- **Cuándo se aplica:** Al validar una recepción de inventario (operaciones de entrada)

**Comportamiento cuando está activado:**

- Si el precio unitario es 0, muestra advertencia
- Si la variación del precio excede el porcentaje permitido, muestra advertencia
- Los administradores de inventario pueden aprobar las variaciones
- Los usuarios regulares no pueden validar recepciones con variaciones

**Comportamiento cuando está desactivado:**

- Las recepciones se validan sin verificación de precios
- No se muestran advertencias ni wizards de confirmación

## Configuración de Productos

Para configurar el porcentaje de variación permitido por producto:

1. Ir a **Inventario → Productos → Productos**
2. Abrir el producto deseado
3. En la pestaña **Información General**, sección **Costo**
4. Configurar el campo **"Porcentaje de variación"** (por defecto: 10%)
5. Guardar el producto

## Permisos Requeridos

- **Usuarios regulares:** Pueden ver las advertencias pero no pueden aprobar variaciones
- **Administradores de inventario** (grupo `stock.group_stock_manager`): Pueden aprobar órdenes/recepciones con variaciones de precio

## Casos de Uso

### Caso 1: Validación Completa (Recomendado)

- Ambas opciones activadas
- Validación en compras y recepciones
- Máximo control sobre variaciones de precio

### Caso 2: Solo Validación en Compras

- Activar solo "Órdenes de Compra"
- Desactivar "Recepciones de Inventario"
- Útil cuando las recepciones siempre vienen de órdenes de compra ya validadas

### Caso 3: Solo Validación en Recepciones

- Desactivar "Órdenes de Compra"
- Activar solo "Recepciones de Inventario"
- Útil cuando se reciben productos sin orden de compra previa

### Caso 4: Sin Validación

- Ambas opciones desactivadas
- No se realizan validaciones de precio
- Útil para entornos de prueba o casos especiales

## Notas Importantes

- Los cambios en la configuración se aplican inmediatamente
- No es necesario reiniciar Odoo después de cambiar la configuración
- Las validaciones solo se aplican a productos de tipo "Goods" (consu)
- Las validaciones no afectan operaciones de salida o transferencias internas
