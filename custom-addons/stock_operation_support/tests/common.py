# -*- coding: utf-8 -*-
"""Preparacion comun de los tests con ORM."""

import base64

from odoo.tests.common import TransactionCase

# Un JPEG minimo valido: basta para que el adaptador reconozca el tipo.
DUMMY_JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9")


def parsed_result(lines, sender=None, receiver=None, signatures=None, lines_unit="UND", **extra):
    """Arma una respuesta de vision con la forma exacta del contrato."""
    result = {
        "remission_ref": "REM-001",
        "issue_date": "2026-09-10",
        "document_type": "remision",
        "sender": sender or {"nit": "900123456", "dv": "7", "name": "CAFES DEL SUR SAS"},
        "receiver": receiver or {"nit": "901234567", "dv": "8", "name": "LIBERTARIO COFFEE"},
        "lines": [
            {
                "sequence": index + 1,
                "description": line[0],
                "code": line[1],
                "quantity": line[2],
                "unit": lines_unit,
                "is_service": False,
            }
            for index, line in enumerate(lines)
        ],
        "signatures": signatures or {
            "sender": {"present": True, "confidence": 0.9, "name": "Juan Entrega",
                       "id_number": "", "note": ""},
            "receiver": {"present": True, "confidence": 0.9, "name": "Ana Recibe",
                         "id_number": "", "note": ""},
        },
        "confidence": 0.9,
        "provider": "test",
        "available": True,
        "error": "",
        "raw_warnings": [],
        "raw": {},
    }
    result.update(extra)
    return result


class FakeVisionAdapter:
    """Adaptador que devuelve lo que le pasen. Ningun test hace red."""

    name = "test"

    def __init__(self, result, units=None):
        self.result = result
        self.units = units
        self.calls = []
        self.unit_calls = []

    def extract(self, file_bytes, filename, hint=None):
        self.calls.append({"filename": filename, "hint": hint, "size": len(file_bytes or b"")})
        return self.result

    def match_units(self, lines, moves):
        self.unit_calls.append({"lines": lines, "moves": moves})
        return self.units(lines, moves) if self.units else None


class SosCase(TransactionCase):
    """Compania con NIT, proveedor con NIT y una recepcion con dos lineas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # El nombre debe ser el mismo que parsed_result() pone como receptor:
        # si no, la regla de razon social avisa con toda la razon y el caso
        # feliz nunca llega a "aprobado".
        cls.company.name = "LIBERTARIO COFFEE"
        cls.company.vat = "901234567-8"
        cls.env["ir.config_parameter"].sudo().set_param("sos.company_nit", "901234567")
        # Los Boolean de Ajustes se guardan a mano; los tests fijan los dos.
        cls.env["ir.config_parameter"].sudo().set_param("sos.party_check", "True")
        cls.env["ir.config_parameter"].sudo().set_param("sos.signature_check", "True")
        # La vision se inyecta simulada en cada test; nunca se llama de verdad.
        cls.env["ir.config_parameter"].sudo().set_param("sos.vision_enabled", "False")
        # Apagada aqui para que los demas tests no muevan inventario; los de
        # validacion automatica la encienden.
        cls.env["ir.config_parameter"].sudo().set_param("sos.auto_validate", "False")

        cls.env.user.group_ids |= cls.env.ref("stock_operation_support.group_sos_manager")

        cls.supplier = cls.env["res.partner"].create({
            "name": "CAFES DEL SUR SAS",
            "is_company": True,
            "vat": "900123456-7",
        })

        cls.product_cafe = cls.env["product.product"].create({
            "name": "Cafe verde excelso",
            "default_code": "CAFE-001",
            "type": "consu",
            "is_storable": True,
        })
        cls.product_bag = cls.env["product.product"].create({
            "name": "Empaque 500 g",
            "default_code": "INT-EMP-500",
            "type": "consu",
            "is_storable": True,
            "seller_ids": [(0, 0, {
                "partner_id": cls.supplier.id,
                "product_code": "EMP-500",
            })],
        })

        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.picking_type_in = cls.warehouse.in_type_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_picking(self, lines=None, confirm=True):
        """Recepcion con las lineas dadas: [(producto, cantidad), ...]."""
        lines = lines or [(self.product_cafe, 100.0), (self.product_bag, 50.0)]
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_in.id,
            "partner_id": self.supplier.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "company_id": self.company.id,
            "move_ids": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "company_id": self.company.id,
            }) for product, qty in lines],
        })
        if confirm:
            picking.action_confirm()
        return picking

    def _create_support(self, picking, **extra):
        values = {
            "picking_id": picking.id,
            "company_id": self.company.id,
            "support_file": DUMMY_JPEG,
            "support_filename": "remision.jpg",
        }
        values.update(extra)
        return self.env["stock.operation.support"].create(values)

    def _validate_with(self, support, result, units=None):
        """Corre el pipeline con un adaptador simulado."""
        from unittest.mock import patch

        from odoo.addons.stock_operation_support.services import vision_adapter

        adapter = FakeVisionAdapter(result, units)
        with patch.object(vision_adapter, "get_vision_adapter", return_value=adapter):
            support.action_validate()
        return adapter

    def _codes(self, support, level=None):
        import json

        findings = json.loads(support.validation_json)["findings"]
        return {f["code"] for f in findings if level is None or f["level"] == level}
