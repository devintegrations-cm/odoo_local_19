/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask, makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { CredibancoTransport } from "@pos_api_credibanco/app/utils/payment/credibanco_transport";
import {
    ANSWER,
    CODE_APPROVED,
    CODE_NO_FINAL_ANSWER,
    TRANSACTION,
    FIELD_LIMITS,
    buildPacket,
    cashRegisterRepresentation,
    getChargedAmount,
    getResponseMessage,
    operatorRepresentation,
    parseAnswer,
    OPERATOR_DIGITS,
    protocolAmount,
    protocolField,
    taxBreakdown,
} from "@pos_api_credibanco/app/utils/payment/credibanco_protocol";
import { TextListPopup } from "@pos_api_credibanco/app/components/popups/text_list_popup/text_list_popup";

// Batch size and timeout are protocol/infra decisions, documented in the
// README: the bridge itself gives up at 90 s (tef.ini), so waiting longer than
// that only hides the real error.
const TRANSACTION_NUMBER_BATCH = 25;

const MAX_RECOVERY_ATTEMPTS = 3;

/**
 * Credibanco terminal, built on Odoo 19's payment-terminal framework.
 *
 * Registering it as `use_payment_terminal === "credibanco"` buys, from the core,
 * the things the Odoo 17 module reimplemented by hand: one electronic payment at
 * a time, the pending/retry/done status of the payment line, and a hook to run
 * before the payment request is sent.
 *
 * What the cashier sees is deliberately unchanged from Odoo 17: the amount is
 * entered, the four message values are confirmed, and the terminal is asked.
 * `fastPayments` is false so the core does not fire the request before the
 * cashier has fixed a partial amount.
 *
 * Two rules of this class are load-bearing and should not be "simplified":
 *
 * 1. Nothing that identifies a transaction is ever truncated. A value that does
 *    not fit is an error shown to the cashier, never a shortened value: a
 *    shortened cash register or transaction number could be echoed back against
 *    somebody else's sale.
 * 2. Cancellation and recovery echo what was *sent*, read back from the payment
 *    itself.  Recomputing those positions from the session (device ids and
 *    counters move) or taking them from the terminal's answer would pair an
 *    anulación with the wrong transaction.
 */
export class PaymentCredibanco extends PaymentInterface {
    setup(pos, paymentMethod) {
        super.setup(...arguments);
        this.api = new CredibancoTransport();
        this.transactionNumbers = [];
        // The core's "Reverse Payment" button is the trigger, but the reversal
        // itself is done the Odoo 17 way: send the protocol anulación and
        // register a compensating negative payment line on the order. The core
        // would set the amount to 0 (`reversed` status), which accounting and
        // the bank statement cannot reconcile against: the sale and its
        // cancellation need to be visible as two movements. See
        // `sendPaymentReversal`.
        this.supports_reversals = true;
        this.taxMap = null;
    }

    get fastPayments() {
        return false;
    }

    get paymentMethod() {
        return this.payment_method_id;
    }

    async sendPaymentRequest(uuid) {
        const line = this._getLine(uuid);
        if (!line) {
            return false;
        }

        let prepared;
        try {
            prepared = await this._prepareFields(line);
        } catch (error) {
            console.error("Credibanco: no se pudieron preparar los valores", error);
            this._alert(
                _t("No se pudieron calcular los valores del datáfono"),
                _t(
                    "El punto de venta no pudo preparar la transacción " +
                        "(impuestos o número de transacción). Verifique la conexión " +
                        "con el servidor e intente de nuevo; si persiste, avise a IT."
                )
            );
            return false;
        }
        if (!prepared.ok) {
            this._alert(prepared.title, prepared.body);
            return false;
        }

        // The references are stored before contacting the device: if the answer
        // never arrives, cancellation and recovery still echo this exact sale.
        this._storeReferences(line, prepared.references);

        const confirmed = await this._confirmAmounts(prepared.fields);
        if (!confirmed) {
            return false;
        }

        return this._runSale(line, prepared.fields, prepared.references);
    }

