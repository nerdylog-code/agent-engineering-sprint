"""Adversarial retrieval corpus: semantic paraphrases, distractors and abstention."""

from __future__ import annotations

from .models import Document

_CORPUS: tuple[tuple[str, str, str, str], ...] = (
    (
        "hr-annual-leave",
        "Annual leave entitlement",
        "After the accrual period is completed, employees receive thirty consecutive calendar days of annual leave for rest and recovery.",
        "paraphrase",
    ),
    (
        "hr-business-days",
        "Business-day leave policy",
        "After the accrual period, employees receive twenty business days of leave; weekends and public holidays are excluded.",
        "distractor",
    ),
    (
        "security-mtls",
        "Mutual TLS authentication",
        "Mutual TLS, abbreviated mTLS, authenticates both endpoints by requiring certificates from the client and the server during the handshake.",
        "abbreviation",
    ),
    (
        "security-server-tls",
        "Server TLS authentication",
        "Server-side TLS encrypts traffic and authenticates the server, while the client connects without presenting a certificate.",
        "distractor",
    ),
    (
        "observability-p95",
        "Tail latency percentile",
        "P95 latency is the response-time threshold that at least ninety-five percent of requests meet or beat; it exposes slow-tail behavior.",
        "synonym",
    ),
    (
        "observability-average",
        "Average latency",
        "Mean latency is the arithmetic average of request durations and can hide a small group of extremely slow requests.",
        "distractor",
    ),
    (
        "sqlite-wal",
        "SQLite write-ahead logging",
        "SQLite write-ahead logging, or WAL mode, lets readers continue while a writer appends changes to a log; checkpointing later merges those changes.",
        "abbreviation",
    ),
    (
        "sqlite-journal",
        "SQLite rollback journal",
        "SQLite rollback-journal mode records original pages before replacing the database and commonly serializes readers with a writer.",
        "distractor",
    ),
    (
        "mcp-scope",
        "MCP per-tool authorization",
        "An MCP scope such as tools:calculator grants permission to invoke one named tool; broad roles do not replace per-tool authorization.",
        "scope",
    ),
    (
        "mcp-role",
        "MCP role authorization",
        "A role groups several permissions for a principal, but a role alone does not prove that a specific MCP tool scope was granted.",
        "distractor",
    ),
    (
        "rag-abstention",
        "Grounded retrieval abstention",
        "A grounded RAG assistant should abstain when retrieved context does not contain evidence for the requested claim instead of inventing an answer.",
        "abstention",
    ),
    (
        "rag-hallucination",
        "Ungrounded answer risk",
        "A hallucinated answer presents unsupported claims as facts even when the retrieval context is empty or irrelevant.",
        "distractor",
    ),
    (
        "retry-idempotent",
        "Safe retry policy",
        "Automatic retries are safest for idempotent operations; retrying a non-idempotent write can duplicate its side effect.",
        "reliability",
    ),
    (
        "retry-backoff",
        "Retry backoff",
        "Exponential backoff spaces repeated attempts so a failing dependency is not overwhelmed by synchronized clients.",
        "distractor",
    ),
    (
        "ci-gates",
        "Continuous integration gates",
        "A CI pipeline should run tests, type checks, security audits and packaging gates before a change is promoted.",
        "synonym",
    ),
    (
        "ci-deploy",
        "Continuous deployment",
        "A deployment workflow publishes an already validated artifact to a runtime environment and can trigger a rollback.",
        "distractor",
    ),
    (
        "otel-trace",
        "Distributed trace identity",
        "A distributed trace links request, router, retrieval and tool spans through one shared trace identifier.",
        "paraphrase",
    ),
    (
        "otel-metric",
        "Metrics versus traces",
        "A metric aggregates measurements over time, while a trace preserves the causal sequence of spans for one request.",
        "distractor",
    ),
    (
        "mcp-timeout",
        "Tool timeout boundary",
        "A tool timeout bounds how long the host waits for a tool; cancelling the caller does not forcibly kill an already running Python thread.",
        "timeout",
    ),
    (
        "mcp-retry",
        "Tool retry behavior",
        "A retry policy decides whether a failed tool call may be attempted again and should consider idempotency before repeating it.",
        "distractor",
    ),
    (
        "rbac-tenant",
        "RBAC and tenant isolation",
        "Role-based access control grants permissions through roles, while tenant isolation prevents a principal from reading another tenant's resources.",
        "security",
    ),
    (
        "acl-document",
        "Document ACL",
        "A document ACL lists the principals allowed to read one document and is narrower than a role shared across a tenant.",
        "distractor",
    ),
    (
        "rpo-recovery",
        "Recovery point objective",
        "RPO is the maximum acceptable amount of data loss expressed as elapsed time between the latest recoverable copy and an incident.",
        "synonym",
    ),
    (
        "rto-recovery",
        "Recovery time objective",
        "RTO is the target time to restore a service after disruption, not the amount of data that may be lost.",
        "distractor",
    ),
)


