/** @odoo-module **/
// Kanban and list of the plant board: every column open, always (Odoo folds groups beyond the tenth), and a reload
// whenever the plant alert service hears about a new or changed request, so nobody refreshes the page.
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { RelationalModel } from "@web/model/relational_model/relational_model";

export const PLANT_CHANGED = "plant_request_board:changed";

export class PlantKanbanModel extends RelationalModel {}
PlantKanbanModel.MAX_NUMBER_OPENED_GROUPS = 500;   // Odoo 17
PlantKanbanModel.DEFAULT_OPEN_GROUP_LIMIT = 500;   // Odoo 19: groups opened by default when the kanban loads

export class PlantKanbanController extends KanbanController {
    setup() {
        super.setup();
        useBus(this.env.bus, PLANT_CHANGED, () => this.model.load());
    }
}

export class PlantListController extends ListController {
    setup() {
        super.setup();
        useBus(this.env.bus, PLANT_CHANGED, () => this.model.load());
    }
}

export const plantKanbanView = { ...kanbanView, Model: PlantKanbanModel, Controller: PlantKanbanController };
export const plantListView = { ...listView, Controller: PlantListController };
registry.category("views").add("plant_request_kanban", plantKanbanView);
registry.category("views").add("plant_request_list", plantListView);
