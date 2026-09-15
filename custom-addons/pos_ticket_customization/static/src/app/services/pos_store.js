/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { formatDateTime } from "@web/core/l10n/dates";
import {
    barcodeSrc,
    buildFallbackText,
    buildReviewUrl,
    buildVCardPayload,
    buildWhatsappUrl,
    buildWifiPayload,
    fetchImageDataUrl,
    imageDataUrl,
    isDataUrl,
    resolvePlaceholders,
} from "@pos_ticket_customization/utils/receipt_block_utils";

const { DateTime } = luxon;

patch(PosStore.prototype, {
    async setup(...args) {
        await super.setup(...arguments);
        this.customReceiptBlocks = this.models["pos.receipt.custom.block"]?.getAll() || [];
        // URL de `/report/barcode` -> imagen ya incrustada como `data:` URI.
        this.customReceiptBlockImages = {};
        // No se espera (`await`) a propósito: no debe retrasar la apertura del POS.
        // `resolveCustomReceiptBlockImages()` vuelve a intentarlo antes de imprimir.
        this.customReceiptBlockImagesReady = this.preloadCustomReceiptBlockImages();
    },

    /**
     * Incrusta al abrir la sesión las imágenes de los bloques cuyo valor no
     * depende del pedido (WiFi, reseña, vCard, WhatsApp sin marcadores...).
     *
     * Es el momento fiable para hacerlo: acabamos de hablar con el servidor para
     * cargar la sesión, así que hay conexión. A partir de aquí esos códigos viven
     * en memoria y el ticket ya no necesita al servidor para imprimirse.
     *
     * @returns {Promise<void>}
     */
    async preloadCustomReceiptBlockImages() {
        const urls = new Set();
        for (const block of this.customReceiptBlocks) {
            const url = this._getStaticBlockCodeUrl(block);
            if (url) {
                urls.add(url);
            }
        }
        await Promise.all([...urls].map((url) => this._embedCustomReceiptBlockImage(url)));
    },

    /**
     * Descarga una imagen de código y la guarda incrustada.
     *
     * Los fallos NO se cachean: si la caja estaba sin conexión al abrir la
     * sesión, el siguiente intento (antes de imprimir) vuelve a probar.
     *
     * @param {string} url
     * @returns {Promise<string|null>} `data:` URI, o `null` si no se pudo generar
     */
    async _embedCustomReceiptBlockImage(url) {
        this.customReceiptBlockImages ||= {};
        if (this.customReceiptBlockImages[url]) {
            return this.customReceiptBlockImages[url];
        }
        try {
            this.customReceiptBlockImages[url] = await fetchImageDataUrl(url);
        } catch (error) {
            console.warn(`No se pudo generar el código del ticket (${url}):`, error);
            return null;
        }
        return this.customReceiptBlockImages[url];
    },

    /**
     * Incrusta las imágenes que falten de un ticket ya resuelto, justo antes de
     * rasterizarlo.
     *
     * Muta los bloques en el sitio y rellena la caché del store: `imgSrc` pasa a
     * ser un `data:` URI o `null`. Nunca se deja una URL a `/report/barcode` en
     * un ticket que va a pasar por `htmlToCanvas`, porque su caché confunde unos
     * códigos con otros (ver `fetchImageDataUrl`). Si la imagen no se puede
     * generar, el bloque se queda sin `imgSrc` y la plantilla imprime
     * `fallbackText` en su lugar.
     *
     * @param {{header: Object[], before_footer: Object[], footer: Object[]}} [groups]
     * @returns {Promise<void>}
     */
    async resolveCustomReceiptBlockImages(groups) {
        if (!groups) {
            return;
        }
        const pending = Object.values(groups)
            .flat()
            .filter((block) => block.codeUrl && !isDataUrl(block.imgSrc));
        await Promise.all(
            pending.map(async (block) => {
                block.imgSrc = await this._embedCustomReceiptBlockImage(block.codeUrl);
            })
        );
    },

    /**
     * Devuelve la URL del código del bloque si no depende del pedido, si no `null`.
     * @param {Object} block
     * @returns {string|null}
     */
    _getStaticBlockCodeUrl(block) {
        const dynamicFields = [block.content, block.wa_message];
        if (dynamicFields.some((value) => value && String(value).includes("{"))) {
            return null;
        }
        const prepared = this._prepareCustomReceiptBlock(block, {});
        return prepared ? prepared.codeUrl : null;
    },

    /**
     * Valores disponibles para los marcadores `{...}` de un bloque.
     * @param {Object} order
     * @returns {Object<string, string>}
     */
    getCustomReceiptBlockContext(order) {
        const partner = order.getPartner && order.getPartner();
        // `getTable` solo existe cuando `pos_restaurant` está instalado.
        const table = order.getTable ? order.getTable() : null;
        return {
            order_name: order.getName ? order.getName() : "",
            total: this.env.utils.formatCurrency(order.priceIncl),
            date: order.date_order ? formatDateTime(order.date_order) : "",
            // Mismo criterio que el recibidor del core: el cajero del pedido, sin
            // caer al cajero actual, para que una reimpresión no atribuya el
            // ticket a quien lo está reimprimiendo.
            cashier: order.getCashierName ? order.getCashierName() : "",
            table: (table && table.name) || "",
            partner_name: (partner && partner.name) || "",
            tracking_number: order.tracking_number || "",
            store_name: this.config.name || "",
        };
    },

    /**
     * Resuelve los bloques aplicables a un pedido, agrupados por posición.
     *
     * @param {Object} order
     * @returns {{header: Object[], before_footer: Object[], footer: Object[]}}
     */
    getCustomReceiptBlocks(order) {
        const grouped = { header: [], before_footer: [], footer: [] };
        const blocks = this.customReceiptBlocks || [];
        if (!blocks.length) {
            return grouped;
        }
        // `today` y las fechas del bloque son objetos luxon (llegaron del servidor
        // como "YYYY-MM-DD" y el core los deserializó al cargar la sesión).
        const today = DateTime.now().startOf("day");
        const total = order.priceIncl;
        const context = this.getCustomReceiptBlockContext(order);
        // `sequence_number` es único dentro de la sesión de caja, se asigna una sola
        // vez y se persiste en el pedido: al reimprimir un ticket salen exactamente
        // los mismos bloques que se imprimieron la primera vez.
        const sequenceNumber = order.sequence_number;

        // El loader ya devuelve los bloques ordenados por `sequence, id`, pero
        // reordenamos por si otro módulo altera la lista en memoria.
        const applicable = blocks
            .filter((block) => this._isCustomReceiptBlockApplicable(block, today, total, sequenceNumber))
            .sort((a, b) => a.sequence - b.sequence || a.id - b.id);

        for (const block of applicable) {
            const prepared = this._prepareCustomReceiptBlock(block, context);
            if (prepared && grouped[prepared.position]) {
                grouped[prepared.position].push(prepared);
            }
        }
        return grouped;
    },

    /**
     * Filtros de vigencia por fecha, importe mínimo y frecuencia.
     */
    _isCustomReceiptBlockApplicable(block, today, total, sequenceNumber) {
        if (block.date_start && block.date_start > today) {
            return false;
        }
        if (block.date_stop && block.date_stop < today) {
            return false;
        }
        if (block.min_amount && total < block.min_amount) {
            return false;
        }
        if (!this._matchesCustomReceiptBlockFrequency(block, sequenceNumber)) {
            return false;
        }
        return true;
    },

    /**
     * ¿Le toca a este pedido dentro del ciclo "cada N pedidos"?
     *
     * @param {Object} block
     * @param {number} sequenceNumber Número del pedido dentro de la sesión de caja
     * @returns {boolean}
     */
    _matchesCustomReceiptBlockFrequency(block, sequenceNumber) {
        const frequency = block.frequency || 1;
        if (frequency <= 1) {
            return true;
        }
        // Sin número de pedido no se puede decidir el ciclo. Se imprime, porque
        // omitir un bloque configurado es peor que repetirlo alguna vez de más.
        if (!Number.isInteger(sequenceNumber)) {
            return true;
        }
        // La doble suma normaliza el resto: en JS `-4 % 10` es -4, no 6, así que
        // un desplazamiento mayor que el número de pedido fallaría sin ella.
        const offset = block.frequency_offset || 0;
        return (((sequenceNumber - offset) % frequency) + frequency) % frequency === 0;
    },

    /**
     * Convierte un bloque de la base de datos en un objeto plano listo para QWeb.
     * @param {Object} block
     * @param {Object<string, string>} context Valores de los marcadores dinámicos
     * @returns {Object|null}
     */
    _prepareCustomReceiptBlock(block, context) {
        const prepared = {
            id: block.id,
            type: block.block_type,
            position: block.position,
            alignment: block.alignment || "center",
            label: resolvePlaceholders(block.label, context),
            text: "",
            // URL a `/report/barcode`: solo la usa `resolveCustomReceiptBlockImages()`
            // para saber qué descargar. Nunca llega a la plantilla.
            codeUrl: null,
            imgSrc: null,
            imageData: null,
            // Qué imprimir si el código no se puede generar (POS sin conexión).
            fallbackText: "",
            width: block.barcode_width || 150,
            height: block.barcode_height || 150,
        };
        const content = resolvePlaceholders(block.content, context);
        const size = { width: prepared.width, height: prepared.height };
        let message = "";

        switch (block.block_type) {
            case "text":
            case "legal_text":
                prepared.text = content;
                break;
            case "separator":
                break;
            case "image":
                if (!block.image) {
                    return null;
                }
                // El loader entrega el binario en base64; incrustarlo evita una
                // llamada extra al servidor y funciona con el POS sin conexión.
                prepared.imageData = imageDataUrl(block.image);
                break;
            case "barcode":
                if (!content) {
                    return null;
                }
                prepared.codeUrl = barcodeSrc(block.barcode_type || "Code128", content, {
                    ...size,
                    humanReadable: block.barcode_humanreadable,
                });
                break;
            case "url_qr":
            case "qr_text":
            case "payment_qr":
                if (!content) {
                    return null;
                }
                prepared.codeUrl = barcodeSrc("QR", content, size);
                break;
            case "review_qr":
                if (!content) {
                    return null;
                }
                prepared.codeUrl = barcodeSrc("QR", buildReviewUrl(content), size);
                break;
            case "whatsapp_qr": {
                if (!block.wa_number) {
                    return null;
                }
                message = resolvePlaceholders(block.wa_message, context);
                prepared.codeUrl = barcodeSrc("QR", buildWhatsappUrl(block, message), size);
                break;
            }
            case "wifi_qr":
                if (!block.wifi_ssid) {
                    return null;
                }
                prepared.codeUrl = barcodeSrc("QR", buildWifiPayload(block), size);
                break;
            case "vcard_qr":
                if (!block.vcard_name) {
                    return null;
                }
                prepared.codeUrl = barcodeSrc("QR", buildVCardPayload(block), size);
                break;
            default:
                return null;
        }

        if (prepared.codeUrl) {
            // Si ya está incrustada se usa tal cual. Si no, se deja la URL para que
            // la pantalla de recibo la muestre igualmente estando en línea; antes de
            // imprimir, `resolveCustomReceiptBlockImages()` la sustituye o la anula.
            prepared.imgSrc = this.customReceiptBlockImages?.[prepared.codeUrl] || prepared.codeUrl;
            prepared.fallbackText = buildFallbackText(block, content, message);
        }
        return prepared;
    },
});