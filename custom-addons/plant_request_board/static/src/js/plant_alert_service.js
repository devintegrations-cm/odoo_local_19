/** @odoo-module **/
// Rings when a store creates a plant request.
// The server sends a "plant_request_board/new" bus notification to the plant users. This service shows a sticky
// notification anywhere in Odoo but only PLAYS THE SOUND while the user is inside the Planta app. Browsers only
// play audio after the user interacted with the page once (any click).
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { url } from "@web/core/utils/urls";

const ALERT_URL = "/plant_request_board/static/src/audio/alert.wav?v=3"; // bump when the sound changes so browsers do not keep the old one
const PLANT_APP = "plant_request_board.menu_plant_root";
const PLANT_CHANGED = "plant_request_board:changed"; // what the plant views listen to in order to reload themselves

export const plantAlertService = {
    dependencies: ["bus_service", "notification", "action", "menu"],
    start(env, { bus_service, notification, action, menu }) {
        const audio = new Audio(url(ALERT_URL));
        audio.preload = "auto";
        bus_service.subscribe("plant_request_board/new", (payload) => {
            const app = menu.getCurrentApp();
            const inPlant = !!app && app.xmlid === PLANT_APP;
            if (inPlant || payload.test) {
                audio.currentTime = 0;
                audio.play().catch(() => {});
            }
            const title = payload.test ? _t("Prueba de alerta de planta") : _t("Nueva solicitud de %s", payload.store || "");
            notification.add(payload.summary || "", {
                title,
                type: payload.test ? "info" : "warning",
                sticky: true,
                buttons: payload.picking_id ? [{
                    name: _t("Abrir solicitud"),
                    primary: true,
                    onClick: () => action.doAction({ type: "ir.actions.act_window", res_model: "stock.picking", res_id: payload.picking_id, views: [[false, "form"]], target: "current" }),
                }] : [],
            });
            env.bus.trigger(PLANT_CHANGED, payload);
        });
        // a tick, a stage change or a delivery by someone else: the open plant views reload, silently
        bus_service.subscribe("plant_request_board/update", (payload) => env.bus.trigger(PLANT_CHANGED, payload));
    },
};
registry.category("services").add("plant_request_board.alert", plantAlertService);
