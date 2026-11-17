# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Claves auxiliares que se usan solo dentro de este módulo para armar las líneas
# y que no deben llegar a account.move.line.create().
_AUX_KEYS = ('reward_product_tag_target_id', 'target_order_line')


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _maps_order_line(self, oline, qty=None, taxes=None, is_reward=False):
        """Copia los vals de una línea de factura cambiando cantidad, impuestos y
        la marca de premio. Misma semántica que en 17 (qty/taxes falsy = se conservan).
        """
        oline = {k: v for k, v in oline.items() if k not in _AUX_KEYS}
        upoline = {
            'tax_ids': taxes if taxes else oline.get('tax_ids'),
            'quantity': qty if qty else oline.get('quantity'),
            'invoice_reward_line': is_reward,
        }
        # 19: extra_tax_data describe la línea base original (precio/cantidad). Al
        # cambiar cantidad o impuestos deja de corresponder: se descarta para que
        # account.move.line recalcule impuestos desde price_unit/quantity/tax_ids.
        if (qty or taxes) and 'extra_tax_data' in oline:
            oline.pop('extra_tax_data')
        return (0, None, {**oline, **upoline})

    def _pair_invoice_lines_with_pos_lines(self, invoice_lines):
        """Empareja cada comando de línea de factura con su pos.order.line de origen.

        En 17 se hacía con zip(self.lines, invoice_lines). En 19 el núcleo intercala
        notas (display_type 'line_note': descuento de lista de precios, customer_note,
        general_customer_note), así que el zip queda corrido. Aquí se recorre la lista
        en el mismo orden en que la arma point_of_sale (por pedido, por línea) y se
        saltan las notas. Las secciones de combo ('line_section') sí corresponden a
        una línea POS (la línea padre del combo).

        :return: lista de (pos.order.line, vals) o None si no se pudo emparejar.
        """
        pos_lines = [line for order in self for line in order.lines]
        pairs = []
        idx = 0
        for command in invoice_lines:
            vals = command[2]
            if vals.get('display_type') == 'line_note':
                continue
            if idx >= len(pos_lines):
                return None
            pos_line = pos_lines[idx]
            idx += 1
            # Verificación: una línea de producto debe traer el mismo producto.
            if not vals.get('display_type') and vals.get('product_id') != pos_line.product_id.id:
                return None
            pairs.append((pos_line, vals))
        if idx != len(pos_lines):
            return None
        return pairs

    def _prepare_invoice_lines(self, move_type):
        invoice_lines = super()._prepare_invoice_lines(move_type)
        if not any(line.is_reward_line for line in self.lines):
            return invoice_lines

        pairs = self._pair_invoice_lines_with_pos_lines(invoice_lines)
        if pairs is None:
            _logger.warning(
                "POS %s: no se pudieron emparejar las líneas de factura con las líneas POS; "
                "se factura sin el tratamiento de premios.", self.mapped('name'))
            return invoice_lines

        # Marca de premio sobre los vals originales (se modifican en sitio, igual que en 17:
        # así la lista original ya lleva invoice_reward_line si se devuelve tal cual).
        vals_by_pos_line = {}
        for pos_line, vals in pairs:
            vals['invoice_reward_line'] = pos_line.is_reward_line
            if pos_line.reward_related_order_line_id:
                vals['target_order_line'] = pos_line.reward_related_order_line_id
            vals_by_pos_line[pos_line.id] = vals

        reward_pos_lines = [pl for pl, _vals in pairs if pl.is_reward_line]
        target_ids = [pl.reward_related_order_line_id for pl in reward_pos_lines]

        # Camino "sin enlace" (17): si no todas las líneas de premio están enlazadas a una
        # línea de producto del pedido, se factura como lo arma el núcleo, solo con la
        # marca invoice_reward_line (account.move pone en 0 el precio de esas líneas).
        # 19 agrega dos salvaguardas que en 17 terminaban en excepción (KeyError /
        # campo inválido): dos premios sobre la misma línea, o una línea destino ausente.
        if (
            not all(target_ids)
            or len(set(target_ids)) != len(target_ids)
            or any(t not in vals_by_pos_line for t in target_ids)
        ):
            _logger.info(
                "POS %s: premios sin enlace completo (%s de %s); se marcan sin reestructurar.",
                self.mapped('name'), len([t for t in target_ids if t]), len(target_ids))
            return [
                (cmd[0], cmd[1], {k: v for k, v in cmd[2].items() if k not in _AUX_KEYS})
                for cmd in invoice_lines
            ]

        # Camino "con enlace" (17): la línea del producto destino se parte en
        #   - la cantidad pagada (qty producto - qty premio), si queda algo, y
        #   - la cantidad regalada, con el producto destino, marcada como premio y con los
        #     impuestos del producto de la línea de premio (producto de descuento de lealtad).
        # La línea de premio original (producto de descuento, precio negativo) se elimina.
        new_invoice_lines = []
        lines_to_delete = set()
        for reward_line in reward_pos_lines:
            reward_vals = vals_by_pos_line[reward_line.id]
            target_id = reward_line.reward_related_order_line_id
            target_vals = vals_by_pos_line[target_id]
            qty_reward = reward_vals['quantity']
            qty_product = target_vals['quantity']
            qty_remaining = qty_product - qty_reward
            if qty_remaining > 0:
                new_invoice_lines.append(
                    self._maps_order_line(target_vals, qty=qty_remaining, is_reward=False))
            # 17: [(6, 0, [product_id.taxes_id.id])]. Se usa .ids (evita singleton con
            # varios impuestos y [False] sin impuestos) filtrado por compañía del pedido.
            reward_taxes = reward_line.product_id.taxes_id._filter_taxes_by_company(
                reward_line.order_id.company_id)
            new_invoice_lines.append(self._maps_order_line(
                target_vals, qty=qty_reward, taxes=[(6, 0, reward_taxes.ids)], is_reward=True))
            lines_to_delete.add(reward_line.id)
            lines_to_delete.add(target_id)

        # Se conservan en su orden las demás líneas (incluidas notas y secciones) y al
        # final las líneas nuevas, como en 17.
        deleted_vals_ids = {id(vals_by_pos_line[pl_id]) for pl_id in lines_to_delete}
        kept_lines = [
            (cmd[0], cmd[1], {k: v for k, v in cmd[2].items() if k not in _AUX_KEYS})
            for cmd in invoice_lines
            if id(cmd[2]) not in deleted_vals_ids
        ]
        return kept_lines + new_invoice_lines