    /**
     * Cancelling while the terminal is waiting is not safe: the customer may
     * approve a second later. So the cancellation goes through the protocol
     * cancellation, and the line stays pending if that fails.
     */
    async sendPaymentCancel(order, uuid) {
        const line = this._getLine(uuid);
        this.api.abort();
        const positions = line && this._sentPositions(line);
        if (!positions) {
            // Nothing was ever sent to the terminal for this line.
            return true;
        }
        // No expectation here: the answer of an anulación (OUTPUT_FIELDS_02)
        // carries the terminal reference (43), which a sale that never answered
        // does not have yet.
        const cancelled = await this._send(TRANSACTION.CANCEL, positions);
        if (cancelled?.code === CODE_APPROVED) {
            line.credibanco_pending_sale = "";
            return true;
        }
        this._alert(
            _t("No se pudo cancelar la transacción"),
            _t(
                "El datáfono no confirmó la cancelación. No cancele ni cobre de " +
                    "nuevo: use «Recuperar» antes de continuar, o la venta puede " +
                    "quedar registrada en el terminal sin pago en Odoo."
            )
        );
        return false;
    }

    /**
     * Reversal of an approved payment, done the Odoo 17 way so accounting and
     * the bank statement keep seeing a sale and its cancellation as two
     * movements: send the protocol anulación (echoed from the values this
     * payment actually sent plus the reference the terminal returned) and, if
     * the terminal approves it, register a compensating negative payment line.
     *
     * It deliberately returns `false` to the core even on success. `true` would
     * make the core zero the approved line (`setAmount(0)` + `reversed`), which
     * is exactly the single 0-valued record the migration wanted to avoid. With
     * `false`, the core only marks the line non-reversible again and restores
     * `done`, so the `+X` stays and our `-X` line cancels it. This is not a bug
     * to "fix" back to `true`.
     */
    async sendPaymentReversal(uuid) {
        const line = this._getLine(uuid);
        const positions = line && this._sentPositions(line);
        if (!positions) {
            this._alert(
                _t("No se puede anular el pago"),
                _t(
                    "Este pago no guardó las referencias enviadas al datáfono, así " +
                        "que no se puede construir la anulación. Registre una " +
                        "devolución manual y avise a IT."
                )
            );
            return false;
        }
        // The anulación of an approved payment can be matched: the terminal
        // returns its own reference (43) in the answer, and we stored it.
        const reversed = await this._send(TRANSACTION.CANCEL, positions, {
            [ANSWER.REFERENCE]: positions[ANSWER.REFERENCE],
        });
        if (reversed?.code !== CODE_APPROVED) {
            this._alert(
                _t("La anulación no fue aprobada"),
                reversed
                    ? reversed.body || reversed.message || _t("El datáfono no respondió.")
                    : _t("El datáfono no respondió.")
            );
            return false;
        }
        this._addAnulationLine(line, reversed.values);
        return false;
    }

    /**
     * The compensating negative payment line an anulación leaves behind.
     *
     * It is created directly on the order (not through the core's
     * `addPaymentline`) so it carries no electronic `payment_status`: a plain
     * payment line, exactly like the Odoo 17 module registered it, and it is
     * what `_create_payment_moves` turns into the reversal entry at session
     * close. The amount is the *approved* charge with the opposite sign so the
     * order nets to zero; Odoo 17 read position 40 of the anulación answer,
     * which left a tip (81) uncancelled and broke the netting.
     *
     * The references copied from the cancelled line are what ties it to the
     * sale for audit; `credibanco_anulation_of` is the marker the delete guard
     * uses to keep it from being removed without the terminal's reversal.
     */
    _addAnulationLine(originalLine, answerValues) {
        const order = originalLine.pos_order_id;
        const anulation = this.pos.models["pos.payment"].create({
            pos_order_id: order,
            payment_method_id: this.payment_method_id,
        });
        anulation.setAmount(-Math.abs(originalLine.getAmount()));
        anulation.credibanco_cash_register = originalLine.credibanco_cash_register;
        anulation.credibanco_number_transaction = originalLine.credibanco_number_transaction;
        anulation.credibanco_operator = originalLine.credibanco_operator;
        anulation.credibanco_anulation_of = originalLine.uuid;
        if (answerValues) {
            anulation.credibanco_response = JSON.stringify(answerValues);
        }
        const approval = originalLine.credibanco_approval_number || "";
        anulation.credibanco_approval_number = approval
            ? `Anul. de ${approval}`
            : _t("Anulación");
        anulation.setReceiptInfo(`\n${_t("Anulación de una venta Credibanco")}\n`);
        return anulation;
    }

