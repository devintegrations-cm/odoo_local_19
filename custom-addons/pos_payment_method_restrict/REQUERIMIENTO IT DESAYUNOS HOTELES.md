# **Solicitud de desarrollo IT**

## **Sistema de registro, control de inventario y facturación mensual de desayunos – Convenio hotelero**

### **1\. Objetivo de la solicitud**

Se requiere desarrollar o configurar en el sistema de facturación/POS del coffee shop Libertario Laureles un flujo especial para la atención de los huéspedes de un hotel aliado.

Los huéspedes que tengan el desayuno incluido en su reserva podrán dirigirse al coffee shop y seleccionar un desayuno y una bebida entre unas opciones previamente definidas.

Estas órdenes deberán:

* Registrarse individualmente en el sistema.  
* Descontar automáticamente el inventario correspondiente.  
* Contabilizar la cantidad de desayunos entregados.  
* No exigir el pago inmediato por parte del huésped.  
* Acumularse en una cuenta por cobrar a nombre del hotel.  
* Permitir la facturación consolidada al hotel al finalizar cada mes.  
* Conservar el detalle de los productos y opciones entregadas durante el periodo.

Adicionalmente, los huéspedes del hotel tendrán un beneficio del 10 % de descuento en otros consumos de alimentos y bebidas realizados en el coffee shop Libertario Laureles. Este beneficio no aplicará para bolsas de café.

---

# **2\. Alcance general**

El desarrollo debe contemplar dos flujos diferentes:

## **Flujo A: desayuno incluido en la reserva**

Corresponde al desayuno y la bebida incluidos en el convenio con el hotel.

El huésped no deberá realizar ningún pago en el momento de la entrega. El consumo deberá quedar cargado a la cuenta del hotel para ser facturado al cierre del mes.

## **Flujo B: consumos adicionales del huésped**

Corresponde a cualquier otro alimento o bebida que el huésped desee comprar adicionalmente durante su visita.

En este caso:

* El huésped deberá pagar directamente su consumo.  
* Se aplicará un descuento del 10 %.  
* El descuento solo será válido en el coffee shop Libertario Laureles.  
* El descuento aplicará a alimentos y bebidas.  
* Las bolsas de café deberán estar excluidas del descuento.  
* El beneficio no deberá acumularse con otras promociones, descuentos o beneficios, salvo que se defina expresamente lo contrario.

---

# **3\. Productos incluidos en el desayuno del hotel**

Cada desayuno deberá estar compuesto por:

* Una opción de alimento.  
* Una opción de bebida.

## **3.1. Opciones de alimento**

El huésped podrá escoger una de las siguientes opciones:

1. Tostadas francesas.  
2. Cacerola de huevos gratinados.  
3. Cacerola de huevos al gusto.  
4. Bowl de granola.

Cada alimento deberá ser facturado al hotel con un descuento del 10 % sobre su precio vigente en la carta.

El sistema deberá tomar como referencia el precio de venta actual de cada producto y aplicar automáticamente el 10 % de descuento.

### **Consideración importante**

Si el precio de alguno de estos productos cambia en la carta, el valor del convenio también deberá actualizarse automáticamente, manteniendo el descuento del 10 %, o deberá existir un mecanismo claramente definido para actualizar el precio del convenio.

Se debe evitar que los precios del convenio queden desactualizados frente a los precios vigentes de la carta.

---

## **3.2. Opciones de bebida**

El huésped podrá escoger una bebida entre las siguientes categorías:

1. Bebida a base de espresso.  
2. Jugo.  
3. Chocolate.

Todas las opciones de bebida deberán ser cobradas al hotel al mismo valor, independientemente de la bebida seleccionada.

El precio de facturación de la bebida será equivalente al precio de venta vigente de un **Cappuccino Paz Almendra**, menos un descuento del 10 %.

### **Requerimiento para la creación de productos**

Es necesario crear uno o varios productos específicos en el sistema que permitan:

* Registrar la categoría o bebida seleccionada por el huésped.  
* Descontar los ingredientes o inventario correspondiente a la bebida efectivamente preparada.  
* Mantener un único precio de facturación para todas las bebidas del convenio.  
* Identificar en los reportes cuál fue la bebida seleccionada.  
* Evitar que la selección de una bebida con un precio de carta diferente modifique el valor que se le cobrará al hotel.

