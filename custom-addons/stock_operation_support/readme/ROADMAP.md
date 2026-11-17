- **Conversión de unidades reescrita para Odoo 19 (19.0.1.4.2), validada solo por lectura y con
  pruebas unitarias sin ejecutar.** `services/line_matcher.py` ya no usa `uom.category_id`,
  `uom.product_uom_categ_unit`, `product.packaging_ids` ni `product.uom_po_id`: dos unidades son
  convertibles si comparten unidad de referencia (`uom.uom._has_common_reference`), los empaques son
  las unidades de `product.template.uom_ids` de la misma familia que la unidad del producto, y la
  unidad de compra que se le muestra a la IA es la del primer proveedor (`seller_ids.product_uom_id`)
  o, si no hay, la del producto. Falta correr las pruebas en una base 19 y comparar las conversiones
  con casos reales de 17 antes de activar el módulo (tarea E8 del plan
  `auditoria/PLAN_BLOQUEOS_2026-11-04.md`).
- **Cambio de comportamiento heredado de Odoo 19:** si el papel trae el nombre exacto de una unidad
  de empaque de Odoo (p. ej. «Caja x 24»), Odoo la convierte sin IA. En 17 un empaque no era unidad
  de medida y ese caso iba a la IA con respaldo del empaque.
- **Redondeo global de unidades:** en 19 todas las unidades redondean con la precisión
  «Product Unit» (en esta base, 4 decimales). La comparación exacta de la validación automática
  (`_exact_match_reason`) es por eso más estricta que en 17, donde cada unidad tenía su propio
  redondeo (0,01 por defecto).
