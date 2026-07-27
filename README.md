# PyBank Slip

PyBank Slip is an independent, modern, and robust Python library designed to unify and simplify communication with bank slip (Boleto and Pix) APIs in Brazil. It manages all the complexity of authentication (OAuth2 and mTLS) and abstracts the bank routes, allowing your application (like ERPs or E-commerces) to focus solely on building the bank slip payload.

---

## 🏦 Supported Banks

The library currently supports the APIs of the following financial institutions:
- **Banco do Brasil** (API de Cobranças V2)
- **Santander** (API de Cobrança / Workspace V2)
- **Sicredi** (API de Cobrança V1 / OAuth2 / PDF)

---

## ⚙️ How it Works?

The library adopts the **Factory/Adapter** design pattern. The core focuses on the `BankSlipManager`, which receives the global credentials and the target bank, and returns an instance (Adapter) ready for use. The Adapter handles:
1. Automatically fetching the **Access Token (Bearer)** using the credentials (`grant_type=client_credentials` or `grant_type=password`).
2. Attaching the **ICP-Brasil Certificate (mTLS)** when required by the bank APIs.
3. Defensive validation against missing mandatory payload fields and empty/zero-padded strings.
4. Managing the selected environment (Production vs Sandbox).

---

## 📌 Required Parameters

The library requires configurations in three main areas:

### 1. `OAuthCredentials`
A structure that stores the App data created in the bank's developer portal:
- `client_id`: The Client ID / App Key (x-api-key for Sicredi).
- `client_secret`: The Client Secret (password for Sicredi OAuth).
- `app_key` (Optional): Primarily used by Banco do Brasil (gw-dev-app-key).

### 2. `CertificateAuth` (mTLS)
Digital certificate configuration for two-way SSL/TLS encryption (required by Santander and BB).
- `cert_path`: Absolute path to the `.pem` file of the client certificate (Public Key).
- `key_path`: Absolute path to the `.pem` file of the private key.

### 3. Manager/Adapter 
Parameters passed when instantiating the adapter:
- `bank`: Bank string identifier (`'bb'`, `'santander'`, or `'sicredi'`).
- `credentials`: Instance of `OAuthCredentials`.
- `environment`: Environment string (`'production'` or `'sandbox'`).
- `cert_auth`: Instance of `CertificateAuth` (optional for Sicredi).
- `workspace_id` (Only Santander): The financial workspace ID.

---

## 🚀 Abstracted Routes and Features

Each Adapter abstracts raw HTTP calls into standardized, built-in methods:

### `generate_bank_slip(payload: dict)`
Sends the bank slip registration request.
- **Banco do Brasil:** `POST /cobrancas/v2/boletos`
- **Santander:** `POST /collection_bill_management/v2/workspaces/{workspace_id}/bank_slips`
- **Sicredi:** `POST /sb/cobranca/boleto/v1/boletos`

### `list_bank_slips(filters: dict)`
Queries issued bank slips using filters (Document, Date, etc).
- **Banco do Brasil:** `GET /cobrancas/v2/boletos`
- **Santander:** `GET /collection_bill_management/v2/workspaces/{workspace_id}/bank_slips`

### `cancel_bank_slip(bank_slip_id: str, payload: dict)`
Requests the cancellation/write-off of the bank slip.
- **Banco do Brasil:** `POST /cobrancas/v2/boletos/{id}/baixar`
- **Santander:** `PATCH /collection_bill_management/v2/workspaces/{workspace_id}/bank_slips/{id}`
- **Sicredi:** `PATCH /sb/cobranca/boleto/v1/boletos/{id}/baixa`

### `edit_bank_slip(bank_slip_id: str, payload: dict)`
Allows editing conditions (Due Date, Value, Discounts) of the bank slip.
- **Banco do Brasil:** `PATCH /cobrancas/v2/boletos/{id}`
- **Santander:** `PATCH /collection_bill_management/v2/workspaces/{workspace_id}/bank_slips/{id}`
- **Sicredi:** `PATCH /sb/cobranca/boleto/v1/boletos/{id}/data-vencimento`

### `get_bank_slip_pdf(digitable_line: str, payload: dict)`
Downloads the official PDF binary stream directly from the bank API.
- **Sicredi:** `GET /sb/cobranca/boleto/v1/boletos/pdf?linhaDigitavel={linha}`

---

## 💻 Practical Usage Example

```python
from pybank_slip import BankSlipManager, OAuthCredentials, CertificateAuth

# 1. Setup Credentials for Sicredi
credentials = OAuthCredentials(
    client_id="your_x_api_key",
    client_secret="your_password"
)

# 2. Generate Adapter (Factory)
adapter = BankSlipManager.get_adapter(
    bank="sicredi",
    credentials=credentials,
    environment="sandbox"
)

# 3. Call the desired feature
payload_sicredi = {
    "cooperativa": "0100",
    "posto": "03",
    "codigoBeneficiario": "12345",
    "tipoCobranca": "NORMAL",
    "nossoNumero": "242000015",
    "seuNumero": "10001",
    "dataVencimento": "2026-08-30",
    "valor": 150.00,
    "especieDocumento": "DUPLICATA_MERCANTIL_INDICACAO",
    "pagador": {
        "nome": "Cliente Exemplo",
        "tipoPessoa": "PESSOA_FISICA",
        "documento": "12345678901",
        "endereco": "Rua Exemplo, 100",
        "cidade": "São Paulo",
        "uf": "SP",
        "cep": "01000000"
    }
}

response = adapter.generate_bank_slip(payload_sicredi)
print(response)
```
