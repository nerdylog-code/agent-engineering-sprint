# Guia de entrevista

Use estas respostas como roteiro de explicação do código real; não decore
números de terceiros. Cada afirmação técnica aponta para um módulo ou teste.

## Python / backend

**Por que FastAPI?**

Para uma API de laboratório, FastAPI oferece contratos tipados e validação
assíncrona. Neste baseline o núcleo é stdlib-only para o CI offline; FastAPI e
Pydantic estão isolados como extras e devem entrar apenas quando houver endpoint
real para validar.

**Async vs sync?**

Async ajuda em I/O concorrente; não torna CPU-bound gratuito. Retrieval local
pode ser sync enquanto chamadas de rede/LLM devem ser async ou isoladas. A
escolha precisa ser medida por latência e throughput.

**O que acontece se uma API externa cair?**

Timeout explícito, erro observável, retry apenas em operação idempotente e
fallback que não inventa resposta. O orchestrator local representa esse
contrato por retries limitados e status explícito.

**O que é idempotência?**

Repetir uma operação produz o mesmo efeito. Ações não idempotentes precisam de
idempotency key, deduplicação ou aprovação humana antes de retry.

## Agents

**Workflow vs agent?**

Workflow tem passos e transições conhecidas. Agent escolhe ações em runtime.
Use workflow quando o caminho for previsível; agent somente quando a decisão
adaptativa compensar a superfície de risco.

**Como o router escolhe?**

Por sinais explícitos e determinísticos em `route_request`; a decisão registra
rota, tool e razão no trace. Isso permite avaliar seleção sem depender de um
LLM-as-a-judge.

**Como impedir loop infinito?**

Limite de retries, limite de passos, timeout e estado terminal observável.
`AgentOrchestrator.run()` não aceita retries acima de 5.

**Como structured output inválido é tratado?**

Schema valida tipos e intervalos; cada falha gera evento `structured_output`
com `status=retry` ou `error`. Após o limite, o run vira `failed`.

## MCP e tools

**Host, client e server?**

O host coordena a aplicação, o client transporta a sessão e o server expõe
resources/tools. A fronteira deste projeto é representada por `ToolRegistry`;
ela mantém allowlist, least privilege e bloqueio de output suspeito.

**Como proteger secrets e tool output?**

Não colocar secrets em dataset ou trace; redigir valores sensíveis; tratar
output da tool como dado não confiável; validar schema e bloquear instruções que
tentem substituir a política do sistema.

## RAG

**Por que chunking?**

Para recuperar unidades relevantes sem exceder contexto. Tamanho e overlap
mudam recall, custo e redundância; por isso ficam mensuráveis no evaluator.

**Vector-only vs hybrid?**

Vector search captura semântica; keyword preserva termos exatos. Hybrid usa
RRF para combinar sinais e o reranker reordena com evidência lexical mais forte.

**Recall@K e MRR?**

Recall@K pergunta se o documento esperado aparece nos K primeiros. MRR mede o
inverso da posição do primeiro acerto. Groundedness verifica se os termos
esperados aparecem no contexto recuperado.

## Production

**Logging, tracing, metrics e evals?**

Logging são eventos; tracing conecta spans de um run; metrics agregam latência,
erros e custo; evals testam comportamento contra casos gold. São camadas
complementares, não sinônimos.

**P50 vs P95?**

P50 mostra a mediana; P95 mostra a cauda lenta. O evidence generator calcula
ambos a partir das latências reais dos runs.

**Como o CI impede regressão?**

Compile, unit tests, evals, security scan, RAG smoke e Docker build estão
separados em gates. Um pipeline verde significa que esses checks executaram;
não significa que uma credencial externa foi obtida.
