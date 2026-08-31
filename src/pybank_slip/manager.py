from typing import Optional
from .interfaces import BaseBankAdapter
from .adapters.bb_adapter import BancoDoBrasilAdapter
from .adapters.santander_adapter import SantanderAdapter
from .adapters.sicredi_adapter import SicrediAdapter
from .auth import CertificateAuth, OAuthCredentials

class BankSlipManager:
    """
    Factory manager to instantiate the correct bank adapter based on the bank identifier.
    """
    
    @staticmethod
    def get_adapter(
        bank_code: str, 
        credentials: OAuthCredentials, 
        environment: str,
        cert_auth: Optional[CertificateAuth] = None
    ) -> BaseBankAdapter:
        """
        Instantiate the appropriate Bank Adapter.
        
        :param bank_code: String identifier for the bank (e.g., 'bb', 'santander').
        :param credentials: OAuthCredentials object containing client_id and secret.
        :param environment: Environment parameter ('production' or 'sandbox').
        :param cert_auth: Optional CertificateAuth for mTLS (required by Santander).
        :return: BaseBankAdapter instance.
        """
        bank_code = bank_code.lower().strip()
        
        if bank_code == "bb":
            return BancoDoBrasilAdapter(credentials=credentials, environment=environment)
        
        elif bank_code == "santander":
            return SantanderAdapter(credentials=credentials, environment=environment, cert_auth=cert_auth)
            
        elif bank_code == "sicredi":
            return SicrediAdapter(credentials=credentials, environment=environment, cert_auth=cert_auth)
            
        else:
            raise NotImplementedError(f"Bank code '{bank_code}' is not supported.")
