from unittest.mock import MagicMock, call, patch

import psycopg2
from psycopg2 import errors as psycopg2_errors

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestPosInventoryQueue(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Queue = self.env['pos.inventory.queue']
        self.Picking = self.env['stock.picking']

        self.warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', self.warehouse.id),
        ], limit=1)

        self.product = self.env['product.product'].create({
            'name': 'Test Queue Product',
            'type': 'consu',
            'is_storable': True,
            'list_price': 10.0,
        })

        self.source_location = (
            self.picking_type.default_location_src_id
            or self.warehouse.lot_stock_id
        )
        self.dest_location = (
            self.picking_type.default_location_dest_id
            or self.env['stock.warehouse']._get_partner_locations()[0]
        )

        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'location_id': self.source_location.id,
            'inventory_quantity': 100.0,
        }).action_apply_inventory()

    def _create_picking(self, origin=None, product=None):
        product = product or self.product
        picking = self.Picking.create({
            'picking_type_id': self.picking_type.id,
            'location_id': self.source_location.id,
            'location_dest_id': self.dest_location.id,
            'origin': origin or 'TEST',
        })
        self.env['stock.move'].create({
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.source_location.id,
            'location_dest_id': self.dest_location.id,
        })
        picking.action_confirm()
        picking.move_ids.picked = True
        return picking

    def test_sequence_generation(self):
        item1 = self.Queue.create({
            'picking_id': self._create_picking('SEQ-1').id,
        })
        item2 = self.Queue.create({
            'picking_id': self._create_picking('SEQ-2').id,
        })

        self.assertNotEqual(item1.name, 'New')
        self.assertNotEqual(item2.name, 'New')
        self.assertNotEqual(item1.name, item2.name)

    def test_duplicate_picking_prevention(self):
        picking = self._create_picking('DUP-1')
        item1 = self.Queue.create({'picking_id': picking.id})
        item2 = self.Queue.create({'picking_id': picking.id})

        self.assertEqual(item1.id, item2.id)
        self.assertEqual(len(self.Queue.search(
            [('picking_id', '=', picking.id)]
        )), 1)

    def test_default_state(self):
        picking = self._create_picking('STATE-1')
        item = self.Queue.create({'picking_id': picking.id})
        self.assertEqual(item.state, 'pending')

    def test_retry_from_failed_permanent(self):
        picking = self._create_picking('RETRY-1')
        item = self.Queue.create({'picking_id': picking.id})
        item.sudo().write({
            'state': 'failed_permanent',
            'retry_count': 5,
            'error_message': 'Test error',
            'next_retry_date': '2099-01-01 00:00:00',
        })

        item.action_retry()
        self.env.invalidate_all()
        item = self.Queue.search([('picking_id', '=', picking.id)])
        self.assertEqual(item.state, 'pending')
        self.assertEqual(item.retry_count, 0)
        self.assertFalse(item.error_message)
        self.assertFalse(item.next_retry_date)

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            self.Queue._process_queue()
        self.env.invalidate_all()
        item = self.Queue.search([('picking_id', '=', picking.id)])
        self.assertEqual(item.state, 'done')

    def test_claim_respects_future_next_retry_date(self):
        """(P0-8) Un item 'failed' con next_retry_date en el futuro NO se
        reclama: el backoff diferido debe respetarse hasta que venza."""
        picking = self._create_picking('NRET-FUT')
        item = self.Queue.create({'picking_id': picking.id})
        item.sudo().write({
            'state': 'failed',
            'retry_count': 2,
            'next_retry_date': '2099-01-01 00:00:00',
        })
        self.env.cr.flush()

        claimed = self.Queue._claim_next_item()
        self.env.invalidate_all()
        self.assertIsNone(
            claimed,
            'failed item con next_retry_date futuro no debe reclamarse',
        )

    def test_claim_after_next_retry_date_passed(self):
        """(P0-8) Un item 'failed' con next_retry_date vencido SI se
        reclama (el backoff expiro)."""
        picking = self._create_picking('NRET-PAST')
        item = self.Queue.create({'picking_id': picking.id})
        item.sudo().write({
            'state': 'failed',
            'retry_count': 2,
            'next_retry_date': '2000-01-01 00:00:00',
        })
        self.env.cr.flush()

        claimed = self.Queue._claim_next_item()
        self.env.invalidate_all()
        self.assertIsNotNone(
            claimed,
            'failed item con next_retry_date vencido debe reclamarse',
        )

    def test_retry_ignores_non_failed(self):
        picking = self._create_picking('RETRY-2')
        item = self.Queue.create({'picking_id': picking.id})

        item.action_retry()

        self.assertEqual(item.state, 'pending')
        self.assertEqual(item.retry_count, 0)

    def test_claim_next_item(self):
        p1 = self._create_picking('CLAIM-1')
        p2 = self._create_picking('CLAIM-2')
        self.Queue.create({'picking_id': p1.id})
        self.Queue.create({'picking_id': p2.id})

        item_id = self.Queue._claim_next_item()
        self.assertIsNotNone(item_id)

        self.env.invalidate_all()

        item = self.Queue.browse(item_id)
        self.assertEqual(item.state, 'processing')

    def test_claim_returns_none_when_empty(self):
        item_id = self.Queue._claim_next_item()
        self.assertIsNone(item_id)

    def test_process_queue_single_item(self):
        picking = self._create_picking('PROC-1')
        self.Queue.create({'picking_id': picking.id})

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            self.Queue._process_queue()

        self.env.invalidate_all()

        item = self.Queue.search(
            [('picking_id', '=', picking.id)]
        )
        self.assertEqual(item.state, 'done')
        self.assertFalse(item.error_message)

    def test_process_queue_preserves_order(self):
        p1 = self._create_picking('ORDER-1')
        p2 = self._create_picking('ORDER-2')
        p3 = self._create_picking('ORDER-3')
        self.Queue.create({'picking_id': p1.id})
        self.Queue.create({'picking_id': p2.id})
        self.Queue.create({'picking_id': p3.id})

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            self.Queue._process_queue()

        self.env.invalidate_all()

        items = self.Queue.search([
            ('picking_id', 'in', [p1.id, p2.id, p3.id]),
        ], order='sequence, id')

        for item in items:
            self.assertEqual(item.state, 'done')

    def test_claim_pending_with_max_retries(self):
        """Regression: pending items with retry_count >= MAX_RETRIES
        must still be claimed by the cron."""
        picking = self._create_picking('MAXRETRY-1')
        item = self.Queue.create({'picking_id': picking.id})

        item.sudo().write({
            'state': 'pending',
            'retry_count': self.Queue.MAX_RETRIES,
        })

        self.env.cr.flush()

        item_id = self.Queue._claim_next_item()
        self.assertIsNotNone(
            item_id,
            'pending item with retry_count=MAX_RETRIES '
            'should be claimable',
        )

        self.env.invalidate_all()

        item = self.Queue.browse(item_id)
        self.assertEqual(item.state, 'processing')

    def test_claim_failed_with_max_retries_excluded(self):
        """failed items with retry_count >= MAX_RETRIES must NOT be
        claimed — they represent logic errors, not contention."""
        picking = self._create_picking('MAXRETRY-2')
        item = self.Queue.create({'picking_id': picking.id})

        item.sudo().write({
            'state': 'failed',
            'retry_count': self.Queue.MAX_RETRIES,
        })

        self.env.cr.flush()

        item_id = self.Queue._claim_next_item()
        self.assertIsNone(
            item_id,
            'failed item with retry_count=MAX_RETRIES '
            'should NOT be claimable',
        )

    def test_process_item_in_new_cursor_already_done(self):
        """Si el picking ya está done (reclamo de stale), el item se
        marca done sin re-ejecutar _action_done() para no duplicar
        quants."""
        picking = self._create_picking('IDEMP-1')
        item = self.Queue.create({'picking_id': picking.id})

        picking.action_confirm()
        picking.move_ids.picked = True
        picking._action_done()
        self.assertEqual(picking.state, 'done')

        item.sudo().write({
            'state': 'processing',
            'start_date': '2026-01-01 00:00:00',
        })

        with self.enter_registry_test_mode():
            status = self.Queue._process_item_in_new_cursor(item.id)
        self.env.invalidate_all()

        self.assertEqual(status, 'done')
        item = self.Queue.browse(item.id)
        self.assertEqual(item.state, 'done')
        self.assertFalse(item.error_message)

    def test_cron_cleanup_done_items(self):
        """El cron de limpieza elimina items done más antiguos que N
        días y deja los recientes."""
        from datetime import timedelta

        p_old = self._create_picking('CLEAN-OLD')
        p_new = self._create_picking('CLEAN-NEW')
        item_old = self.Queue.create({'picking_id': p_old.id})
        item_new = self.Queue.create({'picking_id': p_new.id})

        now = fields.Datetime.now()
        old_date = (now - timedelta(days=60)).strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        new_date = now.strftime('%Y-%m-%d %H:%M:%S')

        self.env.cr.execute(
            "UPDATE pos_inventory_queue "
            "SET state = 'done', done_date = %s "
            "WHERE id = %s",
            (old_date, item_old.id),
        )
        self.env.cr.execute(
            "UPDATE pos_inventory_queue "
            "SET state = 'done', done_date = %s "
            "WHERE id = %s",
            (new_date, item_new.id),
        )

        self.Queue._cron_cleanup_done_items(days=30)
        self.env.invalidate_all()

        self.assertFalse(
            item_old.exists(),
            'Old done item should be cleaned up',
        )
        self.assertTrue(
            item_new.exists(),
            'Recent done item should remain',
        )

    def test_process_session_items(self):
        """_process_session_items procesa los ítems pendientes de una
        sesión y devuelve los que siguen sin done."""
        session, order, picking, item = self._make_session_item('SESSION-1')

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(picking.state, 'done')
        self.assertEqual(item.state, 'done')
        self.assertEqual(len(remaining), 0)

    def test_stale_processing_reclaim(self):
        """Items en 'processing' con start_date > 5 minutos se reclaman
        como stale (el claim los trata como pending)."""
        picking = self._create_picking('STALE-1')
        item = self.Queue.create({'picking_id': picking.id})

        from datetime import timedelta
        stale_time = (
            fields.Datetime.now() - timedelta(minutes=10)
        ).strftime('%Y-%m-%d %H:%M:%S')

        self.env.cr.execute(
            "UPDATE pos_inventory_queue "
            "SET state = 'processing', start_date = %s "
            "WHERE id = %s",
            (stale_time, item.id),
        )
        self.env.cr.flush()

        item_id = self.Queue._claim_next_item()
        self.env.invalidate_all()

        self.assertIsNotNone(
            item_id,
            'stale processing item should be reclaimable',
        )
        claimed = self.Queue.browse(item_id)
        self.assertEqual(claimed.state, 'processing')
        self.assertEqual(claimed.id, item.id)

    def test_format_error_output(self):
        """_format_error incluye el tipo de excepción y trunca con '...'
        cuando el mensaje supera 4000 caracteres."""
        import psycopg2

        short_exc = psycopg2.OperationalError('short error')
        result = self.Queue._format_error(short_exc)
        self.assertIn('OperationalError', result)
        self.assertIn('short error', result)
        self.assertFalse(result.endswith('...'))

        long_msg = 'x' * 5000
        long_exc = psycopg2.OperationalError(long_msg)
        result = self.Queue._format_error(long_exc)
        self.assertTrue(len(result) <= 4000)
        self.assertTrue(result.endswith('...'))

    def test_action_trigger_processing_returns_notification(self):
        """action_trigger_processing devuelve una notificación client."""
        result = self.Queue.action_trigger_processing()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')

    # ------------------------------------------------------------------
    # ALERTA DE FALLO PERMANENTE (PIQ-2)
    # ------------------------------------------------------------------

    def _make_failed_permanent(self, origin):
        """Item en estado 'failed_permanent' con picking asociado."""
        picking = self._create_picking(origin)
        item = self.Queue.create({'picking_id': picking.id})
        item.sudo().write({
            'state': 'failed_permanent',
            'retry_count': self.Queue.MAX_RETRIES,
            'error_message': 'Error simulado para la alerta',
        })
        return item

    @staticmethod
    def _alerts_for(item, user=None):
        """Actividades de alerta creadas para el picking del item (la
        actividad se ancla al picking: pos.inventory.queue no hereda
        mail.thread). `user` acota a un usuario concreto para no depender
        de los usuarios demo de la base de tests."""
        domain = [
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', item.picking_id.id),
            ('active', '=', True),
        ]
        activities = item.env['mail.activity'].search(domain)
        if user:
            activities = activities.filtered(lambda a: a.user_id == user)
        return activities

    def test_notify_permanent_failure_creates_activity(self):
        """(PIQ-2) _notify_permanent_failure crea la actividad para el
        gestor de inventario.

        Regresión de dos bugs encadenados, ambos tragados por el
        except externo del metodo:
        1. el dominio usaba `res.users.groups_id` (existia en Odoo 17;
           en Odoo 19 el campo es `group_ids`) -> ValueError.
        2. la actividad se anclaba a `pos.inventory.queue`, que no hereda
           mail.thread -> mail.activity.create lanza AttributeError en
           message_notify()/message_subscribe().
        """
        manager = new_test_user(
            self.env,
            login='piq_stock_manager',
            groups='base.group_user,stock.group_stock_manager',
        )
        item = self._make_failed_permanent('ALERT-1')

        with self.enter_registry_test_mode():
            self.Queue._notify_permanent_failure(item.id)
        self.env.invalidate_all()

        alerts = self._alerts_for(item, manager)
        self.assertEqual(
            len(alerts), 1,
            'no se creó la alerta de fallo permanente',
        )
        self.assertEqual(
            alerts.activity_type_id,
            self.env.ref('mail.mail_activity_data_todo'),
        )
        self.assertTrue(alerts.active)
        self.assertTrue(alerts.automated)
        self.assertIn('fallo permanente', alerts.summary or '')
        self.assertEqual(alerts.res_id, item.picking_id.id)
        self.assertIn(item.name, alerts.note or '')

    def test_notify_permanent_failure_is_idempotent(self):
        """(PIQ-2) Un segundo intento (p. ej. el drenaje en línea del
        cierre de sesión) NO duplica la actividad del usuario."""
        manager = new_test_user(
            self.env,
            login='piq_stock_manager_idem',
            groups='base.group_user,stock.group_stock_manager',
        )
        item = self._make_failed_permanent('ALERT-2')

        with self.enter_registry_test_mode():
            self.Queue._notify_permanent_failure(item.id)
        self.env.invalidate_all()
        self.assertEqual(len(self._alerts_for(item, manager)), 1)

        with self.enter_registry_test_mode():
            self.Queue._notify_permanent_failure(item.id)
        self.env.invalidate_all()
        self.assertEqual(
            len(self._alerts_for(item, manager)), 1,
            'el reintento duplicó la alerta',
        )

    def test_notify_permanent_failure_skips_non_managers(self):
        """(PIQ-2) Un usuario interno sin el rol de gestor de inventario
        no recibe la alerta."""
        plain = new_test_user(
            self.env,
            login='piq_plain_user',
            groups='base.group_user',
        )
        item = self._make_failed_permanent('ALERT-3')

        with self.enter_registry_test_mode():
            self.Queue._notify_permanent_failure(item.id)
        self.env.invalidate_all()

        self.assertFalse(
            self._alerts_for(item, plain),
            'un usuario sin stock.group_stock_manager no debe alertarse',
        )

    # ------------------------------------------------------------------
    # COSTO FIFO/AVCO TRAS VALIDAR EL PICKING (PIQ-1)
    # ------------------------------------------------------------------

    def _make_session(self):
        """Sesión POS abierta para los tests de sesión/orden."""
        pos_config = self.env['pos.config'].search([], limit=1)
        if not pos_config:
            self.skipTest('No POS config available for session test')

        existing_sessions = self.env['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state', '!=', 'closed'),
        ])
        if existing_sessions:
            existing_sessions.action_pos_session_closing_control()
            self.env.cr.flush()

        return self.env['pos.session'].create({
            'config_id': pos_config.id,
            'user_id': self.env.uid,
        })

    def _make_order(self, session, product, price=150.0):
        """Orden POS de una línea en la sesión dada."""
        return self.env['pos.order'].create({
            'session_id': session.id,
            'user_id': self.env.uid,
            'amount_tax': 0.0,
            'amount_total': price,
            'amount_paid': price,
            'amount_return': 0.0,
            'lines': [(0, 0, {
                'product_id': product.id,
                'name': product.display_name,
                'qty': 1,
                'price_unit': price,
                'price_subtotal': price,
                'price_subtotal_incl': price,
            })],
        })

    def _make_session_item(
        self,
        origin,
        product=None,
        item_state=None,
        picking_done=False,
        retry_count=0,
    ):
        """Sesión POS con una orden suya, su picking encolado y el ítem de
        cola en el estado pedido."""
        session = self._make_session()
        product = product or self.product
        order = self._make_order(session, product)
        picking = self._create_picking(origin, product=product)
        picking.write({
            'pos_order_id': order.id,
            'pos_session_id': session.id,
        })
        if picking_done:
            picking._action_done()
        item = self.Queue.create({'picking_id': picking.id})
        if item_state:
            item.sudo().write({
                'state': item_state,
                'retry_count': retry_count,
                'error_message': 'Error simulado (PIQ-4)',
            })
        return session, order, picking, item

    def _make_order_with_cost(self, cost_method='average'):
        """Orden POS de una línea sobre un producto con el costo dado, con
        su picking encolado. Devuelve (order, picking, line)."""
        category = self.env['product.category'].create({
            'name': 'PIQ Cost Test %s' % cost_method,
            'property_cost_method': cost_method,
        })
        product = self.env['product.product'].create({
            'name': 'PIQ Cost Product %s' % cost_method,
            'type': 'consu',
            'is_storable': True,
            'categ_id': category.id,
            'standard_price': 100.0,
            'list_price': 150.0,
        })
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': self.source_location.id,
            'inventory_quantity': 50.0,
        }).action_apply_inventory()

        session = self._make_session()
        order = self._make_order(session, product)
        picking = self._create_picking(
            'COST-%s' % cost_method, product=product)
        picking.write({
            'pos_order_id': order.id,
            'pos_session_id': session.id,
        })
        return order, picking, order.lines

    def test_recompute_cost_after_queue_fifo_avco(self):
        """(PIQ-1) El core calcula el costo FIFO/AVCO con el picking sin
        validar (move.value = 0 y quantity = 0) y lo clava en 0 con
        is_total_cost_computed=True; el recálculo de la cola lo recupera.

        move.value se fija a mano: es lo que deja la valuación
        automatizada (real_time) en producción, y con la valuación
        periódica de la base de tests no se puebla solo.
        """
        order, picking, line = self._make_order_with_cost('average')

        # Igual que _process_saved_order(): recálculo con moves sin validar.
        order._compute_total_cost_in_real_time()
        self.assertTrue(line.is_total_cost_computed)
        self.assertEqual(
            line.total_cost, 0.0,
            'regresión: el costo FIFO/AVCO queda en 0',
        )

        picking._action_done()
        picking.move_ids.write({'value': 1000.0})

        self.assertTrue(
            self.env['pos.order']._recompute_cost_after_queue(picking)
        )
        self.assertEqual(line.total_cost, 1000.0)
        self.assertTrue(line.is_total_cost_computed)
        self.assertNotEqual(
            line.margin, 0.0,
            'margin debe recalcularse con el costo nuevo',
        )

    def test_recompute_cost_after_queue_standard_untouched(self):
        """(PIQ-1) Un producto standard no se toca: su costo sale de
        standard_price y ya es correcto con el cálculo del core."""
        order, picking, line = self._make_order_with_cost('standard')

        order._compute_total_cost_in_real_time()
        self.assertEqual(line.total_cost, 100.0)

        picking._action_done()
        self.assertFalse(
            self.env['pos.order']._recompute_cost_after_queue(picking)
        )
        self.assertEqual(line.total_cost, 100.0)
        self.assertTrue(line.is_total_cost_computed)

    def test_recompute_cost_after_queue_without_order(self):
        """(PIQ-1) Un picking sin orden POS no lanza ni hace nada."""
        picking = self._create_picking('COST-NOORDER')
        self.assertFalse(
            self.env['pos.order']._recompute_cost_after_queue(picking)
        )

    def test_process_item_recomputes_cost(self):
        """(PIQ-1) El drenaje del ítem recalcula el costo solo, sin que
        nadie llame al helper a mano (cableado en las dos ramas de
        _process_item_in_new_cursor).

        El costo de salida sale del move valorado (move.value = 100, su
        capa FIFO de entrada), no del 0 que deja el cálculo del core
        sobre moves sin validar.
        """
        order, picking, line = self._make_order_with_cost('fifo')
        item = self.Queue.create({'picking_id': picking.id})

        order._compute_total_cost_in_real_time()
        self.assertEqual(
            line.total_cost, 0.0,
            'regresión: el costo FIFO queda en 0',
        )

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            self.Queue._process_queue()
        self.env.invalidate_all()

        self.assertEqual(picking.state, 'done')
        self.assertEqual(item.state, 'done')
        self.assertEqual(
            picking.move_ids.value, 100.0,
            'el move sale valorado a su costo FIFO real',
        )
        self.assertEqual(
            line.total_cost, picking.move_ids.value,
            'el procesamiento del ítem no recalculó el costo desde '
            'move.value',
        )
        self.assertTrue(line.is_total_cost_computed)

    # ------------------------------------------------------------------
    # CIERRE DE SESIÓN CON PICKINGS YA VALIDADOS (PIQ-4)
    # ------------------------------------------------------------------

    def test_session_close_marks_manual_validated_picking_done(self):
        """(PIQ-4) Si alguien validó el picking a mano desde Inventario,
        el ítem queda 'pending' y la guarda del cierre lo reconcilia a
        'done' en vez de saltarlo (antes bloqueaba hasta un Retry)."""
        session, order, picking, item = self._make_session_item(
            'PIQ4-1', picking_done=True)
        self.assertEqual(item.state, 'pending')

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(item.state, 'done')
        self.assertNotIn(item, remaining)
        self.assertEqual(picking.state, 'done')

    def test_session_close_reconciles_failed_permanent_done_picking(self):
        """(PIQ-4) Un 'failed_permanent' cuyo picking ya se validó a mano
        se reconcilia a 'done' (sin revalidar) y deja de bloquear el
        cierre."""
        session, order, picking, item = self._make_session_item(
            'PIQ4-2',
            item_state='failed_permanent',
            retry_count=self.Queue.MAX_RETRIES,
            picking_done=True,
        )

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(item.state, 'done')
        self.assertEqual(item.retry_count, 0)
        self.assertFalse(item.error_message)
        self.assertNotIn(item, remaining)

    def test_session_close_blocks_unresolved_failed_permanent(self):
        """(PIQ-4) Si la causa del 'failed_permanent' sigue sin
        resolverse, el cierre lo reintenta, vuelve a fallar y el ítem
        sigue en la lista que bloquea el cierre."""
        session, order, picking, item = self._make_session_item(
            'PIQ4-3',
            item_state='failed_permanent',
            retry_count=self.Queue.MAX_RETRIES,
        )

        with patch.object(
            type(picking), '_action_done',
            side_effect=UserError('fallo simulado de validación'),
        ), patch.object(
            type(self.Queue), '_notify_permanent_failure',
        ), self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(item.state, 'failed_permanent')
        self.assertEqual(
            item.retry_count, self.Queue.MAX_RETRIES,
            'el contador de ciclos no debe crecer sin tope',
        )
        self.assertIn(item, remaining)

    def test_session_close_processes_failed_retriable_items(self):
        """(PIQ-4) Un ítem 'failed' reintentable de la sesión también se
        procesa en el cierre (antes solo salía si no estaba fallido)."""
        session, order, picking, item = self._make_session_item(
            'PIQ4-4', item_state='failed', retry_count=2)

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit'):
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(item.state, 'done')
        self.assertEqual(item.retry_count, 0)
        self.assertNotIn(item, remaining)

    # ------------------------------------------------------------------
    # FOTO DE LA TRANSACCIÓN DEL CIERRE (PIQ-3)
    # ------------------------------------------------------------------

    def test_session_close_commits_when_there_was_work(self):
        """(PIQ-3) Con trabajo pendiente, el drenaje confirma la
        transacción del cierre antes de la lectura final.

        Los cursores de Odoo corren en REPEATABLE READ: sin ese commit,
        la lectura final se haría con la foto fija de antes de drenar y
        no vería que los cursores aislados marcaron los ítems 'done'
        (el cierre fallaba el primer intento). La foto en sí no es
        reproducible en test mode, donde todos los cursores son la misma
        transacción: aquí se verifica que el commit se dispara.
        """
        session, order, picking, item = self._make_session_item('PIQ3-1')

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit') as commit_mock:
            remaining = self.Queue._process_session_items(session)
        self.env.invalidate_all()

        self.assertEqual(item.state, 'done')
        self.assertFalse(remaining)
        self.assertTrue(
            commit_mock.called,
            'falta el commit de foto antes de la lectura final (PIQ-3)',
        )

    def test_session_close_skips_commit_without_work(self):
        """(PIQ-3) Sin ítems pendientes no se confirma nada: el commit
        solo se hace si hubo trabajo que reconciliar."""
        session = self._make_session()

        with self.enter_registry_test_mode(), \
             patch.object(self.env.cr, 'commit') as commit_mock:
            remaining = self.Queue._process_session_items(session)

        self.assertFalse(remaining)
        self.assertFalse(
            commit_mock.called,
            'no debe confirmar la transacción del cierre sin trabajo',
        )

    # ------------------------------------------------------------------
    # CONCURRENCIA: CONEXIÓN QUE NO ABRE Y LOCKS DE STOCK DE SESIÓN
    # ------------------------------------------------------------------

    def _only_claimable(self, item):
        """Deja 'item' como único ítem reclamable de la base (dentro de la
        transacción del test, que se revierte al terminar)."""
        self.Queue.search([
            ('id', '!=', item.id),
            ('state', 'in', ('pending', 'failed', 'processing')),
        ]).sudo().write({'state': 'done'})

    def _advisory_locks_held(self):
        """Locks advisory que tiene la conexión del test. En registry test
        mode el cursor aislado comparte esta misma conexión."""
        self.env.cr.execute(
            "SELECT count(*) FROM pg_locks "
            "WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
        )
        return self.env.cr.fetchone()[0]

    def test_process_queue_reverts_item_when_connection_fails(self):
        """Si PostgreSQL no da conexión para el cursor aislado ('too many
        clients' = OperationalError), el ítem vuelve a 'pending' al instante
        en vez de quedar 'processing' hasta el reclamo de 5 minutos."""
        picking = self._create_picking('CONN-1')
        item = self.Queue.create({'picking_id': picking.id})
        self._only_claimable(item)

        with patch.object(
            type(self.Queue), '_process_item_in_new_cursor',
            side_effect=psycopg2.OperationalError(
                'FATAL:  sorry, too many clients already'),
        ) as process_mock, patch.object(self.env.cr, 'commit'):
            self.Queue._process_queue(time_budget=0)
        self.env.invalidate_all()

        process_mock.assert_called_once_with(item.id)
        self.assertEqual(item.state, 'pending')
        self.assertFalse(item.start_date)
        self.assertIn('OperationalError', item.error_message)
        self.assertEqual(picking.state, 'assigned')

    def test_acquire_stock_locks_commits_after_locking(self):
        """Los locks son de SESIÓN, en orden, y se confirma DESPUÉS de
        tomarlos: la foto de la transacción de trabajo es posterior a la
        espera del lock (con pg_advisory_xact_lock la foto quedaba de antes
        y el drenador chocaba igual en stock_quant)."""
        cr = MagicMock()
        self.Queue._acquire_stock_locks(cr, [11, 22])

        self.assertEqual(cr.mock_calls, [
            call.execute("SELECT pg_advisory_lock(%s)", (11,)),
            call.execute("SELECT pg_advisory_lock(%s)", (22,)),
            call.commit(),
        ])

    def test_stock_locks_released_after_success(self):
        """Tras procesar el ítem no queda ningún lock de sesión en la
        conexión: vuelve al pool sin limpiarse y lo heredaría el próximo
        uso."""
        picking = self._create_picking('LOCK-1')
        item = self.Queue.create({'picking_id': picking.id})

        with self.enter_registry_test_mode():
            status = self.Queue._process_item_in_new_cursor(item.id)
        self.env.invalidate_all()

        self.assertEqual(status, 'done')
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._advisory_locks_held(), 0)

    def test_stock_locks_released_after_logic_error(self):
        """Un error de lógica (UserError del picking) también suelta los
        locks."""
        picking = self._create_picking('LOCK-2')
        item = self.Queue.create({'picking_id': picking.id})

        with patch.object(
            type(picking), '_action_done',
            side_effect=UserError('fallo simulado de validación'),
        ), self.enter_registry_test_mode():
            status = self.Queue._process_item_in_new_cursor(item.id)
        self.env.invalidate_all()

        self.assertEqual(status, 'failed')
        self.assertEqual(item.state, 'failed')
        self.assertEqual(self._advisory_locks_held(), 0)

    def test_stock_locks_released_after_contention(self):
        """Contención agotada (LockNotAvailable en todos los intentos): el
        ítem cede a 'pending' y la conexión queda sin locks."""
        picking = self._create_picking('LOCK-3')
        item = self.Queue.create({'picking_id': picking.id})

        with patch.object(
            type(picking), '_action_done',
            side_effect=psycopg2_errors.LockNotAvailable(),
        ), patch('time.sleep'), self.enter_registry_test_mode():
            status = self.Queue._process_item_in_new_cursor(item.id)
        self.env.invalidate_all()

        self.assertEqual(status, 'contention')
        self.assertEqual(item.state, 'pending')
        self.assertEqual(self._advisory_locks_held(), 0)

    # ------------------------------------------------------------------
    # RESERVA DIFERIDA: LA VENTA NO TOCA STOCK_QUANT
    # ------------------------------------------------------------------

    def _deferred_setup(self, defer=True):
        """Sesión POS real, stock en la ubicación de su tipo de operación y
        el interruptor de reserva diferida en el valor pedido."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('pos_inventory_queue.enabled', 'True')
        ICP.set_param('pos_inventory_queue.defer_reservation', str(defer))
        session = self._make_session()
        picking_type = session.config_id.picking_type_id
        self.pos_src = picking_type.default_location_src_id
        self.pos_dest = (
            picking_type.default_location_dest_id
            or self.env['stock.warehouse']._get_partner_locations()[0]
        )
        return session, picking_type

    def _put_stock(self, product, qty, lot=None):
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': self.pos_src.id,
            'lot_id': lot.id if lot else False,
            'inventory_quantity': qty,
        }).action_apply_inventory()

    def _pos_order(self, session, product, qty=1, lot_name=None, refund_of=None):
        line = {
            'product_id': product.id,
            'name': product.display_name,
            'qty': qty,
            'price_unit': 10.0,
            'price_subtotal': 10.0 * qty,
            'price_subtotal_incl': 10.0 * qty,
        }
        if lot_name:
            line['pack_lot_ids'] = [(0, 0, {'lot_name': lot_name})]
        if refund_of:
            line['refunded_orderline_id'] = refund_of.id
        return self.env['pos.order'].create({
            'session_id': session.id,
            'user_id': self.env.uid,
            'amount_tax': 0.0,
            'amount_total': 10.0 * qty,
            'amount_paid': 10.0 * qty,
            'amount_return': 0.0,
            'lines': [(0, 0, line)],
        })

    def _sell(self, order, picking_type):
        """Lo que hace la venta: crear el picking por el camino de la cola."""
        pickings = self.env['stock.picking'].with_context(
            pos_inventory_queue=True,
        )._create_picking_from_pos_order_lines(
            self.pos_dest.id, order.lines, picking_type, order.partner_id,
        )
        pickings.write({
            'pos_order_id': order.id,
            'pos_session_id': order.session_id.id,
        })
        return pickings

    def _process(self, picking):
        item = self.Queue.search([('picking_id', '=', picking.id)])
        with self.enter_registry_test_mode():
            status = self.Queue._process_item_in_new_cursor(item.id)
        self.env.invalidate_all()
        return item, status

    def _on_hand(self, product, lot=None):
        return product.with_context(
            location=self.pos_src.id, lot_id=lot.id if lot else None,
        ).qty_available

    def test_deferred_sale_does_not_reserve(self):
        """Con la reserva diferida la venta deja el picking en BORRADOR, sin
        move lines ni reserva en stock_quant, y el ítem guarda sus líneas."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        order = self._pos_order(session, self.product, qty=2)

        picking = self._sell(order, picking_type)

        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.state, 'draft')
        self.assertFalse(picking.move_line_ids)
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', self.pos_src.id),
        ])
        self.assertEqual(sum(quants.mapped('reserved_quantity')), 0)
        item = self.Queue.search([('picking_id', '=', picking.id)])
        self.assertEqual(item.pos_line_ids, order.lines)

    def test_deferred_picking_completed_by_queue(self):
        """La cola confirma, reserva, asigna y valida el picking en borrador:
        el stock baja lo vendido y el ítem queda 'done'."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        before = self._on_hand(self.product)
        order = self._pos_order(session, self.product, qty=2)
        picking = self._sell(order, picking_type)

        item, status = self._process(picking)

        self.assertEqual(status, 'done')
        self.assertEqual(item.state, 'done')
        self.assertEqual(picking.state, 'done')
        self.assertEqual(sum(picking.move_ids.mapped('quantity')), 2)
        self.assertTrue(all(picking.move_ids.mapped('picked')))
        self.assertEqual(self._on_hand(self.product), before - 2)

    def test_deferred_picking_assigns_lot(self):
        """Producto con lote: el lote que eligió el cajero se asigna en la
        cola, con la misma función del core (_add_mls_related_to_order)."""
        session, picking_type = self._deferred_setup()
        picking_type.use_existing_lots = True
        product = self.env['product.product'].create({
            'name': 'PIQ Lot Product',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
        })
        lot = self.env['stock.lot'].create({
            'name': 'PIQ-LOT-A', 'product_id': product.id,
        })
        self._put_stock(product, 5, lot=lot)
        order = self._pos_order(session, product, qty=1, lot_name='PIQ-LOT-A')
        picking = self._sell(order, picking_type)
        self.assertEqual(picking.state, 'draft')

        item, status = self._process(picking)

        self.assertEqual(status, 'done')
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.move_line_ids.lot_id, lot)
        self.assertEqual(self._on_hand(product, lot=lot), 4)

    def test_switch_off_reserves_in_sale(self):
        """Interruptor apagado: comportamiento anterior, la venta confirma y
        reserva (el picking ya no queda en borrador) y la cola solo valida."""
        session, picking_type = self._deferred_setup(defer=False)
        self._put_stock(self.product, 10)
        order = self._pos_order(session, self.product, qty=1)

        picking = self._sell(order, picking_type)

        self.assertNotEqual(picking.state, 'draft')
        self.assertTrue(picking.move_line_ids)
        item, status = self._process(picking)
        self.assertEqual(status, 'done')
        self.assertEqual(picking.state, 'done')

    def test_partial_refund_while_deferred_picking_queued(self):
        """Devolución parcial de una venta cuyo picking sigue en cola (en
        borrador): se reduce la demanda sin reservar y la cola descuenta
        solo lo que quedó."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        before = self._on_hand(self.product)
        order = self._pos_order(session, self.product, qty=2)
        picking = self._sell(order, picking_type)

        refund = self._pos_order(
            session, self.product, qty=-1, refund_of=order.lines[0])
        refund_pickings = self._sell(refund, picking_type)

        self.assertFalse(refund_pickings, 'no debe crear picking de devolución')
        self.assertEqual(picking.state, 'draft')
        self.assertEqual(picking.move_ids.product_uom_qty, 1)
        item, status = self._process(picking)
        self.assertEqual(status, 'done')
        self.assertEqual(self._on_hand(self.product), before - 1)

    def test_deferred_return_picking(self):
        """Devolución de una venta ya procesada: el picking de entrada
        también se difiere y la cola devuelve el stock."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        before = self._on_hand(self.product)
        order = self._pos_order(session, self.product, qty=1)
        self._process(self._sell(order, picking_type))
        self.assertEqual(self._on_hand(self.product), before - 1)

        refund = self._pos_order(
            session, self.product, qty=-1, refund_of=order.lines[0])
        return_picking = self._sell(refund, picking_type)
        self.assertEqual(return_picking.state, 'draft')

        item, status = self._process(return_picking)

        self.assertEqual(status, 'done')
        self.assertEqual(return_picking.state, 'done')
        self.assertEqual(self._on_hand(self.product), before)

    # ------------------------------------------------------------------
    # NUMERACIÓN DE VENTA DEL POS: 'standard' COMO EN ODOO 17
    # ------------------------------------------------------------------

    def _sale_sequences(self, config):
        return (
            config.order_seq_id
            | config.order_line_seq_id
            | config.order_backend_seq_id
        )

    def test_new_pos_config_uses_standard_sequences(self):
        """Un POS nuevo nace con la numeración de órdenes y líneas 'standard'
        (Odoo 19 las crea 'no_gap' y bloquea a los cajeros de la tienda)."""
        config = self.env['pos.config'].create({'name': 'PIQ Seq Test'})

        sequences = self._sale_sequences(config)
        self.assertEqual(len(sequences), 3)
        self.assertEqual(set(sequences.mapped('implementation')), {'standard'})

    def test_standard_sequences_conversion_is_idempotent(self):
        """La conversión (la que usa la migración) pasa a 'standard' solo lo
        que falta, sin saltar números, y una segunda pasada no cambia nada."""
        config = self.env['pos.config'].create({'name': 'PIQ Seq Test 2'})
        sequences = self._sale_sequences(config)
        sequences.write({'implementation': 'no_gap'})
        config.order_seq_id._next()
        config.order_seq_id._next()
        next_before = config.order_seq_id.number_next_actual

        changed = config._pos_queue_standard_sequences()

        self.assertEqual(changed, sequences)
        self.assertEqual(set(sequences.mapped('implementation')), {'standard'})
        self.assertEqual(config.order_seq_id.number_next_actual, next_before)
        self.assertEqual(int(config.order_seq_id._next()), next_before)
        self.assertFalse(config._pos_queue_standard_sequences())

    # ------------------------------------------------------------------
    # PDF DE LA FACTURA DESPUÉS DE CONFIRMAR LA VENTA
    # ------------------------------------------------------------------

    def _invoiced_order(self, pdf_after_commit=True):
        """Orden POS pagada y lista para facturar."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pos_inventory_queue.invoice_pdf_after_commit', str(pdf_after_commit))
        session, picking_type = self._deferred_setup()
        if not session.config_id.invoice_journal_id:
            self.skipTest('El POS de pruebas no tiene diario de facturas')
        cash = session.config_id.payment_method_ids.filtered('is_cash_count')[:1]
        if not cash:
            self.skipTest('El POS de pruebas no tiene medio de pago en efectivo')
        partner = self.env['res.partner'].create({'name': 'PIQ Cliente Factura'})
        order = self._pos_order(session, self.product, qty=1)
        order.write({'partner_id': partner.id, 'to_invoice': True})
        order.add_payment({
            'amount': order.amount_total,
            'payment_method_id': cash.id,
            'pos_order_id': order.id,
        })
        order.action_pos_order_paid()
        return order

    def _pending_pdf_ids(self):
        from odoo.addons.pos_inventory_queue.models.pos_order import (
            INVOICE_PDF_POSTCOMMIT_KEY,
        )
        return self.env.cr.postcommit.data.get(INVOICE_PDF_POSTCOMMIT_KEY, [])

    def test_invoice_pdf_deferred_after_commit(self):
        """La venta publica la factura SIN generar el PDF dentro y la anota
        para generarlo al confirmar la transacción."""
        order = self._invoiced_order()

        invoice = order._generate_pos_order_invoice()

        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(invoice.name and invoice.name != '/')
        self.assertFalse(invoice.invoice_pdf_report_id)
        self.assertIn(invoice.id, self._pending_pdf_ids())

    def test_invoice_pdf_generated_in_isolated_transaction(self):
        """El post-commit genera el PDF real de la factura (el mismo
        _generate_and_send del core) en su propia transacción."""
        order = self._invoiced_order()
        invoice = order._generate_pos_order_invoice()

        with self.enter_registry_test_mode():
            order._pos_queue_generate_invoice_pdf_isolated(
                self.env.registry, self.env.uid, {}, invoice.id)
        self.env.invalidate_all()

        self.assertTrue(invoice.invoice_pdf_report_id)
        self.assertFalse(invoice.sending_data)

    def test_invoice_pdf_switch_off_generates_in_sale(self):
        """Interruptor apagado: comportamiento del core, el PDF se genera
        dentro de la venta y no se anota nada para después."""
        order = self._invoiced_order(pdf_after_commit=False)

        invoice = order._generate_pos_order_invoice()

        self.assertTrue(invoice.invoice_pdf_report_id)
        self.assertNotIn(invoice.id, self._pending_pdf_ids())

    def test_invoice_pdf_respects_explicit_no_pdf(self):
        """Quien llame con generate_pdf=False no recibe un PDF en diferido."""
        order = self._invoiced_order()

        invoice = order.with_context(generate_pdf=False)._generate_pos_order_invoice()

        self.assertFalse(invoice.invoice_pdf_report_id)
        self.assertNotIn(invoice.id, self._pending_pdf_ids())

    def test_invoice_pdf_failure_falls_back_to_cron(self):
        """Si el PDF falla después de confirmar, la venta no se toca y la
        factura queda para el cron nativo de envío de facturas."""
        order = self._invoiced_order()
        invoice = order._generate_pos_order_invoice()

        with patch.object(
            type(self.env['account.move']), '_generate_and_send',
            side_effect=UserError('fallo simulado del PDF'),
        ), patch('time.sleep'), self.enter_registry_test_mode():
            order._pos_queue_generate_invoice_pdf_isolated(
                self.env.registry, self.env.uid, {}, invoice.id)
        self.env.invalidate_all()

        self.assertFalse(invoice.invoice_pdf_report_id)
        self.assertTrue(invoice.sending_data)
        self.assertEqual(invoice.state, 'posted')

    # ------------------------------------------------------------------
    # PIQ-5: _create_order_picking DELEGA EN ODOO 19
    # ------------------------------------------------------------------

    def test_create_order_picking_goes_through_queue(self):
        """La venta normal sigue encolando: el método del core, con el
        contexto de la cola, deja el picking en borrador con su ítem y lo
        vincula a la orden."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        order = self._pos_order(session, self.product, qty=1)

        order._create_order_picking()

        picking = order.picking_ids
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.state, 'draft')
        self.assertEqual(picking.pos_session_id, session)
        self.assertEqual(picking.origin, order.name)
        item = self.Queue.search([('picking_id', '=', picking.id)])
        self.assertEqual(item.pos_order_id, order)

    def test_ship_later_full_refund_cancels_pending_delivery(self):
        """Rama de Odoo 19 que faltaba: devolver una venta "Enviar más
        tarde" antes de entregarla CANCELA la entrega pendiente (antes el
        módulo lanzaba la regla de abastecimiento y la entrega salía igual)."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        partner = self.env['res.partner'].create({'name': 'PIQ Envío'})
        tomorrow = fields.Date.add(fields.Date.today(), days=1)
        order = self._pos_order(session, self.product, qty=1)
        order.write({'partner_id': partner.id, 'shipping_date': tomorrow})
        order._create_order_picking()
        delivery = order.picking_ids
        if not delivery:
            self.skipTest('Sin ruta de entrega en la base de pruebas')
        self.assertNotIn(delivery.state, ('done', 'cancel'))

        refund = self._pos_order(
            session, self.product, qty=-1, refund_of=order.lines[0])
        refund.write({
            'partner_id': partner.id,
            'shipping_date': tomorrow,
            'is_refund': True,
        })
        refund._create_order_picking()

        self.assertEqual(delivery.state, 'cancel')
        self.assertFalse(refund.picking_ids)

    def test_backorders_linked_after_queue_validation(self):
        """Si al validar en la cola queda un pendiente parcial (backorder),
        queda vinculado a la sesión y la orden del POS, como hace el core."""
        session, picking_type = self._deferred_setup()
        self._put_stock(self.product, 10)
        order = self._pos_order(session, self.product, qty=2)
        picking = self.Picking.create({
            'picking_type_id': picking_type.id,
            'location_id': self.pos_src.id,
            'location_dest_id': self.pos_dest.id,
            'origin': order.name,
            'pos_session_id': session.id,
            'pos_order_id': order.id,
        })
        move = self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom_qty': 2.0,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.pos_src.id,
            'location_dest_id': self.pos_dest.id,
        })
        picking.action_confirm()
        move.quantity = 1.0
        move.picked = True
        self.Queue.create({'picking_id': picking.id})

        item, status = self._process(picking)

        self.assertEqual(status, 'done')
        backorder = picking.backorder_ids
        self.assertTrue(backorder, 'debía quedar un pendiente parcial')
        self.assertEqual(backorder.pos_order_id, order)
        self.assertEqual(backorder.pos_session_id, session)
        self.assertEqual(backorder.origin, order.name)
