# PyBank Slip

[![PyPI Version](https://img.shields.io/pypi/v/pybank-slip.svg?style=flat-square&color=blue)](https://pypi.org/project/pybank-slip/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pybank-slip.svg?style=flat-square&color=3776AB)](https://pypi.org/project/pybank-slip/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)
[![Downloads](https://img.shields.io/pypi/dm/pybank-slip.svg?style=flat-square&color=orange)](https://pypi.org/project/pybank-slip/)

> **A modern, framework-agnostic Python client for issuing, managing, and automating Brazilian Bank Slips (*Boletos de Cobrança*) across multiple banking institutions.**
>
> Built with zero ERP dependencies, automated OAuth2 token lifecycles, native mTLS (mutual TLS) certificate orchestration, and defensive payload verification.

---

## Table of Contents

- [Key Features](#-key-features)
- [Supported Banks & Feature Matrix](#-supported-banks--feature-matrix)
- [Architecture & Design Pattern](#-architecture--design-pattern)
- [Installation](#-installation)
- [Authentication & Credentials](#-authentication--credentials)
  - [OAuth2 Credentials (`OAuthCredentials`)](#1-oauthcredentials)
  - [Mutual TLS Certificates (`CertificateAuth`)](#2-certificateauth-mtls)
- [Quickstart & Bank Examples](#-quickstart--bank-examples)
  - [1. Banco do Brasil (API de Cobranças V2)](#1-banco-do-brasil-api-de-cobranças-v2)
  - [2. Banco Santander (Workspace & Cobrança V2)](#2-banco-santander-workspace--cobrança-v2)
  - [3. Banco Sicredi (API de Cobrança V1 & PDF)](#3-banco-sicredi-api-de-cobrança-v1--pdf)
- [Error Handling & Exceptions](#-error-handling--exceptions)
- [Development & Testing](#-development--testing)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License & Author](#-license--author)

---

## ✨ Key Features

- **Unified Multi-Bank Interface:** One standardized API contract (`BaseBankAdapter`) to generate, query, edit, cancel boletos, and retrieve official PDF streams.
- **Factory/Adapter Architecture:** Clean separation of concerns through `BankSlipManager`, instantiating concrete bank drivers dynamically at runtime.
- **Automated Security & Auth:**
  - Automatic OAuth2 token negotiation and bearer caching (`client_credentials` and `password` grant flows).
  - Native **mTLS / ICP-Brasil Digital Certificate** enforcement (`.pem` cert and key handling via `requests`).
- **Defensive Payload Validation:** Pre-flight client-side inspection that validates mandatory banking parameters and rejects empty or zero-padded strings before hitting upstream bank endpoints.
- **Robust JSON Normalization:** Self-healing parser (`safe_json_loads`) designed to sanitize malformed or truncated JSON responses commonly returned by legacy banking gateways.
- **Production & Sandbox Ready:** Seamlessly toggle between mock/homologation and production environments with zero code rewrites.
- **Zero Heavy Dependencies:** Lightweight footprint relying strictly on `requests>=2.28.0`.

---

## 🏦 Supported Banks & Feature Matrix

| Financial Institution | Bank Code (`bank_code`) | Auth Protocol | Issue Boleto (`generate_bank_slip`) | List Boletos (`list_bank_slips`) | Cancel / Write-off (`cancel_bank_slip`) | Edit Boleto (`edit_bank_slip`) | Download PDF (`get_bank_slip_pdf`) | Workspace Management |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Banco do Brasil** | `'bb'` | OAuth2 + mTLS + AppKey | ✅ | ✅ | ✅ | ✅ | — | — |
| **Santander** | `'santander'` | OAuth2 + mTLS + Workspace | ✅ | — | *(via edit)* | ✅ | — | ✅ |
| **Sicredi** | `'sicredi'` | OAuth2 (Password Flow) | ✅ | — | ✅ | ✅ *(Due date)* | ✅ *(Raw binary)* | — |

---

## 🏗 Architecture & Design Pattern

`pybank-slip` adopts the **Factory / Adapter Pattern**. The client application interacts with a central factory (`BankSlipManager`), which returns an implementation of the abstract `BaseBankAdapter`.

```text
               +-----------------------------------+
               |          Your Application         |
               +-----------------------------------+
                                 |
                                 v
               +-----------------------------------+
               |          BankSlipManager          |
               |       .get_adapter(bank_code)     |
               +-----------------------------------+
                                 |
        +------------------------+------------------------+
        |                                                 |
        v                                                 v
+-------------------------------+                 +-------------------------------+
|     BancoDoBrasilAdapter      |                 |        SicrediAdapter         |
|  - OAuth2 + mTLS              |                 |  - OAuth2 Password Flow       |
|  - Cobranças V2 Endpoints     |                 |  - Direct PDF binary stream   |
+-------------------------------+                 +-------------------------------+
        |                                                 |
        +------------------------+------------------------+
                                 |
                                 v
               +-----------------------------------+
               |        BaseBankAdapter (ABC)      |
               |  - generate_bank_slip()           |
               |  - list_bank_slips()              |
               |  - cancel_bank_slip()             |
               |  - edit_bank_slip()               |
               +-----------------------------------+
```

---

## 📦 Installation

Install the stable package directly from [PyPI](https://pypi.org/project/pybank-slip/):

```bash
pip install pybank-slip
```

To install with development dependencies:

```bash
pip install "pybank-slip[dev]"
```

---

## 🔐 Authentication & Credentials

### 1. `OAuthCredentials`
Stores API authentication keys and context parameters provided by the bank's developer portal:

```python
from pybank_slip import OAuthCredentials

credentials = OAuthCredentials(
    client_id="your-client-id-or-api-key",
    client_secret="your-client-secret-or-password",
    app_key="your-dev-app-key",         # Required for Banco do Brasil (gw-dev-app-key)
    workspace_id="your-workspace-id"    # Required for Santander (Workspace UUID)
)
```

### 2. `CertificateAuth` (mTLS)
Holds ICP-Brasil digital certificate details for two-way TLS encryption:

```python
from pybank_slip import CertificateAuth

cert_auth = CertificateAuth(
    cert_path="/path/to/public_certificate.pem",
    key_path="/path/to/private_key.pem",
    verify=True # Enable/disable SSL CA verification
)
```

---

## 🚀 Quickstart & Bank Examples

### 1. Banco do Brasil (API de Cobranças V2)

Banco do Brasil requires OAuth2 credentials, a developer application key (`app_key`), and an mTLS certificate.

```python
from pybank_slip import BankSlipManager, OAuthCredentials, CertificateAuth

# 1. Configure Authentication & Certificate
credentials = OAuthCredentials(
    client_id="eyJpZCI6Ij...",
    client_secret="eyJpZCI6Ij...",
    app_key="d9f4852084c6..." # gw-dev-app-key
)

cert_auth = CertificateAuth(
    cert_path="/certs/bb_certificate.pem",
    key_path="/certs/bb_private_key.pem"
)

# 2. Instantiate BB Adapter
adapter = BankSlipManager.get_adapter(
    bank_code="bb",
    credentials=credentials,
    environment="sandbox", # or "production"
    cert_auth=cert_auth
)

# 3. Issue a new Bank Slip (Boleto)
payload = {
    "numeroConvenio": 3128557,
    "numeroCarteira": 17,
    "numeroVariacaoCarteira": 35,
    "codigoModalidade": 1,
    "dataEmissao": "27.08.2026",
    "dataVencimento": "30.08.2026",
    "valorOriginal": 125.50,
    "codigoAceite": "N",
    "codigoTipoTitulo": 2,
    "indicadorPermissaoRecebimentoParcial": "N",
    "numeroTituloBeneficiario": "DOC12345",
    "pagador": {
        "tipoInscricao": 1, # 1: CPF, 2: CNPJ
        "numeroInscricao": "12345678909",
        "nome": "João da Silva",
        "endereco": "Avenida Paulista, 1000",
        "cep": 1310000,
        "cidade": "São Paulo",
        "bairro": "Bela Vista",
        "uf": "SP",
        "telefone": "11988887777"
    }
}

response = adapter.generate_bank_slip(payload)
print("Boleto Issued:", response)

# 4. List Bank Slips
boletos = adapter.list_bank_slips(filters={
    "indicadorSituacao": "A",
    "agenciaBeneficiario": 452,
    "contaCorrenteBeneficiario": 123873
})

# 5. Cancel / Baixar Boleto
cancel_result = adapter.cancel_bank_slip(
    bank_slip_id="00031285570000000001",
    payload={"numeroConvenio": 3128557}
)
```

---

### 2. Banco Santander (Workspace & Cobrança V2)

Santander requires OAuth2 credentials, a Workspace ID, and mTLS certificates.

```python
from pybank_slip import BankSlipManager, OAuthCredentials, CertificateAuth

# 1. Configure Credentials & Workspace
credentials = OAuthCredentials(
    client_id="your-santander-client-id",
    client_secret="your-santander-client-secret",
    workspace_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
)

cert_auth = CertificateAuth(
    cert_path="/certs/santander_cert.pem",
    key_path="/certs/santander_key.pem"
)

# 2. Instantiate Santander Adapter
adapter = BankSlipManager.get_adapter(
    bank_code="santander",
    credentials=credentials,
    environment="production",
    cert_auth=cert_auth
)

# 3. Workspace Operations (Optional / Administrative)
workspaces = adapter.search_workspaces()
print("Available Workspaces:", workspaces)

# 4. Issue a new Bank Slip
payload = {
    "covenantCode": "12345678",
    "bankNumber": "000000000001",
    "clientNumber": "ORDER-9921",
    "dueDate": "2026-09-10",
    "issueDate": "2026-08-27",
    "nominalValue": 250.00,
    "payer": {
        "name": "Maria Oliveira",
        "documentType": "CPF",
        "documentNumber": "98765432100",
        "address": "Rua das Flores, 250",
        "neighborhood": "Centro",
        "city": "Curitiba",
        "state": "PR",
        "zipCode": "80000000"
    }
}

response = adapter.generate_bank_slip(payload)
print("Santander Boleto Response:", response)
```

---

### 3. Banco Sicredi (API de Cobrança V1 & PDF)

Sicredi uses `x-api-key` and an Internet Banking password (`grant_type=password`). Digital certificates are not required for standard API operations.

```python
from pybank_slip import BankSlipManager, OAuthCredentials

# 1. Configure Credentials
credentials = OAuthCredentials(
    client_id="your-x-api-key",
    client_secret="your-internet-banking-password"
)

# 2. Instantiate Sicredi Adapter
adapter = BankSlipManager.get_adapter(
    bank_code="sicredi",
    credentials=credentials,
    environment="sandbox"
)

# 3. Issue a new Bank Slip
payload_sicredi = {
    "cooperativa": "0100",
    "posto": "03",
    "codigoBeneficiario": "12345",
    "tipoCobranca": "NORMAL",
    "nossoNumero": "242000015",
    "seuNumero": "INV-2026-001",
    "dataVencimento": "2026-09-05",
    "valor": 89.90,
    "especieDocumento": "DUPLICATA_MERCANTIL_INDICACAO",
    "pagador": {
        "nome": "Tech Solutions Ltda",
        "tipoPessoa": "PESSOA_JURIDICA",
        "documento": "12345678000195",
        "endereco": "Av. Brasil, 500",
        "cidade": "Porto Alegre",
        "uf": "RS",
        "cep": "90000000"
    }
}

response = adapter.generate_bank_slip(payload_sicredi)
print("Sicredi Boleto Response:", response)

# 4. Download Official PDF Stream
pdf_bytes = adapter.get_bank_slip_pdf(
    digitable_line="74891123450000123456789012345678901234567890",
    payload={"cooperativa": "0100", "codigoBeneficiario": "12345"}
)

with open("boleto_sicredi.pdf", "wb") as f:
    f.write(pdf_bytes)

print("PDF successfully saved as boleto_sicredi.pdf!")
```

---

## 🛡 Error Handling & Exceptions

`pybank-slip` performs defensive pre-flight assertions and encapsulates upstream HTTP error details:

- **`ValueError`**: Raised client-side when mandatory credentials or required payload fields are missing, empty, or zero-padded.
- **`NotImplementedError`**: Raised when attempting to invoke an unsupported bank code or an operation not yet implemented by a specific bank adapter.
- **`Exception`**: Raised when upstream bank servers return an HTTP error status code (`>= 400`) or send corrupted/unparseable JSON responses.

### Robust Exception Handling Example

```python
from pybank_slip import BankSlipManager, OAuthCredentials
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

credentials = OAuthCredentials(
    client_id="invalid_client_id",
    client_secret="invalid_secret"
)

try:
    adapter = BankSlipManager.get_adapter(
        bank_code="sicredi",
        credentials=credentials,
        environment="sandbox"
    )
    response = adapter.generate_bank_slip(payload={})

except ValueError as val_err:
    logger.error("Client-side validation error: %s", val_err)

except NotImplementedError as nie_err:
    logger.error("Operation not supported by this bank: %s", nie_err)

except Exception as http_err:
    # Captures HTTP 4xx/5xx status codes with bank endpoint response text
    logger.error("Upstream Bank API Communication Failure: %s", http_err)
```

---

## 🛠 Development & Testing

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/erickovisck/pybank_slip.git
cd pybank_slip

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 2. Install Development Dependencies

```bash
pip install --upgrade pip
pip install -e .
pip install pytest flake8 black
```

### 3. Running Tests & Linters

```bash
# Run test suite
pytest

# Check code formatting with Black
black --check src/

# Run static analysis with Flake8
flake8 src/
```

---

## 🗺 Roadmap

- [ ] **PIX QR Code Integration:** Native support for dynamic Pix QR Code generation embedded in bank slips (*Boleto Híbrido*).
- [ ] **Additional Bank Adapters:**
  - [ ] Itaú Unibanco (API Cobrança v2)
  - [ ] Bradesco (API Cobrança Bradesco)
  - [ ] Banco Inter (API Cobrança v3)
  - [ ] Caixa Econômica Federal
- [ ] **Webhook & Callback Dispatcher:** Built-in signature verification and event deserializers for payment notifications.
- [ ] **Async Support:** Asynchronous adapter implementations using `httpx`.

---

## 🤝 Contributing

Contributions are warmly welcomed! To contribute:

1. **Fork** the repository.
2. **Create a Feature Branch:** `git checkout -b feature/amazing-bank-feature`.
3. **Commit your Changes:** `git commit -m 'feat: add support for Bank X'`.
4. **Push to the Branch:** `git push origin feature/amazing-bank-feature`.
5. **Open a Pull Request** with a detailed explanation of your changes and test coverage.

Please ensure all tests pass and your code adheres to [PEP 8](https://peps.python.org/pep-0008/) standards.

---

## 📄 License & Author

Distributed under the **MIT License**. See `LICENSE` for more information.

**Author:** [Erick Fernando Martins Santos](https://github.com/erickovisck)  
**Email:** `erickmartinslima3@gmail.com`  
**GitHub:** [@erickovisck](https://github.com/erickovisck)
