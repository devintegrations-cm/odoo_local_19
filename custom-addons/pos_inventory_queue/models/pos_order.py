import logging
from functools import partial

from odoo import api, models
from odoo.service.model import retrying
from odoo.tools.misc import str2bool

_logger = logging.getLogger(__name__)

# Clave de cr.postcommit.data donde se acumulan las facturas de la petición
# cuyo PDF se genera después de confirmar la venta.
INVOICE_PDF_POSTCOMMIT_KEY = 'pos_inventory_queue.invoice_pdf_after_commit'


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # -------------------------------------------------------------------------
    # PDF DE LA FACTURA DESPUÉS DE CONFIRMAR LA VENTA
    # -------------------------------------------------------------------------

    @api.model
    def _pos_queue_invoice_pdf_after_commit(self):
        """Interruptor (parámetro de sistema, por defecto activado).

        'pos_inventory_queue.invoice_pdf_after_commit' en 'False' vuelve al
        comportamiento del core: el PDF se genera dentro de la venta.
        """
        return str2bool(
            self.env['ir.config_parameter'].sudo().get_param(
                'pos_inventory_queue.invoice_pdf_after_commit',
                default='True',
            ),
            default=True,
        )

    def _generate_pos_order_invoice(self):
        """Factura la venta y genera su PDF DESPUÉS de confirmarla.

        El core publica la factura (le asigna el número del diario, sin
        huecos) y en la MISMA transacción genera y envía el PDF
        (_generate_and_send, 2-3 s). Mientras tanto la fila del número queda
        tomada y las demás ventas del mismo diario esperan: con un diario
        compartido por varias tiendas, la espera crece con cada cajero.

        Aquí la venta factura sin PDF (generate_pdf=False, opción del core) y
        el PDF se genera en un post-commit: después de confirmar la venta
        (el número ya quedó libre) y ANTES de responder al POS
        (service.model.retrying confirma y ejecuta los post-commit antes de
        devolver). El POS recibe la factura con su PDF real, igual que
        antes; la validación DIAN de Jorels sigue en _post, sin cambios.

        Respeta generate_pdf=False explícito de quien llame.
        """
        if (
            self.env.context.get('generate_pdf', True) is False
            or not self._pos_queue_invoice_pdf_after_commit()
        ):
            return super()._generate_pos_order_invoice()
        invoice = super(
            PosOrder, self.with_context(generate_pdf=False),
        )._generate_pos_order_invoice()
        self._pos_queue_schedule_invoice_pdf(invoice)
        return invoice

    def _pos_queue_schedule_invoice_pdf(self, invoices):
        """Anota las facturas para generar su PDF al confirmar la transacción.

        Un solo post-commit por transacción, aunque la petición traiga varias
        órdenes (sync_from_ui recibe una lista).
        """
        if not invoices:
            return
        postcommit = self.env.cr.postcommit
        pending = postcommit.data.setdefault(INVOICE_PDF_POSTCOMMIT_KEY, [])
        already_registered = bool(pending)
        pending.extend(invoices.ids)
        if already_registered:
            return
        uid = self.env.uid
        context = {
            key: value for key, value in self.env.context.items()
            if key != 'generate_pdf'
        }
        registry = self.env.registry

        @postcommit.add
        def generate_invoice_pdfs():
            for invoice_id in postcommit.data.pop(INVOICE_PDF_POSTCOMMIT_KEY, []):
                self._pos_queue_generate_invoice_pdf_isolated(
                    registry, uid, context, invoice_id,
                )

    @api.model
    def _pos_queue_generate_invoice_pdf_isolated(self, registry, uid, context, invoice_id):
        """Genera el PDF de UNA factura en su propia transacción.

        Mismo llamado que el core (_generate_and_send con
        skip_invoice_sync) y mismo usuario y contexto de la venta. Con el
        reintento del servidor ante choques. Si falla, la venta ya está
        confirmada: se marca la factura para el cron nativo de Odoo
        ('Send invoices automatically') y no se propaga el error.
        """
        try:
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                invoice = env['account.move'].browse(invoice_id).exists()
                if invoice and not invoice.invoice_pdf_report_id:
                    retrying(partial(
                        invoice.with_context(skip_invoice_sync=True)._generate_and_send,
                    ), env)
        except Exception:
            _logger.exception(
                'POS Queue: no se pudo generar el PDF de la factura %s después '
                'de la venta; se deja al cron de envío de facturas', invoice_id,
            )
            self._pos_queue_invoice_pdf_fallback(registry, uid, invoice_id)

    @api.model
    def _pos_queue_invoice_pdf_fallback(self, registry, uid, invoice_id):
        """Deja la factura al cron nativo de Odoo que genera y envía PDFs."""
        try:
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                invoice = env['account.move'].browse(invoice_id).exists()
                if not invoice or invoice.invoice_pdf_report_id:
                    return
                invoice.sudo().sending_data = {
                    'author_user_id': env.user.id,
                    'author_partner_id': env.user.partner_id.id,
                }
                env.ref('account.ir_cron_account_move_send')._trigger()
        except Exception:
            _logger.exception(
                'POS Queue: tampoco se pudo dejar la factura %s al cron de '
                'envío; generar el PDF a mano desde la factura', invoice_id,
            )

    def _create_order_picking(self):
        """Crea el picking de la venta con el método de Odoo 19 y la cola activa.

        El contexto pos_inventory_queue=True es lo que hace que
        stock.picking._create_picking_from_pos_order_lines encole el picking
        en vez de validarlo (ver models/stock_picking.py). El resto es el
        método del core, sin copiarlo (PIQ-5): antes era una copia del de
        Odoo 17 y le faltaban dos ramas de 19, la devolución de una venta
        "Enviar más tarde" (cancela o reduce la entrega pendiente) y la
        escritura de sesión, orden y origen en los backorders (con la cola,
        los backorders aparecen al validar: los completa
        pos.inventory.queue._link_pos_backorders).
        """
        return super(
            PosOrder, self.with_context(pos_inventory_queue=True),
        )._create_order_picking()

    @api.model
    def _recompute_cost_after_queue(self, picking):
        """(PIQ-1) Recalcula el costo FIFO/AVCO de la orden de un picking
        recién validado por la cola.

        El core calcula ``total_cost`` en ``_process_saved_order()``, justo
        después de ``_create_order_picking()`` y ANTES de que la cola
        valide los moves: en ese momento ``stock.move.value`` es 0 (el
        move todavía no está valorado), así que las líneas FIFO/AVCO
        quedan con costo 0 y con ``is_total_cost_computed=True``. El
        cierre de sesión solo recalcula las líneas con
        ``is_total_cost_computed=False``, así que nunca las corrige.

        Se reutiliza el método del core (paridad, sin lógica nueva): se
        resetea la bandera de las líneas FIFO/AVCO ya calculadas y se
        vuelve a llamar ``_compute_total_cost_in_real_time()``, que ahora
        lee ``move.value`` poblado por ``_action_done()``.

        Devuelve True si tocó algo. Best-effort: no lanza.
        """
        order = picking.pos_order_id
        if not order:
            return False
        if not order._should_create_picking_real_time():
            # En este camino las líneas FIFO/AVCO se calculan al cierre
            # de la sesión: resetearlas aquí las dejaría en
            # is_total_cost_computed=False sin que nadie las recalcule.
            return False
        lines = order.lines.filtered(
            lambda line: line.is_total_cost_computed
            and line._is_product_storable_fifo_avco()
        )
        if not lines:
            return False
        lines.write({'is_total_cost_computed': False})
        order._compute_total_cost_in_real_time()
        return True
