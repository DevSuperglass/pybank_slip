import requests
from ..utils import safe_json_loads
from typing import Dict, Any, Optional
from ..interfaces import BaseBankAdapter
from ..auth import CertificateAuth, OAuthCredentials
import json

class SicrediAdapter(BaseBankAdapter):
    def _set_urls(self):
        if self.environment == 'sandbox':
            self.base_url = "https://api-parceiro.sicredi.com.br/sb/cobranca/boleto/v1"
            self.token_url = "https://api-parceiro.sicredi.com.br/sb/auth/openapi/token"
        else:
            self.base_url = "https://api-parceiro.sicredi.com.br/cobranca/boleto/v1"
            self.token_url = "https://api-parceiro.sicredi.com.br/auth/openapi/token"

        self.route_bank_slips = "/boletos"

    def __init__(self, credentials: OAuthCredentials, environment: str = 'production', cert_auth: Optional[CertificateAuth] = None):
        """
        credentials.client_id: x-api-key do Sicredi
        credentials.client_secret: password gerado no Internet Banking
        """
        self.credentials = credentials
        self.environment = environment.lower()
        self.cert_auth = cert_auth
        self._set_urls()
        self._token = None

    def _get_token(self, cooperativa: str, codigo_beneficiario: str) -> str:
        """Fetches the OAuth2 Bearer token from Sicredi."""
        if self._token:
            return self._token

        headers = {
            "x-api-key": self.credentials.client_id,
            "context": "COBRANCA",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        import urllib.parse
        
        username = f"{codigo_beneficiario}{cooperativa}"
        password = self.credentials.client_secret

        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "cobranca"
        }

        response = requests.post(
            self.token_url,
            data=urllib.parse.urlencode(data),
            headers=headers,
        )

        # Se falhar com credenciais inválidas no ambiente Sandbox, tenta com os dados de homologação do manual (123456789 / teste123)
        if response.status_code == 401 and "invalid_grant" in response.text and self.environment == 'sandbox':
            for sb_user, sb_pass in [("123456789", "teste123"), (username, "teste123"), ("123456789", password)]:
                data["username"] = sb_user
                data["password"] = sb_pass
                sb_resp = requests.post(
                    self.token_url,
                    data=urllib.parse.urlencode(data),
                    headers=headers,
                )
                if sb_resp.status_code == 200:
                    response = sb_resp
                    break

        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

        self._token = response.json().get("access_token")
        return self._token

    def _build_headers(self, cooperativa: str, posto: str, codigo_beneficiario: str, include_beneficiario_in_header: bool = False) -> Dict[str, str]:
        token = self._get_token(cooperativa, codigo_beneficiario)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
            "cooperativa": cooperativa,
            "posto": posto,
        }
        if include_beneficiario_in_header:
            headers["codigoBeneficiario"] = codigo_beneficiario
        return headers

    def generate_bank_slip(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        def _is_valid(val):
            if not val:
                return False
            if isinstance(val, str) and (not val.strip() or set(val.strip()) == {"0"}):
                return False
            return True

        if not self.credentials.client_secret:
            raise ValueError("API credential 'client_secret' (password) is required for Sicredi.")

        required_fields = ["cooperativa", "posto", "codigoBeneficiario", "dataVencimento", "valor", "pagador"]
        missing = [f for f in required_fields if not _is_valid(payload.get(f))]
        if missing:
            raise ValueError(f"Invalid Sicredi payload. Required fields missing or empty: {', '.join(missing)}")

        pagador = payload.get("pagador", {})
        if isinstance(pagador, dict):
            req_pagador = ["nome", "documento", "endereco", "cidade", "uf", "cep"]
            missing_pag = [f for f in req_pagador if not _is_valid(pagador.get(f))]
            if missing_pag:
                raise ValueError(f"Invalid Sicredi payload. Required payer details missing or empty: {', '.join(missing_pag)}")

        cooperativa = payload.get("cooperativa", "")
        posto = payload.get("posto", "")
        codigo_beneficiario = payload.get("codigoBeneficiario", "")

        headers = self._build_headers(cooperativa, posto, codigo_beneficiario, include_beneficiario_in_header=False)
        url = f"{self.base_url}{self.route_bank_slips}"

        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            # cert=(self.cert_auth.cert_path, self.cert_auth.key_path) if self.cert_auth else None,
            # verify=self.cert_auth.verify if self.cert_auth else True,
        )

        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

        return safe_json_loads(response.text)

    def cancel_bank_slip(self, bank_number: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not payload:
            raise ValueError("Payload is required for cancelling Sicredi bank slips (must contain cooperativa, posto, codigoBeneficiario)")

        cooperativa = payload.get("cooperativa", "")
        posto = payload.get("posto", "")
        codigo_beneficiario = payload.get("codigoBeneficiario", "")

        headers = self._build_headers(cooperativa, posto, codigo_beneficiario, include_beneficiario_in_header=True)
        url = f"{self.base_url}{self.route_bank_slips}/{bank_number}/baixa"

        response = requests.patch(
            url,
            data=json.dumps({}),
            headers=headers,
        )

        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

        return safe_json_loads(response.text)

    def list_bank_slips(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError("List bank slips is not yet implemented for Sicredi.")

    def edit_bank_slip(self, bank_number: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Para alterar vencimento (única alteração coberta por padrão no edit_bank_slip básico caso tenha dataVencimento no payload)
        if "dataVencimento" in payload:
            cooperativa = payload.get("cooperativa", "")
            posto = payload.get("posto", "")
            codigo_beneficiario = payload.get("codigoBeneficiario", "")

            headers = self._build_headers(cooperativa, posto, codigo_beneficiario, include_beneficiario_in_header=True)
            url = f"{self.base_url}{self.route_bank_slips}/{bank_number}/data-vencimento"

            patch_payload = {"dataVencimento": payload.get("dataVencimento")}

            response = requests.patch(
                url,
                data=json.dumps(patch_payload),
                headers=headers,
            )

            if response.status_code >= 400:
                raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

            return safe_json_loads(response.text)

        return {}

    def get_bank_slip_pdf(self, digitable_line: str, payload: Optional[Dict[str, Any]] = None) -> bytes:
        import re
        cooperativa = payload.get("cooperativa", "") if payload else ""
        codigo_beneficiario = payload.get("codigoBeneficiario", "") if payload else ""

        token = self._get_token(cooperativa, codigo_beneficiario)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
        }

        cleaned_line = re.sub(r'\D', '', digitable_line or "")
        url = f"{self.base_url}/boletos/pdf"

        response = requests.get(
            url,
            params={"linhaDigitavel": cleaned_line},
            headers=headers,
        )

        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

        return response.content
