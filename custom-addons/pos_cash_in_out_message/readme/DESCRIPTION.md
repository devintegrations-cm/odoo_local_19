Pide una **confirmación explícita** antes de registrar una entrada o salida de efectivo en el
Punto de Venta. Al pulsar *Confirmar* en la ventana de *Entrada/salida de efectivo*, aparece un
diálogo que muestra el tipo de movimiento (entrada o salida), el monto y, si el punto de venta lo
tiene configurado, un **mensaje propio** del negocio (por ejemplo, un recordatorio del
procedimiento de caja). El movimiento solo se registra si el cajero responde *Sí, registrar*.

Existe para evitar movimientos de caja registrados por error: un monto mal digitado o una salida
marcada como entrada se detecta antes de que afecte el cuadre de la sesión.

Trabaja junto con `pos_closing_validation`, del que depende: ese módulo lleva la cuenta de
movimientos permitidos por sesión, y este muestra en el mismo diálogo el aviso de **último
movimiento permitido** cuando corresponde.
