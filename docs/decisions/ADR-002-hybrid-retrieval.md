# ADR-002 — Hybrid retrieval antes de reranking

- **Status:** Accepted
- **Contexto:** Queries de engenharia contêm tanto significado semântico quanto
  identificadores exatos, códigos e nomes de ferramentas.
- **Decisão:** Medir vector-only, hybrid com RRF e hybrid + reranker no mesmo
  golden dataset; usar citations do documento recuperado.
- **Consequência positiva:** O experimento mostra o ganho real de combinar
  sinais e preserva explicabilidade lexical.
- **Consequência negativa:** O embedding por hashing é apenas baseline; um
  cross-encoder real poderá mudar o ranking e o custo.
- **Reversão:** Substituir apenas o adapter de embedding/reranking e preservar
  o evaluator e o dataset.
