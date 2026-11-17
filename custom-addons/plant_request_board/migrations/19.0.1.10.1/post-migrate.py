import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# the groups of 1.10.0, then the records they hung from (Odoo 19 privilege, Odoo 17 module category)
PLANT_XMLIDS = (
    "plant_request_board.group_plant_manager",
    "plant_request_board.group_plant_user",
    "plant_request_board.privilege_plant",
    "plant_request_board.module_category_plant",
)


def migrate(cr, version):
    """1.10.1: the module uses the standard Inventory groups. The Planta groups of 1.10.0 are removed and nobody
    loses a right: whoever had Inventario / Usuario only through «Planta / Usuario» keeps it explicitly (Odoo 19
    stores only the direct groups of a user, so the implied one would go with the group), and the members of
    «Planta / Jefe» who are not Inventario / Administrador are listed in the log for the administrator to decide;
    they are never promoted automatically."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Users = env["res.users"].with_context(active_test=False)
    Groups = env["res.groups"]
    users_field = "group_ids" if "group_ids" in Users._fields else "groups_id"   # Odoo 19 renamed groups_id
    implied_field = "all_implied_ids" if "all_implied_ids" in Groups._fields else "trans_implied_ids"   # idem
    stock_user = env.ref("stock.group_stock_user", raise_if_not_found=False)
    stock_manager = env.ref("stock.group_stock_manager", raise_if_not_found=False)
    manager_group = env.ref("plant_request_board.group_plant_manager", raise_if_not_found=False)
    user_group = env.ref("plant_request_board.group_plant_user", raise_if_not_found=False)
    planta = (manager_group or Groups) | (user_group or Groups)

    def keeps(user, group):
        """Whether the user still has the group once the Planta groups are gone: directly or through another."""
        direct = user[users_field] - planta
        return group in (direct | direct[implied_field])

    if planta and stock_user:
        members = Users.search([(users_field, "in", planta.ids)])
        losing = members.filtered(lambda u: not keeps(u, stock_user))
        if losing:
            losing.write({users_field: [(4, stock_user.id)]})
            _logger.info("plant_request_board 1.10.1: %s user(s) keep Inventario / Usuario explicitly: %s",
                         len(losing), ", ".join(sorted(losing.mapped("login"))))
    if manager_group and stock_manager:
        bosses = Users.search([(users_field, "in", manager_group.id)])
        pending = bosses.filtered(lambda u: not keeps(u, stock_manager))
        if pending:
            _logger.warning(
                "plant_request_board 1.10.1: %s user(s) were «Planta / Jefe» without Inventario / Administrador "
                "and keep the board only, not the plant configuration, until an administrator grants it: %s",
                len(pending), ", ".join(sorted(pending.mapped("login"))))
    removed = []
    for xmlid in PLANT_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.unlink()   # the ir.model.data row goes with it
            removed.append(xmlid.split(".")[-1])
    _logger.info("plant_request_board 1.10.1: Planta groups removed (%s); the module now uses "
                 "stock.group_stock_user and stock.group_stock_manager", ", ".join(removed) or "none existed")
