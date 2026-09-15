/** @odoo-module */

/**
 * Credibanco wire protocol: packet building and answer parsing.
 *
 * Deliberately free of any Odoo/OWL dependency. It is the part that has to be
 * byte-exact against the terminal, so keeping it apart from the payment
 * interface makes it readable, and unit-testable without a device.
 */

export const TRANSACTION = {
    SALE: 1,
    CANCEL: 2,
    RECOVER: 3,
};

export const CODE_APPROVED = "00";
export const CODE_NO_FINAL_ANSWER = "03";

/**
 * Maximum length of each message position.
 *
 * Transcribed from the terminal bridge resources
 * (`api_credibanco_dkr/resource/fields.ini`, kept outside this module on purpose):
 *
 *   FIELD_LEN_40/41/81/82/84 = 12  FIELD_TYPE = 0 (numeric)  amounts
 *   FIELD_LEN_42             = 10  FIELD_TYPE = 1 (alphanumeric)  cash register
 *   FIELD_LEN_43             = 6   FIELD_TYPE = 0              terminal reference
 *   FIELD_LEN_53             = 10  FIELD_TYPE = 1              transaction number
 *   FIELD_LEN_83             = 12  FIELD_TYPE = 1              operator
 *
 * The bridge pads each field to its length itself (`TefFields.formatField`), so
 * the POS must send the value as it is: never padded, never truncated.  A value
 * longer than the protocol allows is rejected by the terminal as
 * "campo no corresponde" (code 10), so the POS refuses it earlier with a message
 * naming the field instead.
 */
export const FIELD_LIMITS = {
    total: 12,
    iva: 12,
    iac: 12,
    tip: 12,
    cashRegister: 10,
    numberTransaction: 10,
    operator: 12,
    filler: 12,
};

// Kept for callers that only need the operator width.
export const OPERATOR_DIGITS = FIELD_LIMITS.operator;

// Positions of the answer the flow depends on.  Documented in
// static/data/fields_credibanco.json, which the backend uses to label the
// stored breakdown.
export const ANSWER = {
    CODE: "0",
    AUTHORIZATION_CODE: "1",
    TRANSACTION_ID: "2",
    TOTAL: "40",
    TIP: "80",
    TERMINAL_ID: "42",
    REFERENCE: "43",
    TRANSACTION_NUMBER: "53",
    CASHIER: "83",
};

// Codes that stop a payment without meaning "the customer declined".
const RESPONSE_MESSAGES = {
    "02": {
        title: "Transacción rechazada.",
        body: "Fondos insuficientes, clave inválida, tarjeta vencida o transacción cancelada por el cajero.",
    },
    "05": {
        title: "Transacción negada.",
        body: "Problemas de comunicación, intente de nuevo.",
    },
    "06": {
        title: "Error en la trama.",
        body: "La estructura enviada es incorrecta, comuníquese con el área de IT.",
    },
    "99": {
        title: "Puerto ocupado.",
        body: "Comportamiento externo no controlado. Comuníquese con el área de IT.",
    },
    // Infrastructure codes reported by the terminal itself, from
    // api_credibanco_dkr/resource/messages.ini. Without them a malformed packet
    // reads exactly like "the customer declined", which sends the cashier down
    // the wrong path. The bridge also names two I/O errors (MSG_CODE_1,
    // MSG_CODE_2) whose code on the wire is not confirmed, so they are not
    // mapped here rather than guessed: an unmapped code falls through to the
    // generic message, which is honest.
    "09": {
        title: "La función no corresponde.",
        body: "El datáfono no reconoció el tipo de operación. Avise a IT.",
    },
    "10": {
        title: "Campo no corresponde.",
        body: "Un valor enviado no cumple el formato o la longitud que espera el " +
            "datáfono. Revise el número de caja, el número de transacción y los " +
            "importes, y avise a IT.",
    },
    "11": {
        title: "Mensaje no válido.",
        body: "La trama no tiene el formato esperado. Avise a IT.",
    },
    "12": {
        title: "Función no definida.",
        body: "El datáfono no tiene definida esa operación. Avise a IT.",
    },
    "13": {
        title: "Tiempo de espera agotado.",
        body: "El datáfono tardó demasiado en responder. No vuelva a cobrar: use " +
            "«Recuperar» para conocer el estado real de la transacción.",
    },
};

