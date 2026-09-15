/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Utilidades para resolver los bloques de información adicional del ticket.
 *
 * No se usa ninguna librería JS de terceros: los QR y códigos de barras se
 * generan con el endpoint nativo de Odoo `/report/barcode` (ReportLab) y se
 * convierten a `data:` URI para que el ticket no dependa del servidor al imprimir.
 */

/**
 * Construye la URL de una imagen de código para el endpoint nativo.
 *
 * Usamos deliberadamente la forma con query string
 * (`/report/barcode/?barcode_type=..&value=..`) y no la forma de ruta
 * (`/report/barcode/QR/<valor>`) que emplea el helper `qrCodeSrc` del core:
 * el segmento `<path:value>` es des-escapado por Werkzeug antes de enrutar, de
 * modo que un valor con `/` o saltos de línea (vCard, WiFi, URLs con path) puede
 * romper el enrutado. La query string codifica cualquier byte sin ambigüedad.
 *
 * @param {string} barcodeType Nombre de simbología de ReportLab ("QR", "Code128", ...)
 * @param {string} value Valor ya resuelto que se va a codificar
 * @param {{width?: number, height?: number, humanReadable?: boolean}} [options]
 * @returns {string} URL relativa, del mismo origen que Odoo
 */
export function barcodeSrc(barcodeType, value, options = {}) {
    const { width = 150, height = 150, humanReadable = false } = options;
    const params = new URLSearchParams({
        barcode_type: barcodeType,
        value: value,
        width: String(width),
        height: String(height),
    });
    if (humanReadable) {
        params.set("humanreadable", "1");
    }
    return `/report/barcode/?${params.toString()}`;
}

/**
 * ¿El valor ya es una imagen incrustada y no una URL al servidor?
 * @param {string|null} value
 * @returns {boolean}
 */
export function isDataUrl(value) {
    return typeof value === "string" && value.startsWith("data:");
}

/**
 * Descarga una imagen del servidor y la devuelve como `data:` URI.
 *
 * Incrustar la imagen (en vez de dejar `<img src="/report/barcode/?...">`) es
 * obligatorio, no una optimización:
 *
 * 1. Al rasterizar el ticket para la impresora térmica, `html-to-image` cachea
 *    cada recurso por URL PERO borrando todo lo que va detrás de `?` (ver
 *    `getCacheKey` en `point_of_sale/static/src/app/utils/html-to-image.js`, que
 *    solo conserva la query string si le pasan `includeQueryParams`, cosa que el
 *    POS nunca hace). Como todos nuestros códigos son `/report/barcode/?...`,
 *    comparten clave y el primero que se
 *    rasteriza se imprime en TODOS los bloques y en todos los tickets del turno.
 *    Un `data:` URI hace que `embedImageNode()` salga por su `return` inicial y
 *    no pase por esa caché.
 * 2. `/report/barcode` no manda `Cache-Control`, `ETag` ni `Last-Modified`, así
 *    que el navegador revalida contra el servidor: sin conexión, la imagen sale
 *    en blanco. Incrustada, ya no hay petición que hacer.
 *
 * @param {string} url URL del mismo origen que Odoo
 * @returns {Promise<string>} `data:image/png;base64,...`
 * @throws {Error} si la respuesta no llega o no es una imagen
 */
export async function fetchImageDataUrl(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const blob = await response.blob();
    // `/report/barcode` responde 200 con un cuerpo HTML cuando ReportLab falla
    // (p. ej. "Barcode too large"), así que mirar el código de estado no basta.
    if (!blob.type.startsWith("image/")) {
        throw new Error(`la respuesta no es una imagen (${blob.type || "sin tipo"})`);
    }
    return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
    });
}

// Firmas base64 de los formatos de imagen que acepta el campo Binary de Odoo.
const IMAGE_MIME_SIGNATURES = [
    ["/9j/", "image/jpeg"],
    ["iVBOR", "image/png"],
    ["R0lGOD", "image/gif"],
    ["UklGR", "image/webp"],
    ["Qk", "image/bmp"],
];

