import requests
from ..utils import safe_json_loads
from typing import Dict, Any, Optional
from ..interfaces import BaseBankAdapter
from ..auth import OAuthCredentials, CertificateAuth

class SantanderAdapter(BaseBankAdapter):
    def _set_urls(self):
        if self.environment == 'sandbox':
            self.base_url = "https://trust-sandbox.api.santander.com.br"
            self.token_url = "https://trust-sandbox.api.santander.com.br/auth/oauth/v2/token"
        else:
            self.base_url = "https://trust-open.api.santander.com.br"
            self.token_url = "https://trust-open.api.santander.com.br/auth/oauth/v2/token"
            
        self.route_workspaces = "/collection_bill_management/v2/workspaces"
        self.route_bank_slips = "/collection_bill_management/v2/workspaces/{workspace_id}/bank_slips"

    def search_workspaces(self) -> dict:
        token = self._get_token()
        url = f"{self.base_url}{self.route_workspaces}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
        }
        cert = (self.cert_auth.cert_path, self.cert_auth.key_path) if self.cert_auth else None
        verify = self.cert_auth.verify if self.cert_auth else True
        
        response = requests.get(url, headers=headers, cert=cert, verify=verify)
        if response.status_code == 200:
            return safe_json_loads(response.text)
        raise Exception(f"Santander Workspace Error {response.status_code}: {response.text}")

    """
    Bank slip adapter for Santander API.
    """

    def __init__(self, credentials: OAuthCredentials, environment: str = 'production', cert_auth: Optional[CertificateAuth] = None):
        self.credentials = credentials
        self.environment = environment.lower()
        self.cert_auth = cert_auth
        self._set_urls()
        self._token = None

    def _get_token(self) -> str:
        """Fetches the OAuth2 Bearer token from Santander."""
        if self._token:
            return self._token
            
        payload = {"client_id": self.credentials.client_id, "grant_type": "client_credentials"}
        
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.post(
            self.token_url,
            data=payload,
            auth=(self.credentials.client_id, self.credentials.client_secret),
            **cert_args
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
            raise ValueError("Santander API credentials missing (client_id and client_secret are required).")
        if not self.credentials.workspace_id:
            raise ValueError("Workspace ID (workspace_id) is required in Santander credentials.")
        if not self.cert_auth or not self.cert_auth.cert_path or not self.cert_auth.key_path:
            raise ValueError("Digital Certificate and Private Key are required for mTLS authentication in Santander.")

        required_fields = ["covenantCode", "bankNumber", "dueDate", "nominalValue", "payer"]
        missing = [f for f in required_fields if not _is_valid(payload.get(f))]
        if missing:
            raise ValueError(f"Invalid Santander payload. Required fields missing or empty: {', '.join(missing)}")

        payer = payload.get("payer", {})
        if isinstance(payer, dict):
            req_payer = ["name", "documentNumber", "address", "city", "state", "zipCode"]
            missing_payer = [f for f in req_payer if not _is_valid(payer.get(f))]
            if missing_payer:
                raise ValueError(f"Invalid Santander payload. Required payer details missing or empty: {', '.join(missing_payer)}")

        token = self._get_token()
        workspace_id = self.credentials.workspace_id
        url = f"{self.base_url}{self.route_bank_slips}".format(workspace_id=workspace_id)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.post(url=url, json=payload, headers=headers, **cert_args)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def list_bank_slips(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError("List bank slips is not yet implemented for Santander.")

    def cancel_bank_slip(self, bank_slip_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Cancel bank slip must use edit_bank_slip (patch) with the cancel payload in Santander.")

    def edit_bank_slip(self, bank_slip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = self._get_token()
        workspace_id = self.credentials.workspace_id
        url = f"{self.base_url}{self.route_bank_slips}".format(workspace_id=workspace_id)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.patch(url=url, json=payload, headers=headers, **cert_args)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    # Santander Specific Methods
    def register_workspace(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = self._get_token()
        url = f"{self.base_url}/workspaces"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Content-Type": "application/json",
        }
        
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.post(url=url, json=payload, headers=headers, **cert_args)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def list_workspaces(self) -> Dict[str, Any]:
        token = self._get_token()
        url = f"{self.base_url}/workspaces"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
        }
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.get(url=url, headers=headers, **cert_args)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")
        return safe_json_loads(response.text)

    def delete_workspace(self, workspace_id: str) -> None:
        token = self._get_token()
        url = f"{self.base_url}/workspaces/{workspace_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
        }
        cert_args = {}
        if self.cert_auth:
            cert_args['cert'] = (self.cert_auth.cert_path, self.cert_auth.key_path)
            cert_args['verify'] = self.cert_auth.verify
            
        response = requests.delete(url=url, headers=headers, **cert_args)
        if response.status_code >= 400:
            raise Exception(f"HTTP Error {response.status_code} for url {response.url}: {response.text}")

    def create_workspace(self, payload: dict) -> dict:
        token = self._get_token()
        url = f"{self.base_url}{self.route_workspaces}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        cert = (self.cert_auth.cert_path, self.cert_auth.key_path) if self.cert_auth else None
        verify = self.cert_auth.verify if self.cert_auth else True
        import requests
        response = requests.post(url, headers=headers, json=payload, cert=cert, verify=verify)
        if response.status_code == 201:
            return safe_json_loads(response.text)
        raise Exception(f"Erro ao criar workspace: {response.status_code} - {response.text}")

    def edit_workspace(self, workspace_id: str, payload: dict) -> dict:
        token = self._get_token()
        url = f"{self.base_url}{self.route_workspaces}/{workspace_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        cert = (self.cert_auth.cert_path, self.cert_auth.key_path) if self.cert_auth else None
        verify = self.cert_auth.verify if self.cert_auth else True
        import requests
        response = requests.patch(url, headers=headers, json=payload, cert=cert, verify=verify)
        if response.status_code == 200:
            return {}
        raise Exception(f"Erro ao editar workspace: {response.status_code} - {response.text}")

    def delete_workspace(self, workspace_id: str) -> None:
        token = self._get_token()
        url = f"{self.base_url}{self.route_workspaces}/{workspace_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application-Key": self.credentials.client_id,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        cert = (self.cert_auth.cert_path, self.cert_auth.key_path) if self.cert_auth else None
        verify = self.cert_auth.verify if self.cert_auth else True
        import requests
        response = requests.delete(url, headers=headers, cert=cert, verify=verify)
        if response.status_code == 204:
            return None
        raise Exception(f"Erro ao deletar workspace: {response.status_code} - {response.text}")
