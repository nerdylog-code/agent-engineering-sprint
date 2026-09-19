# JWT / RBAC security evidence

This file records the locally executable security contract. It does not claim an
external identity provider or production key-management setup.

## Implemented contract

- HS256 JWTs require a 32-byte minimum secret.
- Required claims: `sub`, `tenant_id`, `roles`, `scopes`, `exp`, `iat`, `iss`, `aud`.
- `exp`, signature, issuer and audience are verified by PyJWT.
- `/v1/*` derives tenant/principal exclusively from the validated token.
- A body tenant/principal mismatch returns `403`.
- `roles` are explicit; `/v1/admin/mcp-audit` requires `admin`.
- MCP `tools/call` requires `tools:<tool_name>` and records allow/deny decisions.
- MCP tool execution has a bounded timeout and returns `504` on timeout.

## Reproduce

From the repository root:

```bash
PYTHONPATH=src python -m pytest tests/test_auth.py tests/test_api.py -q
PYTHONPATH=src python -m unittest discover -s tests -q
```

```text
Ran 43 tests
OK
```
The focused tests cover:

| Case | Expected result |
|---|---|
| Valid claims | principal decoded with tenant, roles and scopes |
| Expired token | `AuthenticationError` |
| Invalid signature | `AuthenticationError` |
| Wrong audience | `AuthenticationError` |
| Wrong issuer | `AuthenticationError` |
| Cross-tenant body claim | HTTP `403` |
| User role on admin route | HTTP `403` |
| Admin role on admin route | HTTP `200` |
| Missing MCP tool scope | HTTP `403` |
| Invalid MCP token | HTTP `401` |
| MCP tool timeout | HTTP `504` plus audit entry |

## Boundary / not claimed

HS256 is the local demonstration mode. A production deployment should use an
external issuer or RS256/EdDSA keys held in a managed secret/KMS system. This
repository does not claim a production identity provider, key rotation, hosted
RBAC policy store, or compliance certification.
