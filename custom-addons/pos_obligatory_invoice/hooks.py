# pos_obligatory_invoice/hooks.py
def pre_init_rename_module(env):
    """
    Se ejecuta antes de instalar/cargar el módulo nuevo.
    Odoo 17/19 pasan `env` (no `cr`).
    Renombra el módulo predecesor obligatory_invoice_msg → pos_obligatory_invoice
    para no dejar xmlids ni ir_module_module huérfanos.
    """
    cr = env.cr

    # 1) Migrar todos los xmlids del módulo viejo al nuevo
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'pos_obligatory_invoice'
         WHERE module = 'obligatory_invoice_msg'
    """)

    # 2) Renombrar el registro del módulo en ir_module_module (si existiera con el nombre viejo)
    cr.execute("""
        UPDATE ir_module_module
           SET name = 'pos_obligatory_invoice'
         WHERE name = 'obligatory_invoice_msg'
    """)

    # 3) (Idempotente) Ajustar dependencias registradas por nombre
    cr.execute("""
        UPDATE ir_module_module_dependency
           SET name = 'pos_obligatory_invoice'
         WHERE name = 'obligatory_invoice_msg'
    """)
