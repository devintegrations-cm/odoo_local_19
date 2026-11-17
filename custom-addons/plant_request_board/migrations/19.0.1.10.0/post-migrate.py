import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """1.10.0: the Anthropic key outside the database (and the two Planta groups that 1.10.1 removed again in
    favour of the standard Inventory groups: on a database that jumps straight to 1.10.1 the groups do not exist
    and the group steps below do nothing).

    - The Anthropic key is no longer read from ir.config_parameter: the stored value is removed and the log says
      where it goes (PLANT_ANTHROPIC_API_KEY in the environment, or plant_anthropic_api_key in odoo.conf)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    user_group = env.ref("plant_request_board.group_plant_user", raise_if_not_found=False)
    manager_group = env.ref("plant_request_board.group_plant_manager", raise_if_not_found=False)
    stock_manager = env.ref("stock.group_stock_manager", raise_if_not_found=False)
    Users = env["res.users"]
    users_field = "group_ids" if "group_ids" in Users._fields else "groups_id"   # Odoo 19 renamed groups_id
    staff = Users.browse(list(env["res.config.settings"]._plant_staff_ids())).exists()
    if user_group and staff:
        staff.write({users_field: [(4, user_group.id)]})
    managers = Users
    if manager_group and stock_manager:
        managers = Users.search([(users_field, "in", stock_manager.id), ("share", "=", False)])
        if managers:
            managers.write({users_field: [(4, manager_group.id)]})
    params = env["ir.config_parameter"].sudo()
    had_key = bool((params.get_param("plant_request_board.anthropic_api_key") or "").strip())
    params.search([("key", "=", "plant_request_board.anthropic_api_key")]).unlink()
    _logger.info("plant_request_board 1.10.0: %s plant users, %s plant managers; Anthropic key %s ir.config_parameter — set PLANT_ANTHROPIC_API_KEY in the environment or plant_anthropic_api_key in odoo.conf",
                 len(staff), len(managers), "removed from" if had_key else "was not in")