_QUESTIONS: tuple[tuple[str, str | None, str, str], ...] = (
    ("How many calendar days of rest are granted after the qualifying accrual period ends?", "hr-annual-leave", "paraphrase", "answerable"),
    ("What is the vacation length once a worker completes the earning period?", "hr-annual-leave", "synonym", "answerable"),
    ("Após concluir o período aquisitivo, por quanto tempo posso me afastar para descanso?", "hr-annual-leave", "multilingual", "answerable"),
    ("If the employee finishes the accrual period, how long is the annual vacation?", "hr-annual-leave", "paraphrase", "answerable"),
    ("What does mTLS prove during a secure handshake?", "security-mtls", "abbreviation", "answerable"),
    ("Why would both sides present certificates when opening the encrypted channel?", "security-mtls", "paraphrase", "answerable"),
    ("What is mutual transport layer security used to authenticate?", "security-mtls", "synonym", "answerable"),
    ("How does client-and-server certificate authentication differ from ordinary TLS?", "security-mtls", "distractor", "answerable"),
    ("Which percentile exposes the slow tail instead of the average response time?", "observability-p95", "synonym", "answerable"),
    ("What does P95 tell an operator about request latency?", "observability-p95", "abbreviation", "answerable"),
    ("The boundary met by ninety-five percent of requests is called what?", "observability-p95", "paraphrase", "answerable"),
    ("latncy p95 reveals which part of system performance?", "observability-p95", "typo", "answerable"),
    ("What does WAL allow readers to do while a SQLite writer is active?", "sqlite-wal", "abbreviation", "answerable"),
    ("Why can a reader continue while new database changes are appended to a log?", "sqlite-wal", "paraphrase", "answerable"),
    ("What is SQLite write ahead logging useful for under concurrent access?", "sqlite-wal", "synonym", "answerable"),
    ("In SQLite, which mode separates appends from a later checkpoint merge?", "sqlite-wal", "paraphrase", "answerable"),
    ("What permission allows a caller to invoke only the calculator MCP tool?", "mcp-scope", "scope", "answerable"),
    ("Why is a role by itself insufficient to authorize one named tool?", "mcp-scope", "paraphrase", "answerable"),
    ("Which scope naming pattern represents permission for a single MCP function?", "mcp-scope", "synonym", "answerable"),
    ("How do per-tool scopes limit an MCP principal's authority?", "mcp-scope", "scope", "answerable"),
    ("When should a grounded RAG assistant refuse to answer?", "rag-abstention", "abstention", "answerable"),
    ("What should retrieval do when context contains no support for the claim?", "rag-abstention", "paraphrase", "answerable"),
    ("Why is inventing a response from an empty context unsafe?", "rag-abstention", "synonym", "answerable"),
    ("How can an assistant avoid unsupported claims in a cited answer?", "rag-abstention", "paraphrase", "answerable"),
    ("Which operations are safest to retry automatically?", "retry-idempotent", "reliability", "answerable"),
    ("Why can repeating a non-idempotent write be dangerous?", "retry-idempotent", "paraphrase", "answerable"),
    ("What property should a request have before a client repeats it after failure?", "retry-idempotent", "synonym", "answerable"),
    ("How can retries duplicate side effects?", "retry-idempotent", "paraphrase", "answerable"),
    ("Which checks belong in a CI promotion gate?", "ci-gates", "synonym", "answerable"),
    ("What must run before a software change is promoted?", "ci-gates", "paraphrase", "answerable"),
    ("Why are type and security checks part of continuous integration?", "ci-gates", "paraphrase", "answerable"),
    ("What is the difference between a CI gate and publishing a deployment?", "ci-gates", "distractor", "answerable"),
    ("What connects all spans belonging to one distributed request?", "otel-trace", "paraphrase", "answerable"),
    ("Why does a trace identifier matter across router and tool boundaries?", "otel-trace", "synonym", "answerable"),
    ("How is a causal request timeline represented in OpenTelemetry?", "otel-trace", "paraphrase", "answerable"),
    ("Which observability object preserves the sequence of spans for one request?", "otel-trace", "synonym", "answerable"),
    ("What does a tool timeout limit at the host boundary?", "mcp-timeout", "timeout", "answerable"),
    ("Does cancelling a Python caller necessarily kill its running tool thread?", "mcp-timeout", "paraphrase", "answerable"),
    ("Why is a deadline useful around an MCP tool invocation?", "mcp-timeout", "synonym", "answerable"),
    ("What failure remains possible after a timed-out thread is cancelled?", "mcp-timeout", "timeout", "answerable"),
    ("How do roles and tenant isolation protect different boundaries?", "rbac-tenant", "security", "answerable"),
    ("What prevents a valid principal from reading another tenant's data?", "rbac-tenant", "paraphrase", "answerable"),
    ("Which control grants capabilities and which control separates customers?", "rbac-tenant", "synonym", "answerable"),
    ("Why is tenant filtering needed even when a user has a valid role?", "rbac-tenant", "paraphrase", "answerable"),
    ("What does RPO measure after a disaster?", "rpo-recovery", "synonym", "answerable"),
    ("Is RPO about restore time or acceptable data loss?", "rpo-recovery", "paraphrase", "answerable"),
    ("How far back may the latest recoverable copy be under the RPO target?", "rpo-recovery", "paraphrase", "answerable"),
    ("Which recovery metric is expressed as a time window of lost data?", "rpo-recovery", "synonym", "answerable"),
    ("Which policy governs the color of a mountain sunset on an unrelated planet?", None, "no-answer", "unanswerable"),
    ("What is the recipe for a dish not mentioned anywhere in the corpus?", None, "no-answer", "unanswerable"),
    ("Which employee badge number belongs to a person absent from these records?", None, "no-answer", "unanswerable"),
    ("How many moons orbit the fictional object described outside this dataset?", None, "no-answer", "unanswerable"),
    ("What is the chemical formula of a substance never discussed in the notes?", None, "no-answer", "unanswerable"),
    ("Which unrelated sports result was omitted from every document?", None, "no-answer", "unanswerable"),
)


def build_adversarial_corpus() -> list[Document]:
    return [
        Document(
            document_id=document_id,
            title=title,
            text=text,
            metadata={"category": category, "benchmark": "adversarial"},
        )
        for document_id, title, text, category in _CORPUS
    ]


def build_adversarial_dataset() -> list[dict[str, object]]:
    return [
        {
            "id": f"adv-{index:03d}",
            "question": question,
            "expected_document": expected_document,
            "category": category,
            "answerability": answerability,
        }
        for index, (question, expected_document, category, answerability) in enumerate(_QUESTIONS)
    ]