Se propone manejar un producto principal llamado, por ejemplo:

**Bebida desayuno hotel**

Este producto tendría como precio el valor del Cappuccino Paz Almendra menos el 10 %.

Al agregarlo a la orden, el sistema deberá solicitar al encargado seleccionar la bebida entregada:

* Bebida a base de espresso.  
* Jugo.  
* Chocolate.

Idealmente, el sistema deberá permitir seleccionar también la referencia específica preparada cuando aplique, con el fin de descontar correctamente el inventario.

Por ejemplo:

* Cappuccino.  
* Latte.  
* Americano.  
* Espresso.  
* Chocolate.  
* Jugo disponible.

La selección específica no deberá cambiar el precio de venta del producto para el hotel.

---

# **4\. Creación del producto o combo de desayuno**

Se solicita evaluar la creación de un producto compuesto, combo o categoría especial llamada, por ejemplo:

**Desayuno convenio hotel**

Al seleccionar este producto en el POS, el sistema deberá obligar al encargado a escoger:

### **Selección 1: alimento**

* Tostadas francesas.  
* Cacerola de huevos gratinados.  
* Cacerola de huevos al gusto.  
* Bowl de granola.

### **Selección 2: bebida**

* Bebida a base de espresso.  
* Jugo.  
* Chocolate.

El sistema no deberá permitir finalizar el registro del desayuno sin haber seleccionado una opción de alimento y una opción de bebida.

Cada componente deberá descontar correctamente sus ingredientes, materias primas o productos asociados del inventario.

En el documento de venta y en los reportes deberá visualizarse, como mínimo:

* Producto principal: desayuno convenio hotel.  
* Alimento seleccionado.  
* Bebida seleccionada.  
* Valor del alimento.  
* Valor de la bebida.  
* Descuento aplicado.  
* Valor total a facturar al hotel.

---

# **5\. Registro del huésped y validación del beneficio**

Antes de registrar el desayuno, el encargado del servicio deberá validar que el huésped tenga el desayuno incluido.

Para garantizar trazabilidad, cada desayuno deberá registrar como mínimo los siguientes datos:

* Fecha.  
* Hora.  
* Nombre del huésped.  
* Número de habitación.  
* Hotel asociado.  
* Número de reserva, voucher o autorización, cuando esté disponible.  
* Alimento seleccionado.  
* Bebida seleccionada.  
* Nombre o usuario del colaborador que registró la entrega.  
* Observaciones, cuando sean necesarias.

Se solicita que IT evalúe cuál de estos datos puede configurarse como obligatorio en el POS.

Como mínimo, se recomienda que sean obligatorios:

* Número de habitación.  
* Nombre del huésped o número de reserva.  
* Hotel asociado.

El objetivo es evitar:

* Registros duplicados.  
* Entregas a personas que no pertenezcan al hotel.  
* Dificultades al conciliar la información con el hotel.  
* Desayunos registrados sin información de soporte.

---

# **6\. Control de cantidad de desayunos entregados**

El sistema deberá permitir llevar un conteo diario y mensual de los desayunos entregados.

El encargado deberá poder consultar:

* Total de desayunos entregados durante el día.  
* Total acumulado durante el mes.  
* Cantidad entregada por fecha.  
* Cantidad entregada por huésped.  
* Cantidad entregada por habitación.  
* Cantidad de cada alimento seleccionado.  
* Cantidad de cada tipo de bebida seleccionada.  
* Valor acumulado pendiente por facturar al hotel.

Se deberá evaluar la creación de una alerta o validación que identifique posibles registros duplicados para un mismo huésped, habitación o reserva durante el mismo día.

La alerta no necesariamente deberá bloquear la operación, ya que podrían existir reservas con más de un huésped por habitación, pero sí deberá advertir al encargado para que confirme la entrega.

---

# **7\. Descuento de inventario**

Aunque el desayuno no sea pagado inmediatamente, la orden deberá procesarse como una salida real de producto.

El sistema deberá:

* Descontar el inventario en el momento en que se entregue el desayuno.  
* Consumir las recetas o listas de materiales correspondientes.  
* Descontar los ingredientes del alimento seleccionado.  
* Descontar los ingredientes de la bebida seleccionada.  
* Registrar la salida en el coffee shop Libertario Laureles.  
* Conservar la trazabilidad de inventario por cada orden.  
* Evitar que la salida de inventario dependa del pago o de la factura mensual al hotel.

La operación deberá considerarse entregada y consumida en el momento del servicio, aunque financieramente permanezca pendiente de pago.

---

# **8\. Pago diferido y cuenta por cobrar al hotel**

Las órdenes del desayuno incluido no deberán solicitar:

* Efectivo.  
* Tarjeta.  
* Transferencia.  
* Código QR.  
* Otro medio de pago inmediato.

Se requiere crear un método de pago o flujo especial, por ejemplo:

* Cuenta por cobrar hotel.  
* Convenio hotelero.  
* Crédito hotel.  
* Desayunos hotel pendientes por facturar.

Este método deberá permitir cerrar correctamente la orden en el POS sin registrar un ingreso de dinero inmediato.

Las órdenes deberán quedar asociadas a un cliente específico creado en el sistema con los datos fiscales y comerciales del hotel.

El movimiento deberá quedar contabilizado de acuerdo con el procedimiento definido por Contabilidad, evitando registrar el pago antes de que el hotel realice el desembolso.

Se solicita que IT valide con el área contable si el flujo debe manejarse como:

* Venta a crédito individual.  
* Cuenta corriente del cliente.  
* Pedido entregado pendiente de facturación.  
* Factura individual pendiente de pago.  
* Consolidación mensual mediante una única factura.  
* Otro mecanismo técnicamente adecuado dentro del sistema actual.

La solución seleccionada deberá evitar duplicar ingresos o facturar dos veces los mismos desayunos.

---

# **9\. Facturación mensual consolidada**

Al finalizar cada mes, el sistema deberá permitir generar un consolidado con todos los desayunos entregados al hotel durante el periodo.

El consolidado deberá incluir:

* Fecha de cada consumo.  
* Hora.  
* Nombre del huésped.  
* Número de habitación.  
* Número de reserva o autorización, cuando aplique.  
* Alimento seleccionado.  
* Bebida seleccionada.  
* Cantidad.  
* Precio de carta utilizado como referencia.  
* Porcentaje de descuento.  
* Valor descontado.  
* Precio final facturado.  
* Total por orden.  
* Total acumulado del mes.

El sistema deberá permitir generar una factura consolidada a nombre del hotel por el valor total consumido durante el mes.

También deberá permitir exportar el detalle en Excel o PDF para enviarlo como soporte de la factura.

La factura mensual deberá estar respaldada por el detalle de las órdenes, pero las órdenes ya incluidas en una factura no deberán volver a aparecer como pendientes en el siguiente periodo.

Se recomienda incluir un estado para cada registro:

* Pendiente por facturar.  
* Facturado.  
* Pagado.  
* Anulado.

---

# **10\. Manejo de anulaciones y correcciones**

El sistema deberá contemplar posibles errores operativos, por ejemplo:

* Selección incorrecta del alimento.  
* Selección incorrecta de la bebida.  
* Registro duplicado.  
* Huésped que finalmente no recibió el desayuno.  
* Orden cargada al hotel por error.  
* Producto preparado que debió ser descartado.

Las anulaciones o correcciones deberán:

* Requerir autorización de un usuario con permisos.  
* Registrar el motivo de la anulación.  
* Registrar el usuario que realizó la modificación.  
* Conservar la trazabilidad del movimiento original.  
* Reintegrar el inventario únicamente cuando corresponda.  
* Evitar que un desayuno anulado sea incluido en la factura mensual.

Cuando el producto haya sido preparado y desperdiciado, no deberá reintegrarse automáticamente al inventario. En este caso, deberá registrarse como merma o desperdicio según el procedimiento definido.

---

# **11\. Beneficio del 10 % para consumos adicionales**

Los huéspedes del hotel tendrán un descuento del 10 % en alimentos y bebidas consumidos en el coffee shop Libertario Laureles.

Este beneficio deberá manejarse como una lista de precios, promoción o descuento específico.

## **Condiciones del beneficio**

