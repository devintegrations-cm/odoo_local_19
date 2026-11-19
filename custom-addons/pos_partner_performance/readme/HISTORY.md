## 19.0.1.0.0

- Primera versión: clientes frecuentes por caja y últimos N días, con su activación y los días
  configurables por caja (0 = ranking estándar; no admite negativos).
- El cliente por defecto de la caja se agrega solo en la primera página de clientes. Con
  `pw_pos_default_customer` se agregaba en todas: cada página traía un cliente de más, el POS
  corría la paginación en uno y se saltaba un cliente por página al bajar en la lista.
