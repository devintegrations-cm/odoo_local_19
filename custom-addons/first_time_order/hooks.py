# first_time_order/hooks.py
def pre_init_rename_module(env):
    """
    Se ejecuta antes de instalar/cargar el módulo nuevo.
    Odoo 17 pasa `env` (no `cr`).
    """
    cr = env.cr

    # 1) Migrar todos los xmlids del módulo viejo al nuevo
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'first_time_order'
         WHERE module = 'firstTimeOrder'
    """)

    # 2) Renombrar el registro del módulo en ir_module_module (si existiera con el nombre viejo)
    cr.execute("""
        UPDATE ir_module_module
           SET name = 'first_time_order'
         WHERE name = 'firstTimeOrder'
    """)

    # 3) (Idempotente) Ajustar dependencias registradas por nombre
    cr.execute("""
        UPDATE ir_module_module_dependency
           SET name = 'first_time_order'
         WHERE name = 'firstTimeOrder'
    """)
