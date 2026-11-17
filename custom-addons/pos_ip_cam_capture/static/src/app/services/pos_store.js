/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

// En 17 se parcheaba Order.prototype.pay; en 19 el botón "Pagar" llama a
// PosStore.pay() (product_screen.xml, pos_restaurant), así que el gancho pasa aquí.
patch(PosStore.prototype, {
    async pay() {
        const order = this.getOrder();
        if (order && this.config.enable_local_ip_camera) {
            // En 17 se enviaba order.uid ("00001-001-0001"), que coincidía con
            // pos_reference ("Order 00001-001-0001") sin letras. En 19 ya no hay uid:
            // pos_reference ("<aa><dispositivo>-<config>-<número>") es la referencia
            // que queda en pos.order, y sin letras sigue siendo igual a sí misma.
            const orderNumber = order.pos_reference;
            const cameraConfig = this.getCameraConfig();
            this.sendWebSocketMessage(orderNumber, cameraConfig);
        }
        return await super.pay(...arguments);
    },

    getCameraConfig() {
        const cameraUrl = this.config.camera_url;
        const cameraUser = this.config.camera_user;
        const cameraPassword = this.config.camera_password;
        const cameraIp = this.config.camera_ip;
        const cameraPort = this.config.camera_port;

        // Verificar que todas las propiedades necesarias estén definidas
        if (!cameraUrl || !cameraUser || !cameraPassword || !cameraIp || !cameraPort) {
            // Solo se informa qué falta: nunca se imprimen los valores (incluyen la contraseña)
            const missing = Object.entries({
                camera_url: cameraUrl,
                camera_user: cameraUser,
                camera_password: cameraPassword,
                camera_ip: cameraIp,
                camera_port: cameraPort,
            })
                .filter(([, value]) => !value)
                .map(([key]) => key);
            console.error("Configuración de la cámara incompleta. Faltan:", missing.join(", "));
            return null;
        }

        return {
            url: cameraUrl,
            ip: cameraIp,
            port: cameraPort,
            user: cameraUser,
            password: cameraPassword,
            rendered_url: this.mapUrl({
                url: cameraUrl,
                user: cameraUser,
                password: cameraPassword,
                ip: cameraIp,
                port: cameraPort,
            }),
        };
    },

    mapUrl(data) {
        const infoMap = {
            "{usr}": "user",
            "{pas}": "password",
            "{ip}": "ip",
            "{port}": "port",
        };
        let url = data.url;
        for (const [key, value] of Object.entries(infoMap)) {
            url = url.replace(new RegExp(key, "g"), data[value]);
        }
        return url;
    },

    sendWebSocketMessage(orderNumber, cameraConfig) {
        const wsUrl = `ws://localhost:8765`;

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            ws.send(
                JSON.stringify({
                    event: "order_validated",
                    order_number: orderNumber,
                    ...cameraConfig,
                })
            );
            console.warn("Mensaje enviado al servidor WebSocket:", orderNumber);
            ws.close();
        };

        ws.onerror = (error) => {
            console.error("Error en la conexión WebSocket:", error);
        };
    },
});
