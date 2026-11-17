from . import models


def post_init_hook(env):
    """Link the seeded rules to the analytic accounts that already exist in the database, by standard name."""
    env["clara.analytic.rule"].action_resolve_analytic_accounts()