/**
 * Construye un data URI a partir del base64 que devuelve el loader.
 *
 * El tipo se deduce de la firma del binario en lugar de asumir PNG: un data URI
 * con un MIME que no corresponde puede no renderizarse y dejaría el hueco en
 * blanco justo en la impresión térmica.
 *
 * @param {string} base64
 * @returns {string|null}
 */
export function imageDataUrl(base64) {
    if (!base64) {
        return null;
    }
    const match = IMAGE_MIME_SIGNATURES.find(([prefix]) => base64.startsWith(prefix));
    return `data:${match ? match[1] : "image/png"};base64,${base64}`;
}

/**
 * Sustituye los marcadores `{clave}` por los valores del contexto del pedido.
 *
 * Los marcadores desconocidos se dejan intactos a propósito: así un error de
 * configuración es visible en la pantalla de recibo antes de imprimir, en lugar
 * de convertirse en un hueco silencioso en el ticket del cliente.
 *
 * @param {string} text
 * @param {Object<string, string>} context
 * @returns {string}
 */
export function resolvePlaceholders(text, context) {
    if (!text) {
        return "";
    }
    return String(text).replace(/\{(\w+)\}/g, (token, key) => {
        const value = context[key];
        return value === undefined || value === null || value === "" ? token : String(value);
    });
}

/**
 * Escapa los caracteres reservados del formato de QR de WiFi (`\`, `;`, `,`, `:`, `"`).
 * @param {string} value
 * @returns {string}
 */
