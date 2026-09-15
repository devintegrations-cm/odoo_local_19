/** @odoo-module **/

import {
    barcodeSrc,
    buildFallbackText,
    buildReviewUrl,
    buildVCardPayload,
    buildWhatsappUrl,
    buildWifiPayload,
    imageDataUrl,
    isDataUrl,
    resolvePlaceholders,
} from "@pos_ticket_customization/utils/receipt_block_utils";

QUnit.module("pos_ticket_customization > receipt_block_utils", {});

// ---------------------------------------------------------------- marcadores

QUnit.test("los marcadores conocidos se sustituyen", (assert) => {
    const context = { order_name: "Orden 001", total: "$15.000", store_name: "Chapinero" };
    assert.strictEqual(
        resolvePlaceholders("{order_name} en {store_name}: {total}", context),
        "Orden 001 en Chapinero: $15.000"
    );
});

QUnit.test("un marcador desconocido o vacío se deja intacto", (assert) => {
    // Es deliberado: así el error de configuración se ve en la pantalla de recibo
    // antes de imprimir, en vez de dejar un hueco silencioso en el ticket.
    assert.strictEqual(resolvePlaceholders("{desconocido}", {}), "{desconocido}");
    assert.strictEqual(resolvePlaceholders("{table}", { table: "" }), "{table}");
    assert.strictEqual(resolvePlaceholders("", {}), "");
});

QUnit.test("un payload JSON no se confunde con marcadores", (assert) => {
    const json = '{"amt":100,"cur":"COP"}';
    assert.strictEqual(resolvePlaceholders(json, {}), json);
});

// -------------------------------------------------------------------- URL

QUnit.test("barcodeSrc usa la query string, no la ruta", (assert) => {
    // La forma `/report/barcode/QR/<valor>` rompe el enrutado con valores que
    // llevan `/` o saltos de línea, porque Werkzeug des-escapa el segmento.
    const src = barcodeSrc("QR", "BEGIN:VCARD\r\nURL:https://a.co/b\r\nEND:VCARD");
    assert.ok(src.startsWith("/report/barcode/?"), "va por query string");
    assert.ok(src.includes("%0D%0A"), "los CRLF quedan codificados");
    assert.ok(src.includes("%2F"), "las barras quedan codificadas");
    assert.notOk(src.includes("humanreadable"), "no se manda si no se pide");
});

QUnit.test("barcodeSrc respeta tamaño y valor legible", (assert) => {
    const src = barcodeSrc("Code128", "ORDEN-42", {
        width: 300,
        height: 60,
        humanReadable: true,
    });
    assert.ok(src.includes("width=300") && src.includes("height=60"));
    assert.ok(src.includes("humanreadable=1"));
});

QUnit.test("isDataUrl distingue imagen incrustada de URL al servidor", (assert) => {
    assert.ok(isDataUrl("data:image/png;base64,iVBOR"));
    assert.notOk(isDataUrl("/report/barcode/?barcode_type=QR"));
    assert.notOk(isDataUrl(null));
    assert.notOk(isDataUrl(undefined));
});

QUnit.test("imageDataUrl deduce el tipo de la firma del binario", (assert) => {
    assert.ok(imageDataUrl("iVBORw0KGgo").startsWith("data:image/png;"));
    assert.ok(imageDataUrl("/9j/4AAQ").startsWith("data:image/jpeg;"));
    assert.ok(imageDataUrl("R0lGODlh").startsWith("data:image/gif;"));
    assert.ok(imageDataUrl("UklGRiQ").startsWith("data:image/webp;"));
    assert.strictEqual(imageDataUrl(""), null);
});

// ------------------------------------------------------------------- WiFi

QUnit.test("el payload de WiFi escapa los caracteres reservados", (assert) => {
    const payload = buildWifiPayload({
        wifi_ssid: "Libertario; Guest",
        wifi_password: 'pa,ss"w:ord',
        wifi_security: "WPA",
        wifi_hidden: true,
    });
    assert.strictEqual(payload, 'WIFI:T:WPA;S:Libertario\\; Guest;P:pa\\,ss\\"w\\:ord;H:true;;');
});

