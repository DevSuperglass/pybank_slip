from dataclasses import dataclass
from typing import Optional

@dataclass
class CertificateAuth:
    """Holds configuration for mTLS certificate authentication (mostly Banco do Brasil)."""
    cert_path: str
    key_path: str
    verify: bool = True

@dataclass
class OAuthCredentials:
    """Holds configuration for OAuth2 token fetching."""
    client_id: str
    client_secret: str
    app_key: Optional[str] = None
    workspace_id: Optional[str] = None
    cooperativa: Optional[str] = None
    posto: Optional[str] = None
    codigo_beneficiario: Optional[str] = None