    /**
     * Recovery of a sale the terminal never answered (code "03" or a reload).
     */
    async recoverPendingPayment(line) {
        const positions = line && this._sentPositions(line);
        if (!positions) {
            this._alert(
                _t("No hay datos para recuperar"),
                _t(
                    "Este pago no guardó la venta enviada al datáfono. Verifique en " +
                        "el terminal si la compra llegó a aprobarse."
                )
            );
            return false;
        }
        return this._runRecover(line, positions);
    }

    // ------------------------------------------------------------------
    // Sale
    // ------------------------------------------------------------------

    async _runSale(line, fields, references) {
        // The answer of a sale carries 42 and 53 back (functionsFields.ini:
        // OUTPUT_FIELDS_01), so the response can be matched to this request.
        const result = await this._send(TRANSACTION.SALE, fields, this._positions(references, fields));

        if (!result) {
            // Unknown outcome: keep the exact sale recoverable instead of letting
            // the cashier retry blind and charge twice.
            line.credibanco_pending_sale = JSON.stringify(this._positions(references, fields));
            this._alert(
                _t("Sin respuesta del datáfono"),
                _t(
                    "La venta puede haber quedado aprobada en el terminal. Use " +
                        "«Recuperar» antes de intentar de nuevo, para no cobrar " +
                        "dos veces."
                )
            );
            return false;
        }

        if (result.code === CODE_APPROVED) {
            line.credibanco_pending_sale = "";
            this._applyApprovedSale(line, result.values);
            return true;
        }

        if (result.code === CODE_NO_FINAL_ANSWER) {
            line.credibanco_pending_sale = JSON.stringify(this._positions(references, fields));
            return this._runRecover(line, this._positions(references, fields));
        }

        line.credibanco_pending_sale = "";
        this._alert(result.title, result.body);
        return false;
    }

    _applyApprovedSale(line, values) {
        const charged = getChargedAmount(values);
        if (charged !== null) {
            // The terminal is the authority: the customer may have added a tip on
            // the device after the amount was sent.
            line.setAmount(charged);
        }
        const approval = values[ANSWER.AUTHORIZATION_CODE];
        line.credibanco_approval_number = approval ? String(approval) : "";
        line.transaction_id = values[ANSWER.TRANSACTION_ID]
            ? String(values[ANSWER.TRANSACTION_ID])
            : line.transaction_id;
        line.credibanco_response = JSON.stringify(values);
        if (approval) {
            line.setReceiptInfo(`\n${_t("Aprob.")}: ${approval}\n`);
        }
    }

    async _runRecover(line, positions) {
        for (let attempt = 0; attempt < MAX_RECOVERY_ATTEMPTS; attempt++) {
            const wantsRecovery = await ask(this.pos.dialog, {
                title: _t("Transacción sin respuesta final"),
                body: _t(
                    "El datáfono no devolvió una respuesta final.\n\n" +
                        "Recupere la transacción para conocer su estado real: en el " +
                        "terminal, TECLA 3 y luego TECLA 9."
                ),
                confirmLabel: _t("Recuperar"),
                cancelLabel: _t("Más tarde"),
            });
            if (!wantsRecovery) {
                return false;
            }
            // OUTPUT_FIELDS_00 returns neither 42 nor 53, so a recovery answer
            // cannot be matched by the request; it is accepted as-is.
            const recovered = await this._send(TRANSACTION.RECOVER, positions);
            if (recovered?.code === CODE_APPROVED) {
                line.credibanco_pending_sale = "";
                this._applyApprovedSale(line, recovered.values);
                return true;
            }
            if (recovered && recovered.code !== CODE_NO_FINAL_ANSWER) {
                line.credibanco_pending_sale = "";
                this._alert(recovered.title, recovered.body);
                return false;
            }
        }
        this._alert(
            _t("La recuperación sigue pendiente"),
            _t(
                "Consulte el estado en el datáfono y avise a un responsable antes " +
                    "de repetir el cobro."
            )
        );
        return false;
    }

