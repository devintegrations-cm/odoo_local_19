Pide al cajero el **número de clientes** (comensales) de la orden en cuanto entra a la pantalla de
**Pago** del Punto de Venta, antes de elegir el método de pago. El número tiene que estar dentro de
un rango **mínimo y máximo** configurable por punto de venta; si está fuera del rango, no se guarda.

La pregunta es **obligatoria**: si el cajero la descarta al entrar, se le vuelve a hacer al pulsar
*Validar*, y la orden no se valida hasta que responda con un número válido.

El valor se guarda en el campo estándar **Comensales** de la orden (`customer_count`, de
`pos_restaurant`), el mismo que usan las mesas. Por eso el valor por invitado de la pantalla de pago,
el encabezado del recibo (*Mesa N, Comensales: X*) y la ficha de la orden en el backend lo muestran
sin cambios adicionales.

Relación con Odoo 19: `pos_restaurant` ya maneja el número de comensales, pero **no lo exige**. Al
abrir una mesa lo llena con los asientos de la mesa, y solo lo pregunta al abrir la orden si el
punto de venta usa *presets* con la opción de invitados. Este módulo agrega la pregunta obligatoria
y el rango válido.