* Aplica exclusivamente a huéspedes del hotel aliado.  
* Aplica exclusivamente en Libertario Laureles.  
* Aplica a alimentos.  
* Aplica a bebidas.  
* No aplica a bolsas de café.  
* No deberá aplicarse al desayuno ya incluido en el convenio, porque este tendrá su propio flujo y condiciones.  
* No deberá acumularse con otros descuentos o promociones, salvo autorización expresa.  
* El consumo adicional deberá ser pagado directamente por el huésped.  
* El descuento deberá quedar identificado en la factura o comprobante.

## **Validación del huésped**

Antes de aplicar el descuento, el encargado deberá validar la condición de huésped mediante alguno de los siguientes soportes:

* Llave o tarjeta de la habitación.  
* Voucher.  
* Confirmación de reserva.  
* Listado enviado por el hotel.  
* Documento o mecanismo definido entre las partes.

Se solicita evaluar la creación de un botón de descuento llamado, por ejemplo:

**Beneficio huésped hotel – 10 %**

Este botón deberá:

* Aplicar el 10 % solo a los productos permitidos.  
* Excluir automáticamente las bolsas de café.  
* Impedir la acumulación con otros descuentos.  
* Registrar qué usuario aplicó el beneficio.  
* Permitir auditar cuántas veces fue utilizado.

---

# **12\. Exclusión de bolsas de café**

Todas las referencias pertenecientes a las categorías de bolsas de café deberán quedar excluidas del beneficio del 10 %.

La exclusión deberá funcionar automáticamente, incluso cuando una misma orden incluya:

* Alimentos.  
* Bebidas.  
* Bolsas de café.

Ejemplo:

* Alimento: aplica 10 %.  
* Bebida: aplica 10 %.  
* Bolsa de café: no aplica descuento.

El sistema deberá aplicar el beneficio únicamente sobre los productos autorizados, sin descontar el valor total de la orden.

Se solicita revisar que todas las referencias actuales y futuras de bolsas de café estén correctamente clasificadas en una categoría excluida.

---

# **13\. Usuarios y permisos**

Se deberán definir diferentes niveles de acceso:

## **Encargado de servicio o caja**

Podrá:

* Registrar el desayuno.  
* Seleccionar el alimento.  
* Seleccionar la bebida.  
* Registrar los datos del huésped.  
* Aplicar el beneficio del 10 % en consumos adicionales.  
* Consultar el conteo del día.

No deberá poder:

* Cambiar precios.  
* Modificar el porcentaje del descuento.  
* Anular consumos sin autorización.  
* Marcar órdenes como facturadas.  
* Modificar consumos de periodos cerrados.

## **Administrador del coffee shop**

Podrá:

* Consultar los reportes.  
* Autorizar anulaciones.  
* Corregir información, dejando trazabilidad.  
* Consultar acumulados diarios y mensuales.  
* Revisar consumos pendientes por facturar.

## **Administración, Contabilidad o Finanzas**

Podrá:

* Consultar el consolidado mensual.  
* Exportar los soportes.  
* Generar la factura al hotel.  
* Marcar los registros como facturados.  
* Consultar cuentas por cobrar.  
* Registrar o conciliar el pago del hotel.  
* Cerrar el periodo mensual.

---

# **14\. Reportes requeridos**

La solución deberá generar como mínimo los siguientes reportes:

## **Reporte diario de desayunos**

* Fecha.  
* Total de desayunos entregados.  
* Detalle por huésped y habitación.  
* Alimentos seleccionados.  
* Bebidas seleccionadas.  
* Valor total del día.  
* Anulaciones y correcciones.

## **Reporte mensual para facturación**

* Todos los consumos pendientes por facturar.  
* Detalle de cada desayuno.  
* Subtotal antes del descuento.  
* Descuento aplicado.  
* Total neto a facturar.  
* Número de desayunos.  
* Periodo de facturación.

## **Reporte de productos e inventario**

* Cantidad consumida por producto.  
* Cantidad consumida por ingrediente.  
* Alimentos más seleccionados.  
* Bebidas más seleccionadas.  
* Anulaciones.  
* Mermas asociadas.

## **Reporte del beneficio del 10 %**