    // ------------------------------------------------------------------
    // Transport
    // ------------------------------------------------------------------

    /**
     * @param {Object} expect  positions the answer must carry with exactly these
     * values for it to belong to *this* request. The bridge broadcasts every
     * answer to all connected browsers, so a second register on the same bridge
     * can otherwise apply a stranger's approval as its own. Only operations whose
     * answer really returns the identifying positions are matched.
     */
    async _send(type, fields, expect = null) {
        const config = this.paymentMethod;
        const packet = buildPacket(type, fields, config.pos_payment_terminal_name);
        if (!packet) {
            return null;
        }
        let raw;
        try {
            raw = await this.api.send(packet, {
                ip_host: config.pos_ip_host,
                port: config.pos_websocket_port,
                timeout: config.credibanco_timeout,
                expect,
            });
        } catch (error) {
            return null;
        }
        const parsed = parseAnswer(raw);
        if (!parsed) {
            return {
                code: "06",
                title: _t("Error en la trama"),
                body: _t("Los datos de la respuesta son diferentes a los esperados."),
            };
        }
        if (parsed.code === CODE_APPROVED || parsed.code === CODE_NO_FINAL_ANSWER) {
            return parsed;
        }
        return { ...parsed, ...getResponseMessage(parsed.code) };
    }

    // ------------------------------------------------------------------
    // Message fields
    // ------------------------------------------------------------------

    async _prepareFields(line) {
        const order = line.pos_order_id;
        const amount = line.getAmount();
        if (!amount || amount <= 0) {
            return {
                ok: false,
                title: _t("Valor incorrecto"),
                body: _t("El monto a pagar debe ser mayor que 0."),
            };
        }

        const references = await this._buildReferences(line, order, amount);
        if (!references.ok) {
            return references;
        }

        const taxes = await this._taxAmounts(order, amount);
        if (!taxes.ok) {
            return taxes;
        }

        const tip = order.getTip() || 0;
        const fields = {
            total: protocolAmount(_t("total"), references.charge - tip, FIELD_LIMITS.total),
            iva: protocolAmount(_t("IVA"), taxes.vat, FIELD_LIMITS.iva),
            iac: protocolAmount(_t("IAC"), taxes.iac, FIELD_LIMITS.iac),
            tip: protocolAmount(_t("propina"), tip, FIELD_LIMITS.tip),
            cashier: references.operator,
            cashRegister: references.cashRegister,
            numberTransaction: references.numberTransaction,
            fieldFiller84: protocolField(_t("relleno 84"), "", FIELD_LIMITS.cashRegister),
        };

        const overflow = Object.values(fields).filter((field) => field.overflow);
        if (overflow.length) {
            return {
                ok: false,
                title: _t("El pedido no cabe en la trama del datáfono"),
                body: _t(
                    "Uno o más valores superan los dígitos admitidos por el " +
                        "datáfono y no se envían recortados para no mezclar " +
                        "transacciones:\n\n%(details)s\n\nContacte a IT.",
                    {
                        details: overflow
                            .map(
                                (field) =>
                                    `  • ${field.label}: ${field.value} (${field.value.length}/${field.digits})`
                            )
                            .join("\n"),
                    }
                ),
            };
        }

        const charged = references.charge;
        if (taxes.vat >= charged || taxes.iac >= charged || tip >= charged) {
            return {
                ok: false,
                title: _t("Valores inconsistentes"),
                body: _t(
                    "Los impuestos y/o la propina no pueden igualar o superar el " +
                        "valor total del cobro."
                ),
            };
        }

        return { ok: true, fields, references };
    }

