import logging
from itertools import groupby

from odoo import api, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        queue_enabled = (
            self.env.context.get('pos_inventory_queue')
            and self.env['pos.inventory.queue']._is_queue_enabled()
        )

        if not queue_enabled:
            return super()._create_picking_from_pos_order_lines(
                location_dest_id, lines, picking_type, partner,
            )

        Queue = self.env['pos.inventory.queue']
        defer = Queue._is_reservation_deferred()
        pickings = self.env['stock.picking']
        lines_by_picking = {}
        stockable_lines = lines.filtered(
            lambda l: l.product_id.type == 'consu'
            and not float_is_zero(l.qty, precision_rounding=l.product_id.uom_id.rounding)
        )
        if not stockable_lines:
            return pickings

        positive_lines = stockable_lines.filtered(lambda l: l.qty > 0)
        negative_lines = stockable_lines - positive_lines

        if positive_lines:
            location_id = picking_type.default_location_src_id.id
            positive_picking = self.env['stock.picking'].create(
                self._prepare_picking_vals(partner, picking_type, location_id, location_dest_id)
            )
            positive_picking._pos_queue_create_moves(positive_lines, defer)
            lines_by_picking[positive_picking.id] = positive_lines
            pickings |= positive_picking

        if negative_lines:
            refunded_order = negative_lines.mapped('refunded_orderline_id.order_id')
            if len(refunded_order) == 1:
                refundable_lines = refunded_order.lines.filtered(
                    lambda l: l.product_id.type == 'consu'
                    and not l.product_uom_id.is_zero(l.qty)
                )
                is_full_refund = all(
                    float_is_zero(
                        line.qty - line.refunded_qty,
                        precision_rounding=line.product_uom_id.rounding,
                    )
                    for line in refundable_lines
                )
                pickings_to_cancel = refunded_order.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel')
                )
                has_done_pickings = refunded_order.picking_ids.filtered(
                    lambda p: p.state == 'done'
                )

                if is_full_refund and pickings_to_cancel and not has_done_pickings:
                    pickings_to_cancel.action_cancel()
                    return pickings
                elif not is_full_refund and pickings_to_cancel and not has_done_pickings:
                    moves_to_reassign = self.env['stock.move']
                    for negative_line in negative_lines:
                        refunded_line = negative_line.refunded_orderline_id
                        moves = pickings_to_cancel.move_ids.filtered(
                            lambda m: m.product_id == refunded_line.product_id
                            and m.never_product_template_attribute_value_ids.ids
                                == refunded_line.attribute_value_ids.ids
                        )
                        cancel_qty = abs(negative_line.qty)
                        for move in moves:
                            new_qty = max(0, move.product_uom_qty - cancel_qty)
                            if float_is_zero(new_qty, precision_rounding=move.product_uom.rounding):
                                move._action_cancel()
                                move.unlink()
                            else:
                                move.product_uom_qty = new_qty
                                moves_to_reassign |= move
                    # Con la reserva diferida los moves siguen en borrador:
                    # basta con bajar la demanda, la cola reserva al validar.
                    moves_to_reassign.filtered(
                        lambda m: m.state != 'draft'
                    )._action_assign()
                    self.env.flush_all()
                    return pickings

            if picking_type.return_picking_type_id:
                return_picking_type = picking_type.return_picking_type_id
                return_location_id = return_picking_type.default_location_dest_id.id
            else:
                return_picking_type = picking_type
                return_location_id = picking_type.default_location_src_id.id

            negative_picking = self.env['stock.picking'].create(
                self._prepare_picking_vals(partner, return_picking_type, location_dest_id, return_location_id)
            )
            negative_picking._pos_queue_create_moves(negative_lines, defer)
            lines_by_picking[negative_picking.id] = negative_lines
            pickings |= negative_picking

        for picking in pickings:
            Queue.create({
                'picking_id': picking.id,
                'state': 'pending',
                'pos_line_ids': [(6, 0, lines_by_picking[picking.id].ids)],
            })
        self._trigger_queue_processing()

        return pickings

    def _pos_queue_create_moves(self, lines, defer):
        """Crea los moves del picking de una venta encolada.

        Con la reserva diferida solo se CREAN los moves (en borrador) con las
        mismas agrupaciones y valores que el core
        (_create_move_from_pos_order_lines de point_of_sale). Confirmar,
        reservar y asignar lotes lo hace la cola al validar
        (pos.inventory.queue._complete_deferred_picking), así la venta no
        toca stock_quant ni compite con otras cajas por el mismo quant.

        Sin reserva diferida delega en el core, como antes.
        """
        self.ensure_one()
        if not defer:
            return self._create_move_from_pos_order_lines(lines)

        def get_grouping_key(line):
            return (line.product_id.id, tuple(sorted(line.attribute_value_ids.ids)))

        move_vals = []
        grouped = groupby(sorted(lines, key=get_grouping_key), key=get_grouping_key)
        for _key, order_lines in grouped:
            order_lines = self.env['pos.order.line'].concat(*order_lines)
            move_vals.append(self._prepare_stock_move_vals(order_lines[0], order_lines))
        return self.env['stock.move'].create(move_vals)

    @api.model
    def _trigger_queue_processing(self):
        """Dispara el drenaje de la cola en el worker de cron (P0-2).

        Delega en el helper consolidado del modelo de cola para que el
        encolado y el presupuesto de tiempo del propio drenaje usen el
        mismo mecanismo (ir.cron._trigger, mejor-esfuerzo). Ver
        pos.inventory.queue._trigger_processing para la explicacion de por
        que _trigger es atomico con el commit de la venta.
        """
        self.env['pos.inventory.queue']._trigger_processing()