* Número de transacciones con beneficio.  
* Valor de venta antes del descuento.  
* Valor total descontado.  
* Valor neto vendido.  
* Detalle de productos.  
* Usuario que aplicó el beneficio.  
* Confirmación de que no se aplicaron descuentos a bolsas de café.

---

# **15\. Requerimientos de auditoría y trazabilidad**

Cada operación deberá conservar:

* Fecha y hora de creación.  
* Usuario que realizó el registro.  
* Datos del huésped.  
* Productos seleccionados.  
* Precio original.  
* Descuento aplicado.  
* Precio final.  
* Estado de facturación.  
* Fecha de facturación al hotel.  
* Número de factura asociada.  
* Historial de cambios.  
* Motivos de anulación o corrección.

Ningún registro facturado deberá poder eliminarse definitivamente del sistema.

---

# **16\. Criterios de aceptación**

El desarrollo se considerará correctamente implementado cuando se cumplan las siguientes condiciones:

1. El encargado puede registrar un desayuno sin recibir un pago inmediato.  
2. El desayuno queda asociado al hotel.  
3. El sistema obliga a seleccionar un alimento y una bebida.  
4. El alimento se factura con el 10 % de descuento sobre su precio de carta.  
5. Todas las bebidas del convenio se cobran al precio del Cappuccino Paz Almendra menos el 10 %.  
6. La bebida seleccionada queda identificada en el sistema.  
7. El inventario se descuenta según el alimento y la bebida realmente entregados.  
8. El sistema muestra el conteo diario y mensual de desayunos.  
9. Los consumos quedan pendientes para la facturación mensual.  
10. Se puede generar un consolidado detallado para el hotel.  
11. Los consumos facturados no vuelven a incluirse en periodos posteriores.  
12. El descuento del 10 % para consumos adicionales solo aplica en Libertario Laureles.  
13. El descuento aplica a alimentos y bebidas.  
14. Las bolsas de café quedan excluidas automáticamente.  
15. El descuento no se acumula con otras promociones.  
16. Las anulaciones requieren autorización y dejan trazabilidad.  
17. Los reportes pueden exportarse para conciliación y facturación.

---

# **17\. Definiciones pendientes para implementación**

Antes de pasar a producción, será necesario confirmar con las áreas responsables:

* Nombre y datos fiscales del hotel.  
* Fecha exacta de inicio del convenio.  
* Día de corte mensual.  
* Condiciones y plazo de pago del hotel.  
* Documento que utilizará el huésped para validar el beneficio.  
* Datos obligatorios que se registrarán por cada huésped.  
* Límite de desayunos por habitación, huésped o reserva.  
* Bebidas específicas disponibles dentro de cada categoría.  
* Si existen adiciones o modificaciones permitidas.  
* Tratamiento de productos agotados.  
* Tratamiento de diferencias entre el reporte del hotel y el reporte de Libertario.  
* Responsable de aprobar anulaciones.  
* Responsable de generar la factura mensual.  
* Cuenta contable y diario que deberán utilizarse.  
* Manejo de impuestos y documento fiscal correspondiente.  
* Regla para la acumulación o no acumulación de descuentos.

---

# **18\. Solicitud al equipo de IT**

Solicitamos al equipo de IT:

1. Revisar la viabilidad técnica del requerimiento dentro del sistema actual.  
2. Definir si la solución se realizará mediante configuración, desarrollo o una combinación de ambos.  
3. Proponer la estructura de productos, categorías, modificadores y listas de precios.  
4. Definir el flujo contable y de cuenta por cobrar junto con Contabilidad.  
5. Confirmar cómo se realizará el descuento automático de inventario.  
6. Diseñar los reportes diarios y mensuales.  
7. Configurar los permisos de usuario.  
8. Implementar las exclusiones del beneficio del 10 %.  
9. Realizar pruebas funcionales antes de la salida a producción.  
10. Entregar un instructivo operativo para caja, administradores y Contabilidad.  
11. Capacitar al equipo de Libertario Laureles antes del inicio del convenio.  
12. Confirmar el tiempo estimado de implementación y los responsables de cada etapa.

La solución deberá ser fácil de utilizar durante la operación, minimizar los registros manuales y garantizar que la información de ventas, inventario, facturación y cartera sea consistente.

