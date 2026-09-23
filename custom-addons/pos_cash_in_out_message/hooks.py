# pos_cash_in_out_message/hooks.py
def pre_init_rename_module(env):
    """
    Se ejecuta antes de instalar/cargar el módulo nuevo.
    Odoo 17/19 pasan `env` (no `cr`).
    Renombra el módulo predecesor cash_in_out_message → pos_cash_in_out_message
    para no dejar xmlids ni ir_module_module huérfanos.
    """
    cr = env.cr

    # 1) Migrar todos los xmlids del módulo viejo al nuevo
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'pos_cash_in_out_message'
         WHERE module = 'cash_in_out_message'
    """)

    # 2) Renombrar el registro del módulo en ir_module_module (si existiera con el nombre viejo)
    cr.execute("""
        UPDATE ir_module_module
           SET name = 'pos_cash_in_out_message'
         WHERE name = 'cash_in_out_message'
    """)

    # 3) (Idempotente) Ajustar dependencias registradas por nombre
    cr.execute("""
        UPDATE ir_module_module_dependency
           SET name = 'pos_cash_in_out_message'
         WHERE name = 'cash_in_out_message'
    """)
