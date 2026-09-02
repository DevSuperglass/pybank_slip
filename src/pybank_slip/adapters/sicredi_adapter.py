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
        self.route_webhook_contrato = "/webhook/contrato"
        self.route_webhook_contratos = "/webhook/contratos"

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

    def _get_token(self, cooperativa: str = "", codigo_beneficiario: str = "") -> str:
        """Fetches the OAuth2 Bearer token from Sicredi."""
        if self._token:
            return self._token

        headers = {
            "x-api-key": self.credentials.client_id,
            "context": "COBRANCA",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        import urllib.parse
        
        coop = cooperativa or getattr(self.credentials, 'cooperativa', '') or ""
        bnf = codigo_beneficiario or getattr(self.credentials, 'codigo_beneficiario', '') or ""
        username = f"{bnf}{coop}"
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

        payload = self.sanitize_payload(payload)

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
        payload = self.sanitize_payload(payload)
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

    # Webhook Contrato Methods (Páginas 223 - 266)

    def create_webhook_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo contrato de webhook no Sicredi (POST /webhook/contrato/)."""
        coop = payload.get("cooperativa") or getattr(self.credentials, 'cooperativa', '') or ""
        bnf = payload.get("codBeneficiario") or getattr(self.credentials, 'codigo_beneficiario', '') or ""
        token = self._get_token(coop, bnf)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{self.route_webhook_contrato}/"
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in (200, 201):
            return safe_json_loads(response.text)
        raise Exception(f"Erro ao criar contrato Webhook Sicredi: {response.status_code} - {response.text}")

    def get_webhook_contracts(self, cooperativa: str = "", posto: str = "", beneficiario: str = "") -> Dict[str, Any]:
        """Consulta contratos de webhook vinculados à cooperativa/posto/beneficiário (GET /webhook/contratos/)."""
        coop = cooperativa or getattr(self.credentials, 'cooperativa', '') or ""
        pst = posto or getattr(self.credentials, 'posto', '') or ""
        bnf = beneficiario or getattr(self.credentials, 'codigo_beneficiario', '') or ""
        token = self._get_token(coop, bnf)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{self.route_webhook_contratos}/?cooperativa={coop}&posto={pst}&beneficiario={bnf}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return safe_json_loads(response.text)
        elif response.status_code in (404, 422):
            return {}
        raise Exception(f"Erro ao consultar contratos Webhook Sicredi: {response.status_code} - {response.text}")

    def get_webhook_contract_by_id(self, contract_id: str) -> Dict[str, Any]:
        """Consulta dados de um contrato de webhook por ID (GET /webhook/contrato/{id})."""
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{self.route_webhook_contrato}/{contract_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return safe_json_loads(response.text)
        raise Exception(f"Erro ao consultar contrato Webhook Sicredi por ID: {response.status_code} - {response.text}")

    def edit_webhook_contract(self, contract_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Altera dados de um contrato de webhook existente (PUT /webhook/contrato/{id})."""
        coop = payload.get("cooperativa") or getattr(self.credentials, 'cooperativa', '') or ""
        bnf = payload.get("codBeneficiario") or getattr(self.credentials, 'codigo_beneficiario', '') or ""
        token = self._get_token(coop, bnf)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.credentials.client_id,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{self.route_webhook_contrato}/{contract_id}"
        response = requests.put(url, json=payload, headers=headers)
        if response.status_code in (200, 201):
            return safe_json_loads(response.text)
        raise Exception(f"Erro ao alterar contrato Webhook Sicredi: {response.status_code} - {response.text}")

    def cancel_webhook_contract(self, contract_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Inativa/cancela contrato de webhook alterando contratoStatus e urlStatus para INATIVO."""
        payload_cancel = dict(payload or {})
        payload_cancel["contratoStatus"] = "INATIVO"
        payload_cancel["urlStatus"] = "INATIVO"
        return self.edit_webhook_contract(contract_id, payload_cancel)

    # Workspace Interface Implementations (Strategy Pattern)

    def search_workspaces(self, **kwargs) -> dict:
        """Busca contratos de webhook no Sicredi e formata para o padrão de workspaces."""
        cooperativa = kwargs.get("cooperativa") or getattr(self.credentials, 'cooperativa', '') or ""
        posto = kwargs.get("posto") or getattr(self.credentials, 'posto', '') or ""
        beneficiario = kwargs.get("beneficiario") or kwargs.get("codBeneficiario") or getattr(self.credentials, 'codigo_beneficiario', '') or ""
        data = self.get_webhook_contracts(cooperativa=cooperativa, posto=posto, beneficiario=beneficiario)
        if not data:
            return {"content": []}
        contracts = data if isinstance(data, list) else [data]
        content = []
        for c in contracts:
            if not isinstance(c, dict) or not c.get("idContrato"):
                continue
            content.append({
                "id": c.get("idContrato"),
                "description": c.get("nomeResponsavel") or f"Contrato Sicredi {c.get('idContrato')}",
                "covenants": [{"code": c.get("codBeneficiario") or ""}],
                "webhookUrl": c.get("url", ""),
                "cooperativa": c.get("cooperativa", ""),
                "posto": c.get("posto", ""),
                "contratoStatus": c.get("contratoStatus", "ATIVO"),
                "urlStatus": c.get("urlStatus", "ATIVO"),
                "nomeResponsavel": c.get("nomeResponsavel", ""),
                "email": c.get("email", ""),
                "telefone": c.get("telefone", ""),
                "bankSlipBillingWebhookActive": True,
                "pixBillingWebhookActive": True,
                "raw": c,
            })
        return {"content": content}

    def create_workspace(self, payload: dict) -> dict:
        """Cria um workspace/contrato no Sicredi via create_webhook_contract."""
        cooperativa = payload.get("cooperativa") or getattr(self.credentials, 'cooperativa', '') or ""
        posto = payload.get("posto") or getattr(self.credentials, 'posto', '') or ""
        covenant_code = payload.get("codBeneficiario") or payload.get("covenant_code", "")
        if not covenant_code and payload.get("covenants"):
            covenant_code = payload["covenants"][0].get("code", "")
        if not covenant_code:
            covenant_code = getattr(self.credentials, 'codigo_beneficiario', '') or ""

        contract_payload = {
            "cooperativa": str(cooperativa).zfill(4) if cooperativa else "",
            "posto": str(posto).zfill(2) if posto else "",
            "codBeneficiario": str(covenant_code).zfill(5) if covenant_code else "",
            "eventos": payload.get("eventos") or ["LIQUIDACAO"],
            "url": payload.get("url") or payload.get("webhookURL") or payload.get("webhook_url", ""),
            "urlStatus": payload.get("urlStatus") or payload.get("url_status", "ATIVO"),
            "contratoStatus": payload.get("contratoStatus") or payload.get("contract_status", "ATIVO"),
            "nomeResponsavel": payload.get("nomeResponsavel") or payload.get("responsible_name") or payload.get("description", ""),
            "email": payload.get("email") or payload.get("responsible_email", ""),
            "telefone": payload.get("telefone") or payload.get("responsible_phone", ""),
            "enviarIdTituloEmpresa": payload.get("enviarIdTituloEmpresa") or payload.get("send_company_title_id", False),
        }
        res = self.create_webhook_contract(contract_payload)
        return {
            "id": res.get("idContrato"),
            "description": res.get("nomeResponsavel") or payload.get("description", ""),
            "raw": res,
        }

    def edit_workspace(self, workspace_id: str, payload: dict) -> dict:
        """Atualiza um workspace/contrato no Sicredi."""
        cooperativa = payload.get("cooperativa") or getattr(self.credentials, 'cooperativa', '') or ""
        posto = payload.get("posto") or getattr(self.credentials, 'posto', '') or ""
        covenant_code = payload.get("codBeneficiario") or payload.get("covenant_code", "")
        if not covenant_code and payload.get("covenants"):
            covenant_code = payload["covenants"][0].get("code", "")
        if not covenant_code:
            covenant_code = getattr(self.credentials, 'codigo_beneficiario', '') or ""

        contract_payload = {
            "cooperativa": str(cooperativa).zfill(4) if cooperativa else "",
            "posto": str(posto).zfill(2) if posto else "",
            "codBeneficiario": str(covenant_code).zfill(5) if covenant_code else "",
            "eventos": payload.get("eventos") or ["LIQUIDACAO"],
            "url": payload.get("url") or payload.get("webhookURL") or payload.get("webhook_url", ""),
            "urlStatus": payload.get("urlStatus") or payload.get("url_status", "ATIVO"),
            "contratoStatus": payload.get("contratoStatus") or payload.get("contract_status", "ATIVO"),
            "nomeResponsavel": payload.get("nomeResponsavel") or payload.get("responsible_name") or payload.get("description", ""),
            "email": payload.get("email") or payload.get("responsible_email", ""),
            "telefone": payload.get("telefone") or payload.get("responsible_phone", ""),
            "enviarIdTituloEmpresa": payload.get("enviarIdTituloEmpresa") or payload.get("send_company_title_id", False),
        }
        return self.edit_webhook_contract(workspace_id, contract_payload)

    def delete_workspace(self, workspace_id: str) -> None:
        """Inativa o workspace/contrato no Sicredi."""
        self.cancel_webhook_contract(workspace_id)