QUnit.test("una red abierta no lleva contraseña", (assert) => {
    // Incluirla vacía confunde a algunos lectores.
    const payload = buildWifiPayload({ wifi_ssid: "Free", wifi_security: "nopass" });
    assert.strictEqual(payload, "WIFI:T:nopass;S:Free;;");
    assert.notOk(payload.includes("P:"));
});

// ------------------------------------------------------------------ vCard

QUnit.test("la vCard escapa según la RFC 6350 §3.4", (assert) => {
    const lines = buildVCardPayload({
        vcard_name: "Pérez; Juan",
        vcard_org: "Libertario, S.A.S.",
        vcard_address: "Cra 7 #100-20; L3",
    }).split("\r\n");
    assert.ok(lines.includes("FN:Pérez\\; Juan"), "FN es texto simple: el ; va escapado");
    assert.ok(lines.includes("N:Pérez\\; Juan;;;;"), "los ; de N siguen siendo separadores");
    assert.ok(lines.includes("ORG:Libertario\\, S.A.S."));
    assert.ok(lines.includes("ADR;TYPE=WORK:;;Cra 7 #100-20\\; L3;;;;"));
});

QUnit.test("la barra invertida se escapa una sola vez", (assert) => {
    const lines = buildVCardPayload({ vcard_name: "A\\B;C" }).split("\r\n");
    assert.ok(lines.includes("FN:A\\\\B\\;C"));
});

QUnit.test("la vCard se separa con CRLF", (assert) => {
    const payload = buildVCardPayload({ vcard_name: "X" });
    assert.ok(payload.startsWith("BEGIN:VCARD\r\nVERSION:3.0\r\n"));
    assert.ok(payload.endsWith("\r\nEND:VCARD"));
});

// --------------------------------------------------------- WhatsApp/reseña

QUnit.test("el número de WhatsApp se normaliza y el mensaje se codifica", (assert) => {
    const url = buildWhatsappUrl({ wa_number: "+57 300 123 4567" }, "Hola ☕ pedido");
    assert.ok(url.startsWith("https://wa.me/573001234567?text="));
    assert.ok(url.includes("%E2%98%95"), "los acentos y emojis no rompen la query string");
});

QUnit.test("buildReviewUrl acepta URL completa o Place ID", (assert) => {
    assert.strictEqual(buildReviewUrl("https://g.page/r/abc/review"), "https://g.page/r/abc/review");
    assert.strictEqual(
        buildReviewUrl("ChIJabc"),
        "https://search.google.com/local/writereview?placeid=ChIJabc"
    );
});

// ------------------------------------------------------ respaldo sin conexión

QUnit.test("el respaldo del WiFi imprime SSID y clave", (assert) => {
    // Sin conexión el QR no se puede generar; la clave tecleada a mano sigue
    // sirviendo, un hueco en blanco no.
    assert.strictEqual(
        buildFallbackText(
            { block_type: "wifi_qr", wifi_ssid: "Libertario", wifi_password: "cafe2026" },
            ""
        ),
        "Red WiFi: Libertario\nClave: cafe2026"
    );
});

QUnit.test("el respaldo de una red abierta lo dice", (assert) => {
    const text = buildFallbackText(
        { block_type: "wifi_qr", wifi_ssid: "Free", wifi_security: "nopass" },
        ""
    );
    assert.ok(text.includes("Free"));
    assert.notOk(text.includes("Clave"));
});

QUnit.test("el respaldo de los demás tipos", (assert) => {
    assert.strictEqual(
        buildFallbackText({ block_type: "url_qr" }, "https://libertario.co"),
        "https://libertario.co"
    );
    assert.strictEqual(
        buildFallbackText({ block_type: "review_qr" }, "ChIJabc"),
        "https://search.google.com/local/writereview?placeid=ChIJabc"
    );
    assert.strictEqual(
        buildFallbackText({ block_type: "whatsapp_qr", wa_number: "573001234567" }, "", "Hola"),
        "WhatsApp: https://wa.me/573001234567\nHola"
    );
    assert.strictEqual(
        buildFallbackText(
            { block_type: "vcard_qr", vcard_name: "Café", vcard_phone: "+57 300" },
            ""
        ),
        "Café\n+57 300"
    );
    assert.strictEqual(buildFallbackText({ block_type: "separator" }, ""), "");
});
