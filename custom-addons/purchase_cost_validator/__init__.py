from . import models


def post_init_hook(env):
    """The validator only looks at what is created from now on: orders and receipts that already exist stay as they are."""
    env["purchase.order.line"]._cost_check_set_start_if_missing()
