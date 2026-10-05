/** @odoo-module **/
// Zona de arrastrar y soltar del portal (DECISIONS.md #45). Eventos delegados en
// el documento: sirven para cualquier .o_spr_dropzone sin importar cuando se
// dibuje. El input transparente ya recibe el archivo soltado; esto solo resalta
// la zona y muestra el nombre del archivo.

import { patch } from "@web/core/utils/patch";
import { CustomerAddress } from "@portal/interactions/address";

function zoneOf(event) {
    return event.target.closest && event.target.closest(".o_spr_dropzone");
}

function showName(zone) {
    const input = zone.querySelector('input[type="file"]');
    const label = zone.querySelector(".o_spr_dropzone_name");
    const file = input && input.files && input.files[0];
    zone.classList.toggle("o_spr_has_file", Boolean(file));
    if (label) {
        label.textContent = file ? file.name : "";
    }
}

for (const type of ["dragenter", "dragover"]) {
    document.addEventListener(type, (event) => {
        const zone = zoneOf(event);
        if (zone) {
            zone.classList.add("o_spr_dragover");
        }
    });
}
for (const type of ["dragleave", "drop"]) {
    document.addEventListener(type, (event) => {
        const zone = zoneOf(event);
        if (zone) {
            zone.classList.remove("o_spr_dragover");
        }
    });
}
document.addEventListener("change", (event) => {
    const zone = zoneOf(event);
    if (zone && event.target.matches('input[type="file"]')) {
        // Elegir otro archivo quita la marca de error del envio anterior.
        event.target.classList.remove("is-invalid");
        showName(zone);
    }
});

// "Mi cuenta" (/my/account): el envio es AJAX (portal/interactions/address.js) y
// los errores se escriben en #errors, arriba del formulario. Con los documentos
// al final, el proveedor no los veia: tras un envio con errores se lleva la
// pagina hasta ellos. Solo en el formulario del proveedor (tiene dropzones).
patch(CustomerAddress.prototype, {
    // address.js, al cargar y al cambiar el pais, le quita el required y pone
    // label-optional (sin asterisco) a todo lo que no esta en sus
    // required_fields. Los datos de facturacion electronica del proveedor son
    // obligatorios (DECISIONS.md #53 y #58): se marcan de nuevo. Sin
    // _markRequired, que falla con nombres repetidos (many2many + hidden).
    async _onChangeCountry() {
        await super._onChangeCountry(...arguments);
        for (const input of this.addressForm.querySelectorAll("[data-spr-required]")) {
            input.required = true;
            this.addressForm
                .querySelector(`label[for="${input.id}"]`)
                ?.classList.remove("label-optional");
        }
    },

    async saveAddress() {
        await super.saveAddress(...arguments);
        if (this.el.querySelector(".o_spr_dropzone") && this.errorsDiv?.childElementCount) {
            this.errorsDiv.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    },
});
