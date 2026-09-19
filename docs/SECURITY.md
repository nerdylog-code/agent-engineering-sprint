# Security review

## Escopo

O review cobre o harness offline, o registry de tools e os artefatos de
observabilidade. Não afirma segurança de um MCP server externo ou de uma conta
cloud que não foi conectada.

## Threat model

| ID | Threat | STRIDE | Risco | Mitigação implementada |
|---|---|---|---|---|
| TM-001 | tool não registrada tenta executar shell | Elevation | alto | registry allowlisted; unknown tool é blocked |
| TM-002 | argumento dunder atravessa fronteira | Tampering | médio | chaves `__*` são recusadas |
| TM-003 | tool output injeta instrução de sistema | Tampering/Info disclosure | alto | marcadores de prompt injection bloqueiam output |
| TM-004 | calculator executa código arbitrário | Elevation | alto | AST com operadores numéricos permitidos; sem `eval()` |
| TM-005 | trace expõe secret literal | Info disclosure | alto | redaction de padrões sensíveis e datasets sem credenciais |
| TM-006 | retry duplica ação não idempotente | DoS/Elevation | médio | retries bounded; aprovação humana explícita |
| TM-007 | RAG responde sem contexto | Info disclosure | médio | fallback sem evidência e citações obrigatórias no answer path |
| TM-008 | secret hardcoded no source | Info disclosure | alto | `scripts/security_scan.py` no CI |

## Controles

- Não há network call no runtime default.
- Não há subprocesso de produção no Agent Lab.
- Docker workflow é build/smoke, sem push de imagem.
- Evals são determinísticos e não enviam dados para terceiros.
- O security gate deve terminar com `status=pass` e `findings=[]`.

## O que ainda exige review humano

- autenticação/autorização de um MCP server real;
- permissões de filesystem/network em produção;
- secret manager da cloud;
- prompt injection adversarial além dos marcadores cobertos;
- supply-chain review de dependências opcionais.
