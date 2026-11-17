# -*- coding: utf-8 -*-
"""Clara public API v3 client, read-only: every data call is a GET. The only POST is the OAuth 2.0 client-credentials
token request, which is authentication, not a write. mTLS certificates are written to temporary files for the
duration of each request."""
import base64
import logging
import os
import tempfile
from datetime import datetime, timedelta

import requests
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 100            # the API's maximum "size" (Clara's documentation); larger values are capped
DEFAULT_PAGE_SIZE = 100
PARAM_PAGE_SIZE = "clara_connector.page_size"
PARAM_TIMEOUT = "clara_connector.clara_request_timeout"
PARAM_CALL_LIMIT = "clara_connector.monthly_call_limit"
PARAM_TOKEN = "clara_connector.access_token"
PARAM_TOKEN_EXPIRY = "clara_connector.access_token_expiry"


class RetryableError(Exception):
    """Transient Clara API error (429, 5xx, network): the next sync tries again."""


class ClaraAPIService:
    def __init__(self, env):
        self.env = env
        # the credentials are readable by Clara administrators only (field groups): the service reads them as superuser,
        # so the weekly cron and the sync button work whoever runs them
        company = self.env.company.sudo()
        self.country = company.clara_country or "co"
        self.client_id = company.clara_client_id
        self.client_secret = company.clara_client_secret
        self.tax_identifier = company.clara_tax_identifier
        config = self.env["ir.config_parameter"].sudo()
        self.timeout = int(config.get_param(PARAM_TIMEOUT, 30) or 30)
        self.page_size = self.page_size_param(self.env)
        self.base_url = f"https://public-api.{self.country}.clara.com"
        self.ca_cert = company.clara_ca_cert
        self.client_cert = company.clara_client_cert
        self.client_key = company.clara_client_key

    @staticmethod
    def page_size_param(env):
        """The configured page size, within 1 and the API's maximum."""
        value = env["ir.config_parameter"].sudo().get_param(PARAM_PAGE_SIZE, DEFAULT_PAGE_SIZE)
        try:
            return max(1, min(int(value), MAX_PAGE_SIZE))
        except (TypeError, ValueError):
            return DEFAULT_PAGE_SIZE

    # ---------------------------------------------------------------- certificates
    def _create_temp_cert_files(self):
        """Write the base64 certificates to temporary files and return their paths. The caller deletes them."""
        if not self.client_cert or not self.client_key:
            raise UserError(_("Faltan los certificados mTLS de Clara. Cárgalos en Ajustes › Clara."))
        ca_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        ca_file.write(base64.b64decode(self.ca_cert) if self.ca_cert else b"")
        ca_file.close()
        cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        cert_file.write(base64.b64decode(self.client_cert))
        cert_file.close()
        key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        key_file.write(base64.b64decode(self.client_key))
        key_file.close()
        return ca_file.name, cert_file.name, key_file.name

    def _cleanup_temp_files(self, *file_paths):
        for path in file_paths:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError as e:
                    _logger.warning("Failed to delete temp cert file %s: %s", path, e)

    # ---------------------------------------------------------------- errors
    def _handle_response_error(self, response):
        status = response.status_code
        if status < 400:
            return
        try:
            body = response.json()
        except ValueError:
            body = response.text
        detail = ""
        if isinstance(body, dict):
            detail = " · ".join(str(body[k]) for k in ("message", "error", "requestId") if body.get(k))
        suffix = (" [Clara %s: %s]" % (status, detail)) if detail else (" [Clara %s]" % status)
        if status == 401:
            # the cached token belongs to the credentials it was issued with: drop it so the next call asks for a new one
            self.env["ir.config_parameter"].sudo().search([("key", "in", (PARAM_TOKEN, PARAM_TOKEN_EXPIRY))]).unlink()
            raise UserError(_("Clara rechazó la autenticación. Revisa el Client ID, el Secret y los certificados.") + suffix)
        if status == 403:
            raise UserError(_("Clara rechazó la autorización. Verifica que el usuario de la API tenga el rol Company Owner.") + suffix)
        if status == 429:
            raise RetryableError(_("Se alcanzó el límite de llamadas de Clara. La próxima sincronización lo intentará de nuevo."))
        if status >= 500:
            # keep Clara's own message and requestId: that is what Clara support asks for
            _logger.warning("Clara API %s on %s: %s", status, response.url, detail or body)
            raise RetryableError(_("El servicio de Clara no está disponible por ahora. Intenta más tarde.") + suffix)
        _logger.error("Clara API Error %s: %s", status, body)
        raise UserError(_("La API de Clara devolvió el error %s: %s") % (status, body))

    # ---------------------------------------------------------------- token (the only POST: OAuth 2.0 client credentials)
    def get_token(self):
        config = self.env["ir.config_parameter"].sudo()
        token = config.get_param(PARAM_TOKEN)
        expiry_str = config.get_param(PARAM_TOKEN_EXPIRY)
        if token and expiry_str:
            expiry = datetime.fromisoformat(expiry_str)
            if datetime.now() < (expiry - timedelta(seconds=60)):
                return token
        if not self.client_id or not self.client_secret:
            raise UserError(_("Faltan el Client ID y el Secret de Clara en Ajustes › Clara."))
        ca_path = cert_path = key_path = None
        try:
            ca_path, cert_path, key_path = self._create_temp_cert_files()
            raw = f"{self.client_id}:{self.client_secret}"
            headers = {
                "Authorization": "Basic " + base64.b64encode(raw.encode("utf-8")).decode("utf-8"),
                "Content-Type": "application/x-www-form-urlencoded",
            }
            try:
                response = requests.post(f"{self.base_url}/oauth/token", data={"grant_type": "client_credentials"}, headers=headers,
                                         cert=(cert_path, key_path), verify=True, timeout=self.timeout)
            except requests.exceptions.RequestException as e:
                _logger.error("Clara API network error: %s", e)
                raise RetryableError(_("Error de red al conectar con la API de Clara: %s") % e)
            self._handle_response_error(response)
            resp_json = response.json()
            new_token = resp_json.get("access_token")
            expires_in = resp_json.get("expires_in", 3600)
            config.set_param(PARAM_TOKEN, new_token)
            config.set_param(PARAM_TOKEN_EXPIRY, (datetime.now() + timedelta(seconds=expires_in)).isoformat())
            return new_token
        finally:
            self._cleanup_temp_files(ca_path, cert_path, key_path)

    # ---------------------------------------------------------------- GET
    def _request(self, method, endpoint, params=None):
        """One call to Clara. The module is read-only: anything but GET is refused here, before any request is sent."""
        if (method or "").upper() != "GET":
            raise UserError(_("El conector de Clara es de solo lectura: no envía %s a %s.") % (method, endpoint))
        if not self.tax_identifier:
            raise UserError(_("El NIT de la compañía es obligatorio para sincronizar con Clara (Ajustes › Clara)."))
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}", "X-Tax-Identifier": self.tax_identifier, "Content-Type": "application/json"}
        url = f"{self.base_url}{endpoint}"
        ca_path = cert_path = key_path = None
        self._count_call()
        try:
            ca_path, cert_path, key_path = self._create_temp_cert_files()
            try:
                response = requests.request("GET", url, headers=headers, params=params, cert=(cert_path, key_path), verify=True, timeout=self.timeout)
            except requests.exceptions.RequestException as e:
                _logger.error("Clara API network error: %s", e)
                raise RetryableError(_("Error de red al conectar con la API de Clara: %s") % e)
            self._handle_response_error(response)
            try:
                resp_json = response.json()
                _logger.debug("Clara API response [GET %s]: %s", endpoint, str(resp_json)[:500])
                return resp_json
            except ValueError:
                _logger.debug("Clara API response [GET %s]: %s", endpoint, response.text[:500])
                return {}
        finally:
            self._cleanup_temp_files(ca_path, cert_path, key_path)

    def _get(self, endpoint, params=None):
        return self._request("GET", endpoint, params=params)

    def _paginate(self, endpoint, params, data_key=None, max_records=None):
        """Every page of a paginated endpoint, with the configured page size. Stops at Clara's ``last`` flag, at a short
        page, or when ``max_records`` is reached."""
        results = []
        params = dict(params or {})
        params.setdefault("size", self.page_size)
        page = params.get("page", 0)
        while True:
            params["page"] = page
            try:
                data = self._get(endpoint, params=params)
            except RetryableError:
                if not results:
                    raise
                # some Clara endpoints fail past a certain offset instead of returning an empty page: keep what was read
                _logger.warning("Clara sync: %s stopped paginating early at page %s after a server error; %s record(s) kept", endpoint, page, len(results))
                break
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = []
                for key in [data_key, "content", "data", "items"]:
                    if key and isinstance(data.get(key), list):
                        items = data[key]
                        break
                if not items:
                    items = next((v for v in data.values() if isinstance(v, list)), [])
            else:
                items = []
            if not items:
                break
            results.extend(items)
            if max_records and len(results) >= max_records:
                break
            if len(items) < params["size"]:
                break   # a short page is the last one
            if isinstance(data, dict):   # a bare list says nothing about the next page: it is asked for
                meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
                if data.get("last") is True or meta.get("last") is True:
                    break
                raw_total = meta.get("totalPages") or data.get("totalPages")
                if raw_total is not None:
                    try:
                        if page >= int(str(raw_total)) - 1:
                            break
                    except (ValueError, TypeError):
                        pass
            page += 1
        return results[:max_records] if max_records else results

    # ---------------------------------------------------------------- endpoints (all GET)
    def get_transactions(self, from_date=None, to_date=None, updated_since=None, page=0, limit=None, max_records=None):
        """Transactions by operation date (``from_date``/``to_date``) or, when ``updated_since`` is given, only those
        Clara created or updated since that date (``lastUpdateDateRangeStart``): what a weekly sync needs."""
        params = {"size": limit or self.page_size, "page": page}
        if updated_since:
            params["lastUpdateDateRangeStart"] = updated_since.strftime("%Y-%m-%d")
        if from_date:
            params["operationDateRangeStart"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["operationDateRangeEnd"] = to_date.strftime("%Y-%m-%d")
        return self._paginate("/api/v3/transactions", params, data_key="content", max_records=max_records)

    def get_cards(self, page=0, limit=None, max_records=None):
        params = {"size": limit or self.page_size, "page": page}
        return self._paginate("/api/v3/cards", params, data_key="content", max_records=max_records)

    # ---------------------------------------------------------------- quota
    def _count_call(self):
        """Monthly call counter against the plan's quota (Libertario: about 3,000 calls a month)."""
        config = self.env["ir.config_parameter"].sudo()
        key = "clara_connector.calls_" + datetime.now().strftime("%Y%m")
        count = int(config.get_param(key, "0") or 0) + 1
        config.set_param(key, str(count))
        limit = int(config.get_param(PARAM_CALL_LIMIT, "0") or 0)
        if limit and count > limit:
            raise UserError(_("Se alcanzó la cuota mensual de llamadas a Clara (%s). Sube el límite en Ajustes o espera al próximo mes.") % limit)
        return count