const UNKNOWN_MESSAGE = {
    title: "Transacción rechazada o declinada.",
    body: "Fondos insuficientes, clave inválida, tarjeta vencida o transacción cancelada por el cajero.",
};

export function getResponseMessage(code) {
    return RESPONSE_MESSAGES[code] || UNKNOWN_MESSAGE;
}

/**
 * LRC checksum used by the terminal, identical to the one the v17 module sent.
 */
export function computeLRC(text) {
    if (!text.length) {
        return "";
    }
    let lrc = text.charCodeAt(0);
    for (let i = 1; i < text.length; i++) {
        lrc ^= text.charCodeAt(i);
    }
    const hex = lrc.toString(16);
    return hex.length === 1 ? `0${hex}` : hex;
}

/**
 * @param {Integer} type one of TRANSACTION
 * @param {Object} fields values already validated/trimmed by the caller
 * @param {String} terminalName prefix the terminal expects
 * @returns {String} the packet to send
 */
export function buildPacket(type, fields, terminalName) {
    const ordered = [];
    switch (type) {
        case TRANSACTION.SALE:
            ordered.push("01");
            ordered.push(fields.total.value); // 40
            ordered.push(fields.iva.value); // 41
            ordered.push(fields.cashRegister.value); // 42
            ordered.push(fields.numberTransaction.value); // 53
            ordered.push(fields.tip.value); // 81
            ordered.push(fields.iac.value); // 82
            ordered.push(fields.cashier.value); // 83
            ordered.push(`${fields.fieldFiller84.value},`); // 84
            break;
        case TRANSACTION.CANCEL:
            ordered.push("02");
            ordered.push(fields[ANSWER.TERMINAL_ID]); // 42
            ordered.push(fields[ANSWER.REFERENCE]); // 43
            ordered.push(fields[ANSWER.TRANSACTION_NUMBER]); // 53
            ordered.push(fields[ANSWER.CASHIER]); // 83
            ordered.push("87" in fields ? fields["87"] : ""); // 87
            ordered.push(`${"88" in fields ? fields["88"] : ""},`); // 88
            break;
        case TRANSACTION.RECOVER:
            ordered.push("00");
            ordered.push(fields[ANSWER.TERMINAL_ID]); // 42
            ordered.push(`${fields[ANSWER.TRANSACTION_NUMBER]},`); // 53
            break;
        default:
            return "";
    }
    const trama = ordered.join(",");
    return `${terminalName}_${trama}${computeLRC(trama)}`;
}

/**
 * Normalises a terminal answer into `{ code, values }` with `values` keyed by
 * protocol position as strings.
 *
 * Two shapes have to be accepted, and only one of them is what the field
 * `functionsFields.ini` describes:
 *
 * - the real bridge serialises a `LinkedHashMap` (WebSocketServer.parseResponse),
 *   so the answer arrives as an OBJECT whose keys are exactly the positions of
 *   `OUTPUT_FIELDS_01` (0, 1, 40, 41, 42, 80, 43 ...).
 * - a plain positional array, which is what an ISO message looks like before the
 *   bridge maps it, and what the development simulator of this module used to
 *   emit.
 *
 * Accepting only one of the two fails silently against the other: an object
 * answer would be reported as "error de trama" on real terminals.
 *
 * @returns {{code: String, values: Object}|null} null when the answer is unusable
 */
export function parseAnswer(raw) {
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch (error) {
        return null;
    }
    if (Array.isArray(parsed)) {
        const values = {};
        parsed.forEach((value, position) => {
            values[String(position)] = value;
        });
        return { code: String(parsed[0]), values };
    }
    if (parsed && typeof parsed === "object") {
        const values = {};
        for (const [position, value] of Object.entries(parsed)) {
            values[String(position)] = value;
        }
        const code = values[ANSWER.CODE];
        if (code === undefined) {
            return null;
        }
        return { code: String(code), values };
    }
    return null;
}

/**
 * Values the server tax map uses to say which message position a tax feeds.
 */