    /**
     * Positions 42, 53 and 83: what identifies this sale at the terminal.
     *
     * 42 is the cash register, composed exactly as the Odoo 17 integration
     * composed it (protocol: alphanumeric, up to 10 characters): the session id
     * concatenated with the cashier id, no separator.  Credibanco's
     * certification of this integration is built on that serialisation, so the
     * composition is kept; the difference against 17 is on the *error* side --
     * a composition that does not fit is refused instead of silently truncated
     * or reported as a bare "IT" popup, because a shortened cash register could
     * be echoed back against somebody else's sale.
     * 53 comes from a block of numbers reserved on the server, so it is unique
     * per register without the POS composing identifiers that read in more than
     * one way.
     * 83 is the cashier's first name, the representation the Odoo 17 integration
     * has always reported to the acquirer, limited to the 12 characters the
     * protocol allows. The employee keeps its full name in Odoo.
     */
    async _buildReferences(line, order, amount) {
        const failed = (title, body) => ({ ok: false, title, body });
        const sessionId = this.pos.session?.id;
        const cashier = this.pos.getCashier();
        if (!sessionId) {
            return failed(
                _t("Sesión no disponible"),
                _t(
                    "El punto de venta no ha terminado de cargar la sesión, así " +
                        "que no puede componer el número de caja. Recargue la " +
                        "página del POS e intente de nuevo."
                )
            );
        }
        if (!cashier || !cashier.id) {
            return failed(
                _t("Falta el cajero"),
                _t("Inicie sesión con un empleado antes de cobrar con el datáfono.")
            );
        }
        const composedRegister = cashRegisterRepresentation(sessionId, cashier.id);
        if (composedRegister.overflow) {
            return failed(
                _t("El número de caja excede el protocolo"),
                _t(
                    "La sesión %(session)s y el cajero %(cashier)s generan un " +
                        "número de caja (%(value)s) de %(length)s caracteres, y el " +
                        "datáfono acepta como máximo %(max)s. No se envía " +
                        "recortado para no mezclar transacciones. Avise a IT.",
                    {
                        session: sessionId,
                        cashier: cashier.id,
                        value: composedRegister.value,
                        length: composedRegister.value.length,
                        max: composedRegister.digits,
                    }
                )
            );
        }
        const numberTransaction = await this._nextTransactionNumber();
        if (!numberTransaction) {
            return failed(
                _t("Sin números de transacción disponibles"),
                _t(
                    "Este terminal agotó los números de transacción reservados y no " +
                        "hay conexión con el servidor para conseguir más. Espere a " +
                        "recuperar la conexión: cobrar con un número repetido puede " +
                        "anular la venta equivocada más adelante."
                )
            );
        }
        const operator = operatorRepresentation(cashier.name, FIELD_LIMITS.operator);
        return {
            ok: true,
            charge: amount,
            cashRegister: protocolField(
                _t("número de caja (42)"),
                composedRegister.value,
                FIELD_LIMITS.cashRegister
            ),
            numberTransaction: protocolField(
                _t("número de transacción (53)"),
                numberTransaction,
                FIELD_LIMITS.numberTransaction
            ),
            // Already limited by operatorRepresentation(): it cannot overflow.
            operator: protocolField(_t("cajero (83)"), operator.value, FIELD_LIMITS.operator),
            operatorTruncated: operator.truncated,
            operatorFull: operator.full,
        };
    }

    /**
     * Next transaction number, refilling the reserved block from the server.
     *
     * @returns {Promise<String|null>} null when the block is empty and the server
     * is unreachable; the caller must refuse instead of reusing a number, because
     * the terminal looks a sale up by (42, 53).
     */
    async _nextTransactionNumber() {
        if (!this.transactionNumbers?.length) {
            // Odoo 19 exposes the connectivity state as `network.offline`; there
            // is no `online` property, and reading one that does not exist means
            // "always offline" for this code path.
            const offline =
                this.pos.data?.network?.offline ?? !navigator.onLine;
            if (offline) {
                return null;
            }
            const reserved = await this.pos.data.call(
                "pos.payment.method",
                "reserve_credibanco_transaction_numbers",
                [[this.paymentMethod.id]],
                { count: TRANSACTION_NUMBER_BATCH }
            );
            if (!Array.isArray(reserved)) {
                // A wrong shape here is a server/programming error, not a lack of
                // connectivity: say so instead of reporting the offline message.
                throw new Error("credibanco_unexpected_reservation");
            }
            this.transactionNumbers = reserved.slice();
        }
        return this.transactionNumbers.shift() || null;
    }

