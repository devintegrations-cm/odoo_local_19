## Limitaciones conocidas

- **El ranking usa la fecha UTC** para contar los días: la diferencia de unas horas no cambia el
  orden en la práctica.
- **Reemplaza la consulta estándar** de `pos.config.get_limited_partners_loading` (no la extiende):
  si Odoo cambia ese método en una versión futura, hay que revisar este módulo. Vuelve a agregar
  por su cuenta el cliente por defecto de `pw_pos_default_customer`.