function escapeWifiValue(value) {
    return String(value || "").replace(/([\\;,:"])/g, "\\$1");
}

/**
 * Payload estándar de un QR de WiFi: `WIFI:T:WPA;S:<ssid>;P:<password>;H:true;;`
 * @param {Object} block
 * @returns {string}
 */
export function buildWifiPayload(block) {
    const security = block.wifi_security || "WPA";
    const parts = [`T:${security}`, `S:${escapeWifiValue(block.wifi_ssid)}`];
    // Una red abierta no lleva contraseña; incluirla vacía confunde a algunos lectores.
    if (security !== "nopass") {
        parts.push(`P:${escapeWifiValue(block.wifi_password)}`);
    }
    if (block.wifi_hidden) {
        parts.push("H:true");
    }
    return `WIFI:${parts.join(";")};;`;
}

/**
 * Escapa un valor de texto de vCard según la RFC 6350 §3.4: `\`, `;`, `,` y los
 * saltos de línea. El orden importa: la barra invertida se escapa primero para no
 * volver a escapar las que introducen las sustituciones siguientes.
 *
 * Hay que aplicarlo a TODOS los campos, no solo a la dirección: un nombre como
 * "Pérez; Juan" rompe la estructura de componentes de `N:` y deja un `;` suelto
 * en `FN:`, que es un valor de texto simple y no admite separadores.
 *
 * @param {string} value
 * @returns {string}
 */
function escapeVCardValue(value) {
    return String(value || "")
        .replace(/\\/g, "\\\\")
        .replace(/\r?\n/g, "\\n")
        .replace(/,/g, "\\,")
        .replace(/;/g, "\\;");
}

/**
 * Payload vCard 3.0. Se usa CRLF porque es lo que exige la RFC 6350 y lo que
 * mejor toleran los lectores de iOS y Android.
 * @param {Object} block
 * @returns {string}
 */
export function buildVCardPayload(block) {
    const name = escapeVCardValue(block.vcard_name);
    const lines = ["BEGIN:VCARD", "VERSION:3.0", `FN:${name}`];
    if (block.vcard_name) {
        // Los `;` de `N:` son separadores de componente (apellido;nombre;...) y
        // por eso van fuera de `escapeVCardValue`.
        lines.push(`N:${name};;;;`);
    }
    if (block.vcard_org) {
        lines.push(`ORG:${escapeVCardValue(block.vcard_org)}`);
    }
    if (block.vcard_phone) {
        lines.push(`TEL;TYPE=WORK,VOICE:${escapeVCardValue(block.vcard_phone)}`);
    }
    if (block.vcard_email) {
        lines.push(`EMAIL;TYPE=WORK:${escapeVCardValue(block.vcard_email)}`);
    }
    if (block.vcard_website) {
        lines.push(`URL:${escapeVCardValue(block.vcard_website)}`);
    }
    if (block.vcard_address) {
        lines.push(`ADR;TYPE=WORK:;;${escapeVCardValue(block.vcard_address)};;;;`);
    }
    lines.push("END:VCARD");
    return lines.join("\r\n");
}

/**
 * Enlace de WhatsApp con mensaje prellenado.
 * El mensaje se codifica DESPUÉS de resolver los marcadores, para que un valor
 * con espacios o acentos (p. ej. el nombre del cliente) no rompa la query string.
 * @param {Object} block
 * @param {string} resolvedMessage
 * @returns {string}
 */
export function buildWhatsappUrl(block, resolvedMessage) {
    const number = String(block.wa_number || "").replace(/[^\d]/g, "");
    const base = `https://wa.me/${number}`;
    return resolvedMessage ? `${base}?text=${encodeURIComponent(resolvedMessage)}` : base;
}

/**
 * URL de reseña de Google. Acepta tanto una URL completa (enlace corto de la
 * ficha del negocio) como un Place ID pelado.
 * @param {string} value
 * @returns {string}
 */
export function buildReviewUrl(value) {
    const content = String(value || "").trim();
    if (/^https?:\/\//i.test(content)) {
        return content;
    }
    return `https://search.google.com/local/writereview?placeid=${encodeURIComponent(content)}`;
}

/**
 * Texto que sustituye al código cuando la imagen no se puede generar.
 *
 * Un QR se genera en el servidor; si el POS está sin conexión y el código no
 * estaba ya incrustado, la alternativa a esto sería un hueco en blanco. Se
 * imprime la misma información en claro para que el ticket siga sirviendo: la
 * clave del WiFi se puede teclear, la URL se puede escribir, el teléfono se puede
 * marcar. Es peor perder el dato que perder el QR.
 *
 * @param {Object} block Registro tal cual lo carga el POS
 * @param {string} content `content` con los marcadores ya resueltos
 * @param {string} [resolvedMessage] `wa_message` con los marcadores ya resueltos
 * @returns {string} Texto listo para imprimir, o "" si no hay nada que decir
 */
export function buildFallbackText(block, content, resolvedMessage = "") {
    switch (block.block_type) {
        case "barcode":
        case "url_qr":
        case "qr_text":
        case "payment_qr":
            return content;
        case "review_qr":
            return buildReviewUrl(content);
        case "whatsapp_qr": {
            const lines = [`${_t("WhatsApp")}: ${buildWhatsappUrl(block, "")}`];
            if (resolvedMessage) {
                lines.push(resolvedMessage);
            }
            return lines.join("\n");
        }
        case "wifi_qr": {
            const lines = [`${_t("Red WiFi")}: ${block.wifi_ssid || ""}`];
            if ((block.wifi_security || "WPA") === "nopass") {
                lines.push(_t("Red abierta, sin contraseña"));
            } else if (block.wifi_password) {
                lines.push(`${_t("Clave")}: ${block.wifi_password}`);
            }
            return lines.join("\n");
        }
        case "vcard_qr":
            return [
                block.vcard_name,
                block.vcard_org,
                block.vcard_phone,
                block.vcard_email,
                block.vcard_website,
                block.vcard_address,
            ]
                .filter(Boolean)
                .join("\n");
        default:
            return "";
    }
}