    /**
     * Called by the core when the payment screen closes: drop the socket so a late
     * answer cannot be applied, and forget the reserved block (the server keeps
     * those numbers for the next screen, and gaps are cheaper than collisions).
     */
    close() {
        this.api.abort();
        this.transactionNumbers = [];
    }

    /**
     * What was sent is recorded before asking the terminal, so a payment whose
     * answer never arrives can still be cancelled or recovered exactly.
     */
    _storeReferences(line, references) {
        line.credibanco_cash_register = references.cashRegister.value;
        line.credibanco_number_transaction = references.numberTransaction.value;
        line.credibanco_operator = references.operator.value;
        if (references.operatorTruncated && this._isDebug()) {
            // Loud in development, silent in production: the cashier only ever sees
            // the name shortened on the device, never in Odoo.
            console.warn(
                "Credibanco: el nombre del cajero excede la posición 83; se envía",
                references.operator.value,
                "en lugar de",
                references.operatorFull
            );
        }
    }

    /**
     * The exact request positions of a sale, so a retry/cancel can echo them.
     */
    _positions(references, fields) {
        return {
            [ANSWER.TOTAL]: fields?.total?.value ?? String(references.charge ?? ""),
            [ANSWER.TERMINAL_ID]: references.cashRegister.value,
            [ANSWER.TRANSACTION_NUMBER]: references.numberTransaction.value,
            [ANSWER.CASHIER]: references.operator.value,
            [ANSWER.TIP]: fields?.tip?.value ?? "0",
        };
    }

    /**
     * Positions needed to cancel or recover, read back from the payment itself.
     *
     * 42/53/83 come from what was sent (persisted fields, falling back to the
     * pending sale stored at send time).  43 and the trailing fields come from the
     * terminal's answer, because that reference is the device's own.
     */
    _sentPositions(line) {
        const answer = this._readAnswer(line) || {};
        const pending = this._readPendingSale(line) || {};
        const cashRegister = line.credibanco_cash_register || pending[ANSWER.TERMINAL_ID];
        const numberTransaction =
            line.credibanco_number_transaction || pending[ANSWER.TRANSACTION_NUMBER];
        if (!cashRegister || !numberTransaction) {
            return null;
        }
        const positions = {
            [ANSWER.TERMINAL_ID]: cashRegister,
            [ANSWER.TRANSACTION_NUMBER]: numberTransaction,
            [ANSWER.CASHIER]: line.credibanco_operator || pending[ANSWER.CASHIER] || "",
        };
        for (const position of [ANSWER.REFERENCE, "87", "88", ANSWER.TOTAL, ANSWER.TIP]) {
            const value = answer[position] ?? pending[position];
            if (value !== undefined && value !== null && value !== "") {
                positions[position] = value;
            }
        }
        return positions;
    }