export const TAX_KINDS = { VAT: "vat", IAC: "iac" };

/**
 * Split the taxes of an order into the amounts the terminal expects.
 *
 * `perLineTaxes` is a list - one entry per order line - of `{taxId, amount}`
 * objects. Where those numbers live in the order is Odoo-version knowledge and
 * stays in the caller, so this function remains pure and checkable.
 *
 * Classification comes from the map the server built out of the tax *group*
 * names. Non-positive amounts never travel (withholdings are not part of the
 * message), and amounts whose tax is absent from the map land in `other`, which
 * lets the caller tell "no taxes" apart from "taxes I was not told how to
 * report".
 *
 * @returns {{vat: number, iac: number, classified: number, other: number}}
 */
export function taxBreakdown(taxMap, perLineTaxes) {
    let vat = 0;
    let iac = 0;
    let classified = 0;
    let other = 0;

    for (const lineTaxes of perLineTaxes || []) {
        for (const entry of lineTaxes || []) {
            const amount = Number(entry?.amount) || 0;
            if (amount <= 0) {
                continue;
            }
            const kind = (taxMap || {})[entry?.taxId];
            if (kind === TAX_KINDS.VAT) {
                vat += amount;
                classified += amount;
            } else if (kind === TAX_KINDS.IAC) {
                iac += amount;
                classified += amount;
            } else {
                other += amount;
            }
        }
    }

    return { vat, iac, classified, other };
}

/**
 * Amount actually charged: terminal total plus what the customer left as tip on
 * the device.  The terminal is the authority here, not the cashier's entry.
 */
export function getChargedAmount(values) {
    const total = Number(values[ANSWER.TOTAL]);
    const tip = Number(values[ANSWER.TIP] || 0);
    if (!Number.isFinite(total)) {
        return null;
    }
    return total + (Number.isFinite(tip) ? tip : 0);
}

/**
 * One protocol text field, checked against the length the terminal accepts.
 *
 * Nothing is ever cut here: an identifier that does not fit is an error that IT
 * has to see (a silently shortened cash register or transaction number can be
 * paired with somebody else's answer), so the caller refuses the payment and
 * reports which field and how long the value was.
 *
 * @returns {{value: String, digits: Integer, overflow: Boolean}}
 */
export function protocolField(label, value, digits) {
    const text = String(value ?? "");
    return { label, value: text, digits, overflow: text.length > digits };
}

/**
 * Currency amount as the terminal expects it: whole units, no separators.
 */
export function protocolAmount(label, value, digits) {
    const rounded = Math.round(Number(value) || 0);
    return protocolField(label, rounded, digits);
}


/**
 * Position 83 of the message: the cashier, first name only, as Odoo 17 has
 * always sent it.
 *
 * The employee record keeps its full name in the database; only this wire
 * representation is limited, and a truncated one is reported so the length can
 * be reviewed instead of silently becoming somebody else's operator code.
 *
 * @returns {{value: String, truncated: Boolean, full: String}}
 */
export function operatorRepresentation(name, digits = OPERATOR_DIGITS) {
    const full = String(name || "").trim();
    const token = full.split(/\s+/)[0] || "";
    if (token.length > digits) {
        return { value: token.slice(0, digits), truncated: true, full };
    }
    return { value: token, truncated: false, full };
}

/**
 * Position 42 of the message: the cash register, composed the way the Odoo 17
 * integration always built it -- the POS session id concatenated with the
 * cashier id, with no separator.
 *
 * This is not an invention of the migration: it is the serialisation Credibanco
 * certified, so it has to stay byte-identical.  What 17 got wrong -- silently
 * truncating a value that overflowed the 10 characters the protocol allows -- is
 * not reproduced: an identifier that does not fit is refused, never shortened,
 * because a shortened cash register could be echoed back against another box's
 * sale when a payment is cancelled.
 *
 * @returns {{value: String, digits: Integer, overflow: Boolean}}
 */
export function cashRegisterRepresentation(sessionId, cashierId, digits = FIELD_LIMITS.cashRegister) {
    const value = `${sessionId ?? ""}${cashierId ?? ""}`;
    return { value, digits, overflow: value.length > digits };
}
