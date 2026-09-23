/** @odoo-module */

/**
 * WebSocket transport of the terminal bridge.
 *
 * Three properties are load-bearing:
 *
 * 1. Every failure settles the promise. The payment screen blocks while waiting
 *    and a promise left pending would freeze the register until the page is
 *    reloaded, so `timeout`, `onerror` and `onclose` all reject.
 * 2. One connection per browser and one request in flight. The bridge answers
 *    every connected browser (it broadcasts), and the terminal itself only
 *    handles one transaction at a time, so serialising here keeps a response
 *    from being applied to the wrong operation.
 * 3. A response is only accepted when it carries the positions that identify the
 *    request it belongs to, when those positions exist in that kind of answer
 *    (see functionsFields.ini). It is a second line of defence on top of the
 *    serialisation; the first one is the bridge replying to its requester.
 */
import { parseAnswer } from "@pos_api_credibanco/app/utils/payment/credibanco_protocol";

const DEFAULT_TIMEOUT_MS = 100000;

export class CredibancoTransport {
    constructor() {
        this.socket = null;
        this.queue = [];
        this.inFlight = null;
    }

    /**
     * @param {String} packet fully built protocol packet
     * @param {Object} config { ip_host, port, timeout, expect }
     * @returns {Promise<String>} raw terminal answer belonging to this request
     */
    send(packet, config = {}) {
        return new Promise((resolve, reject) => {
            this.queue.push({ packet, config, resolve, reject });
            this._pump();
        });
    }

    /**
     * Drops the connection and fails the request in flight. Used when the cashier
     * cancels or leaves the payment screen: a late answer must not be applied to
     * anything. Queued requests are kept: they reconnect on their own.
     */
    abort() {
        const pending = this.inFlight;
        this.inFlight = null;
        this._closeSocket();
        if (pending) {
            clearTimeout(pending.timer);
            pending.reject(new Error("credibanco_aborted"));
        }
        this._pump();
    }

    async _pump() {
        if (this.inFlight || !this.queue.length) {
            return;
        }
        const job = this.queue.shift();
        this.inFlight = job;
        try {
            await this._connect(job);
        } catch (error) {
            this._settle(job, "reject", error);
            this._pump();
        }
    }

    _connect(job) {
        return new Promise((resolve, reject) => {
            const { config } = job;
            const socket = new WebSocket(this._url(config));
            this.socket = socket;
            job.socket = socket;

            const timeout =
                (Number(config.timeout) || DEFAULT_TIMEOUT_MS / 1000) * 1000;
            job.timer = setTimeout(() => {
                reject(new Error("credibanco_timeout"));
                this._closeSocket();
            }, timeout);

            socket.onopen = () => socket.send(job.packet);
            socket.onmessage = (event) => {
                if (!this._belongs(job, event.data)) {
                    // Somebody else's answer (the bridge broadcasts): ignore it
                    // and keep waiting for ours, or time out honestly.
                    return;
                }
                resolve(event.data);
                this._closeSocket();
            };
            socket.onerror = () => reject(new Error("credibanco_connection_error"));
            socket.onclose = () => reject(new Error("credibanco_closed"));
        }).then(
            (raw) => this._settle(job, "resolve", raw),
            (error) => this._settle(job, "reject", error)
        );
    }

    /**
     * Does this answer belong to this request?
     *
     * `expect` maps protocol positions to the values sent. A position the answer
     * does not carry at all (anulación and recovery answers have no 42/53) cannot
     * be checked and does not veto the match, which is why only the operations
     * whose answer repeats them are matched.
     */
    _belongs(job, raw) {
        const expect = job.config.expect;
        if (!expect || !Object.keys(expect).length) {
            return true;
        }
        const parsed = parseAnswer(raw);
        if (!parsed) {
            return false;
        }
        return Object.entries(expect).every(([position, value]) => {
            if (value === undefined || value === null || value === "") {
                // Nothing to compare against: the position is not in this answer.
                return true;
            }
            const answer_value = parsed.values[String(position)];
            if (answer_value === undefined) {
                // The answer of this operation does not carry the position, so it
                // cannot prove nor disprove the match.
                return true;
            }
            return String(answer_value).trim() === String(value).trim();
        });
    }

    _settle(job, kind, value) {
        clearTimeout(job.timer);
        if (this.inFlight === job) {
            this.inFlight = null;
        }
        job[kind](value);
        this._pump();
    }

    _closeSocket() {
        const socket = this.socket;
        this.socket = null;
        if (socket && socket.readyState <= WebSocket.OPEN) {
            socket.onclose = null;
            socket.onerror = null;
            socket.onmessage = null;
            try {
                socket.close();
            } catch (error) {
                // Already closing.
            }
        }
    }

    /**
     * A POS served over https cannot open a plain ws:// socket: the browser
     * blocks it as mixed content and the failure shows up as an opaque connection
     * error. Following the page protocol reaches a TLS-terminated bridge and
     * keeps the error meaning what it says. If the bridge has no TLS, the POS
     * must be served over http on the local network.
     */
    _url({ ip_host, port }) {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${protocol}//${ip_host}:${port}/ws`;
    }
}