    /**
     * IVA and IAC of the amount being charged.
     *
     * Which tax is which is decided by the server (`get_credibanco_tax_map`,
     * matching the tax *group*, so no tax id is hardcoded and a translated group
     * name cannot change the result).  This method only knows *where* Odoo 19
     * keeps the per-line amounts, and hands the arithmetic to the pure
     * `taxBreakdown` helper.
     *
     * Each entry of a line's `taxes_data` carries the tax record itself under
     * `tax` (see `account_tax._get_tax_details`), not an id field: reading a key
     * that does not exist classifies nothing, and the whole order then looks like
     * one unknown tax.
     *
     * When the order does carry positive taxes but none of them is classified, the
     * payment is refused and says which groups it saw: sending zeroes in 41/82
     * would print a receipt that disagrees with what the bank is told.
     */
    async _taxAmounts(order, amount) {
        const taxMap = await this._getTaxMap();
        const perLineTaxes = [];

        for (const orderLine of order.lines) {
            const details = orderLine.prices?.taxes_data;
            if (!Array.isArray(details)) {
                return {
                    ok: false,
                    title: _t("No se pueden determinar los impuestos"),
                    body: _t(
                        "El calculo de impuestos del pedido no devolvio los datos " +
                            "esperados. Avise a IT antes de cobrar con el datafono."
                    ),
                };
            }
            perLineTaxes.push(
                details.map((entry) => ({
                    taxId: entry?.tax?.id ?? entry?.tax_id ?? entry?.id,
                    amount: Number(entry?.tax_amount_currency ?? entry?.tax_amount ?? 0),
                }))
            );
        }

        const breakdown = taxBreakdown(taxMap, perLineTaxes);
        if (!breakdown.classified && breakdown.other > 0) {
            return {
                ok: false,
                title: _t("Impuestos no reconocidos"),
                body: _t(
                    "El pedido tiene impuestos por %s en grupos que el datáfono no " +
                        "sabe reportar (%s). Solo se reconocen los grupos cuyo nombre " +
                        "empieza por IVA o INC. Avise a IT.",
                    this.env.utils.formatCurrency(breakdown.other),
                    this._groupLabels(perLineTaxes)
                ),
            };
        }

        const total = order.priceIncl || 0;
        const factor = total ? amount / total : 1;
        return {
            ok: true,
            vat: Math.round(breakdown.vat * factor),
            iac: Math.round(breakdown.iac * factor),
        };
    }

    /**
     * Tax group names behind a set of amounts, for the error message only.
     *
     * Displayed translated on purpose: it is read by a human who is being asked to
     * fix a chart, and the classification itself never depends on it.
     */
    _groupLabels(perLineTaxes) {
        const taxes = this.pos.models["account.tax"];
        const names = new Set();
        for (const lineTaxes of perLineTaxes) {
            for (const entry of lineTaxes) {
                if (!(entry.amount > 0) || entry.taxId === undefined) {
                    continue;
                }
                const group_name = taxes.get(entry.taxId)?.tax_group_id?.name;
                names.add(group_name || _t("(sin grupo)"));
            }
        }
        return [...names].join(", ") || _t("ninguno");
    }

    async _getTaxMap() {
        if (!this.taxMap) {
            this.taxMap = await this.pos.data.call(
                "pos.payment.method",
                "get_credibanco_tax_map",
                [[this.paymentMethod.id]]
            );
        }
        return this.taxMap || {};
    }

    _isDebug() {
        return Boolean(window.odoo?.debug);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    _getLine(uuid) {
        return this.pos.models["pos.payment"].getBy("uuid", uuid);
    }

    _readAnswer(line) {
        return this._readJson(line.credibanco_response);
    }

    _readPendingSale(line) {
        return this._readJson(line.credibanco_pending_sale);
    }

    _readJson(text) {
        if (!text) {
            return null;
        }
        try {
            const parsed = JSON.parse(text);
            return parsed && typeof parsed === "object" ? parsed : null;
        } catch (error) {
            return null;
        }
    }

    async _confirmAmounts(fields) {
        const money = (value) => this.env.utils.formatCurrency(Number(value) || 0);
        const response = await makeAwaitable(this.pos.dialog, TextListPopup, {
            title: _t("Valores de la transacción"),
            body: _t("Confirme los valores antes de proceder con el pago:"),
            list: [
                `${_t("TOTAL")}: ${money(fields.total.value)}`,
                `${_t("IVA")}: ${money(fields.iva.value)}`,
                `${_t("IAC")}: ${money(fields.iac.value)}`,
                `${_t("PROPINA")}: ${money(fields.tip.value)}`,
            ],
            confirmText: _t("Continuar"),
            cancelText: _t("Cancelar"),
        });
        return Boolean(response?.confirmed);
    }

    _alert(title, body) {
        return this.pos.dialog.add(AlertDialog, { title, body });
    }
}

register_payment_method("credibanco", PaymentCredibanco);
