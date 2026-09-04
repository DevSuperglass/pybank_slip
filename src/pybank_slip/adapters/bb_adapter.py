import requests
from ..utils import safe_json_loads
from typing import Dict, Any, Optional
from ..interfaces import BaseBankAdapter
from ..auth import OAuthCredentials
from requests.auth import HTTPBasicAuth

class BancoDoBrasilAdapter(BaseBankAdapter):
    def _set_urls(self):
        if self.environment == 'sandbox':
            self.base_url = "https://api.hm.bb.com.br"
            self.token_url = "https://oauth.hm.bb.com.br/oauth/token"
        else:
            self.base_url = "https://api.bb.com.br"
            self.token_url = "https://oauth.bb.com.br/oauth/token"
            
        self.route_bank_slips = "/cobrancas/v2/boletos"

    """
    Bank slip adapter for Banco do Brasil API V2.
    """

    def __init__(self, credentials: OAuthCredentials, environment: str = 'production', **kwargs):
        self.credentials = credentials
        self.environment = environment.lower()
        self._set_urls()
        self._token = None

    def _get_token(self) -> str:
        """Fetches the OAuth2 Bearer token from Banco do Brasil."""
        if self._token:
            return self._token

        payload = {"grant_type": "client_credentials", "scope": "cobrancas.boletos-info cobrancas.boletos-requisicao"}
        
        response = requests.post(
            self.token_url,
            data=payload,
            auth=HTTPBasicAuth(self.credentials.client_id, self.credentials.client_secret),
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        self._token = response.json().get("access_token")
        return self._token

    def generate_bank_slip(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        def _is_valid(val):
            if not val:
                return False
            if isinstance(val, str) and (not val.strip() or set(val.strip()) == {"0"}):
                return False
            return True

        if not self.credentials.client_id or not self.credentials.client_secret:
            raise ValueError("Banco do Brasil API credentials missing (client_id and client_secret are required).")
        if not self.credentials.app_key:
            raise ValueError("Application key (app_key) is required in Banco do Brasil credentials.")

        required_fields = ["numeroConvenio", "numeroCarteira", "dataVencimento", "valorOriginal", "pagador"]
        missing = [f for f in required_fields if not _is_valid(payload.get(f))]
        if missing:
            raise ValueError(f"Invalid Banco do Brasil payload. Required fields missing or empty: {', '.join(missing)}")

        pagador = payload.get("pagador", {})
        if isinstance(pagador, dict):
            req_pagador = ["nome", "numeroInscricao", "endereco", "cidade", "uf", "cep"]
            missing_pag = [f for f in req_pagador if not _is_valid(pagador.get(f))]
            if missing_pag:
                raise ValueError(f"Invalid Banco do Brasil payload. Required payer details missing or empty: {', '.join(missing_pag)}")

        payload = self.sanitize_payload(payload)

        token = self._get_token()
        # Ensure the query string uses the correct app_key variable as defined in the credentials
        app_key_qs = f"?gw-dev-app-key={self.credentials.app_key}"
        url = f"{self.base_url}{self.route_bank_slips}{app_key_qs}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        response = requests.post(
            url=url,
            json=payload,
            headers=headers,
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def list_bank_slips(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self._get_token()
        app_key_qs = f"?gw-dev-app-key={self.credentials.app_key}"
        url = f"{self.base_url}{self.route_bank_slips}{app_key_qs}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        
        response = requests.get(
            url=url,
            params=filters,
            headers=headers,
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def get_bank_slip(self, bank_number: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self._get_token()
        app_key_qs = f"?gw-dev-app-key={self.credentials.app_key}"
        url = f"{self.base_url}{self.route_bank_slips}/{bank_number}{app_key_qs}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        numero_convenio = payload.get("numeroConvenio") if payload else getattr(self.credentials, 'numeroConvenio', None)
        params = {}
        if numero_convenio:
            params["numeroConvenio"] = numero_convenio
        response = requests.get(url=url, params=params, headers=headers)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def cancel_bank_slip(self, bank_slip_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self._get_token()
        app_key_qs = f"?gw-dev-app-key={self.credentials.app_key}"
        url = f"{self.base_url}{self.route_bank_slips}{app_key_qs}/{bank_slip_id}/baixar"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if not payload:
            payload = {"numeroConvenio": ""} # Must be filled by the caller
            
        response = requests.post(
            url=url,
            json=payload,
            headers=headers,
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def edit_bank_slip(self, bank_slip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.sanitize_payload(payload)
        token = self._get_token()
        app_key_qs = f"?gw-dev-app-key={self.credentials.app_key}"
        url = f"{self.base_url}{self.route_bank_slips}/{bank_slip_id}{app_key_qs}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        response = requests.patch(
            url=url,
            json=payload,
            headers=headers,
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)
