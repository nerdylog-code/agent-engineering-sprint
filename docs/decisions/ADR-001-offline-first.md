# ADR-001 — Offline-first deterministic baseline

- **Status:** Accepted
- **Contexto:** O sprint exige prova técnica, mas o ambiente pode não possuir
  credenciais, Docker, modelo remoto ou rede estável.
- **Decisão:** O núcleo roda com Python stdlib, corpus sintético e embeddings
  por hashing. FastAPI, Pydantic, pytest e ruff são extras opcionais.
- **Consequência positiva:** CI barato, reprodutível e auditável; números não
  dependem de disponibilidade de provider.
- **Consequência negativa:** Não mede qualidade de um LLM real nem captura toda
  a semântica de embeddings de produção.
- **Reversão:** Criar adapters atrás das interfaces existentes e manter o
  baseline como controle experimental.
