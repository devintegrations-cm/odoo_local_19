# -*- coding: utf-8 -*-
"""Fixtures shared by the connector tests: Clara payloads shaped like the real ones, and two ways of standing in for
Clara's API (the service methods, or the HTTP layer underneath them). Clara is never called."""
import base64
import contextlib
import json
from unittest.mock import patch

from odoo.tests import TransactionCase

from ..services import clara_api_service as svc

MASKED_PAN = "510979******5458"
# a cardholder that is not in the seeded cardholder table (the fresh database seeds the real ones)
HOLDER = "TITULAR PRUEBA CLARA"
HOLDER_UUID = "uuid-titular-prueba-0001"
HOLDER_EMAIL = "titular.prueba@test.local"


def transaction_payload(uuid, comment="", legalization="Approved", amount=56343.0, holder=HOLDER, holder_uuid=HOLDER_UUID,
                        card_uuid="card-1", status="AUTHORIZED", tx_type="PURCHASE", operation_date="2026-10-08",
                        last_update="2026-10-10", receipt=True, merchant="Uber", category="Transportation", document=None):
    user = {"uuid": holder_uuid, "holderName": holder, "links": []}
    if document:
        user["documentNumber"] = document   # Clara does not send it today; if it ever does, it must not be stored
    return {
        "uuid": uuid, "type": tx_type, "transactionLabel": merchant.upper(), "labels": None, "status": status, "comment": comment,
        "audit": {"accountingDate": operation_date, "operationDate": operation_date, "lastUpdateDate": last_update},
        "merchant": {"name": merchant, "mcc": "4121", "description": "Taxicabs and Limousines", "category": category, "categoryCode": 14},
        "card": {"uuid": card_uuid, "maskedPan": MASKED_PAN, "links": []},
        "user": user,
        "authorizationNumber": "807236",
        "originalAmount": {"currency": "COP", "amount": amount}, "amountValue": {"currency": "COP", "amount": amount},
        "validationStatus": {"status": legalization, "comment": "Hola, mil gracias :)"},
        "hasInvoice": {"value": False, "links": []}, "hasAttachments": {"value": receipt, "links": []}, "hasExtractedDocuments": {"value": receipt, "links": []},
        "links": [],
    }


def card_payload(uuid, holder=HOLDER, email=HOLDER_EMAIL, holder_uuid=HOLDER_UUID,
                 status="ACTIVE", lock="UNLOCKED", card_type="MASTER_PHYSICAL", threshold=2000000.0, periodicity="MONTHLY", alias="Clara Física", masked=MASKED_PAN):
    return {
        "uuid": uuid, "claraStatus": status, "status": status, "lockCode": lock, "alias": alias, "threshold": threshold, "periodicity": periodicity,
        "maskedPan": masked, "type": card_type,
        "user": {"uuid": holder_uuid, "fullName": holder, "username": email, "links": []},
        "links": [],
    }


class FakeResponse:
    def __init__(self, payload, status=200, url=""):
        self._payload = payload
        self.status_code = status
        self.url = url
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def fake_http(transactions=(), cards=()):
    """``(request, post, calls)``: stand-ins for ``requests.request`` and ``requests.post`` that page the given records
    the way Clara does (Spring pagination: content, totalPages, last) and record every call."""
    data = {"/api/v3/transactions": list(transactions), "/api/v3/cards": list(cards)}
    calls = []

    def request(method, url, headers=None, params=None, **kwargs):
        params = dict(params or {})
        calls.append({"method": method, "url": url, "params": params})
        path = url.split(".clara.com", 1)[1].split("?")[0]
        items = data.get(path, [])
        size, page = int(params.get("size", 100)), int(params.get("page", 0))
        total_pages = max(1, -(-len(items) // size))
        chunk = items[page * size:(page + 1) * size]
        return FakeResponse({"content": chunk, "totalElements": len(items), "totalPages": total_pages, "last": page >= total_pages - 1, "size": size, "number": page}, url=url)

    def post(url, data=None, headers=None, **kwargs):
        calls.append({"method": "POST", "url": url, "params": {}})
        return FakeResponse({"access_token": "test-token", "expires_in": 3600}, url=url)

    return request, post, calls


class ClaraCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Transaction = self.env["clara.transaction"]
        self.Card = self.env["clara.card"]
        self.Rule = self.env["clara.analytic.rule"]
        self.Order = self.env["purchase.order"]
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param("clara_connector.last_sync_date", False)
        self.icp.set_param("clara_connector.sync_start_date", False)
        self.env.company.partner_id.tz = "America/Bogota"
        self.env.company.write({"clara_country": "co", "clara_client_id": "client-test", "clara_client_secret": "secret-test", "clara_tax_identifier": "900854410",
                                "clara_client_cert": base64.b64encode(b"cert"), "clara_client_key": base64.b64encode(b"key")})
        self.vendor = self.env["res.partner"].create({"name": "PROVEEDOR CLARA TEST", "is_company": True})

    def _user(self, group_xmlid, login):
        Users = self.env["res.users"]
        groups_field = "group_ids" if "group_ids" in Users._fields else "groups_id"   # renamed in Odoo 19
        return Users.create({"name": login, "login": login, groups_field: [(6, 0, [self.env.ref("base.group_user").id, self.env.ref(group_xmlid).id])]})

    def _order(self, name):
        """A purchase order with a known name, created by the test (never by the modules)."""
        return self.Order.create({"name": name, "partner_id": self.vendor.id})

    @contextlib.contextmanager
    def api(self, transactions=(), cards=()):
        """Clara's answers at the service level. Yields the kwargs of every get_transactions call."""
        windows = []

        def get_transactions(service, **kwargs):
            windows.append(kwargs)
            return list(transactions)

        with patch.object(svc.ClaraAPIService, "get_transactions", get_transactions), patch.object(svc.ClaraAPIService, "get_cards", lambda service, **kw: list(cards)):
            yield windows

    @contextlib.contextmanager
    def http(self, transactions=(), cards=()):
        """Clara's answers at the HTTP level: the real service code runs over fake requests. Yields the recorded calls."""
        request, post, calls = fake_http(transactions, cards)
        with patch.object(svc.requests, "request", request), patch.object(svc.requests, "post", post):
            yield calls
