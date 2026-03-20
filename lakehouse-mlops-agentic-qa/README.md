# lakehouse-mlops-agentic-qa

An end-to-end MLOps platform for a RAG-based QA system, built on a medallion lakehouse architecture. The project demonstrates production data engineering and ML deployment practices — from raw document ingestion through quality gates, retrieval-augmented generation, regression testing, drift monitoring, and automated promotion decisions.

Runs locally with zero cloud dependencies for fast iteration, and deploys to Azure as a lakehouse MLOps platform (ADLS Gen2, Databricks, Azure ML, Container Apps) via Bicep IaC and GitHub Actions CI/CD.

## Why this project matters

Production ML systems fail silently. A model that passed all tests last week can degrade today because the underlying data shifted, a document was dropped from the corpus, or an upstream schema changed. Most MLOps demos stop at "deploy the model." This project simulates what happens *after* deployment: how do you know the system is still good enough to serve?

The pipeline implements the practices that distinguish production ML from notebook ML:

- **Data quality gates** that block bad data before it reaches the model
- **Regression tests** with deterministic assertions that catch answer degradation
- **Drift detection** that flags distribution shifts in the data layer
- **Automated promotion logic** that makes reject/canary/production decisions from evidence, not intuition

The RAG system is intentionally simple. The engineering around it — the pipeline, the gates, the evaluation harness, the decision engine — is the point.

## Architecture

```mermaid

flowchart LR
    A[Raw Documents] --> B[Bronze]
    B --> C[Silver]
    C --> D[Gold]

    B --> QB[Bronze Gate]
    C --> QS[Silver Gate]
    D --> QG[Gold Gate]

    D --> E[Build Index]
    E --> F[Retrieve]
    F --> G[Generate]

    G --> H[Regression]
    D --> I[Drift Report]

    QB --> J[Promotion Engine]
    QS --> J
    QG --> J
    H --> J
    I --> J

    J --> K[Release Decision]

    class A input;
    class B,C,D pipeline;
    class QB,QS,QG gates;
    class E,F,G rag;
    class H,I eval;
    class J,K release;

    classDef input fill:#475569,stroke:#cbd5e1,color:#ffffff,stroke-width:1.5px;
    classDef pipeline fill:#2563eb,stroke:#93c5fd,color:#ffffff,stroke-width:1.5px;
    classDef gates fill:#d97706,stroke:#fcd34d,color:#ffffff,stroke-width:1.5px;
    classDef rag fill:#16a34a,stroke:#86efac,color:#ffffff,stroke-width:1.5px;
    classDef eval fill:#7c3aed,stroke:#c4b5fd,color:#ffffff,stroke-width:1.5px;
    classDef release fill:#e11d48,stroke:#fda4af,color:#ffffff,stroke-width:1.8px;

```

## Azure architecture

The local-first design maps directly to Azure services for production deployment:

```mermaid
flowchart TB
  subgraph gh [GitHub]
    Repo[Repository] --> Actions[GitHub Actions<br/>lint · test · build · deploy]
  end

  subgraph azure [Azure Resource Group]
    subgraph data [Data Layer]
      ADLS[ADLS Gen2<br/>raw / lake / artifacts]
    end

    subgraph compute [Compute]
      Databricks[Azure Databricks<br/>Pipeline Jobs]
      ContainerApp[Container Apps<br/>FastAPI Serving]
    end

    subgraph mlops [MLOps]
      AzureML[Azure ML Workspace<br/>MLflow Tracking]
    end

    subgraph security [Security]
      KeyVault[Azure Key Vault]
      ACR[Container Registry]
    end
  end

  Actions -->|push image| ACR
  Actions -->|deploy revision| ContainerApp
  ACR --> ContainerApp
  Databricks -->|read/write| ADLS
  ContainerApp -->|fetch secrets| KeyVault
  Databricks -->|log metrics| AzureML
```

| Local component | Azure service | Notes |
|----------------|---------------|-------|
| `data/raw/`, `data/lake/` | ADLS Gen2 | Medallion layout preserved as containers |
| `artifacts/` | ADLS Gen2 + Azure ML | Artifacts in storage, metrics in MLflow |
| Pipeline CLI (`lmq pipeline run`) | Azure Databricks job | Same Python package, Databricks compute |
| FastAPI server | Azure Container Apps | Containerized, scale-to-zero |
| `OPENAI_API_KEY` env var | Azure Key Vault | Secrets fetched at startup, env var fallback |
| JSON artifacts | Azure ML (MLflow) | Pipeline runs, regression, promotion tracked |
| — | GitHub Actions | Lint → test → build → push → deploy |
| — | Bicep IaC (`infra/`) | All Azure resources declared as code |

## Folder structure

```text
lakehouse-mlops-agentic-qa/
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions: lint, test, build, deploy
├── configs/
│   ├── pipeline.yaml             # local paths, thresholds, and promotion rules
│   └── pipeline.azure.yaml       # Azure paths (Databricks / ADLS Gen2)
├── data/
│   ├── raw/                      # source documents (.md, .txt)
│   ├── raw_fail/                 # intentionally bad input for gate demos
│   └── lake/                     # generated Parquet (gitignored)
│       ├── bronze/
│       ├── silver/
│       └── gold/
├── infra/
│   ├── main.bicep                # Azure resources (ADLS, Key Vault, ACR, etc.)
│   └── parameters.json           # deployment parameters
├── notebooks/
│   └── databricks_pipeline.py    # Databricks job wrapper
├── src/lmq/
│   ├── cloud/                    # Azure integrations (all optional)
│   │   ├── storage.py            # ADLS Gen2 storage_options helper
│   │   ├── keyvault.py           # Key Vault secret loader
│   │   └── mlflow_log.py         # MLflow experiment tracking
│   ├── pipeline/                 # bronze, silver, gold, DuckDB smoke, manifest
│   ├── quality/                  # per-layer gate checks and models
│   ├── rag/                      # chunking, ChromaDB index, retrieve, generate
│   ├── agent/                    # minimal retrieve-then-generate orchestrator
│   ├── serving/                  # FastAPI app (GET /health, POST /v1/qa)
│   ├── eval/                     # regression runner and scoring metrics
│   ├── monitoring/               # Evidently drift + quality reports
│   ├── promotion/                # rules-based promotion engine
│   ├── cli/                      # Typer CLI (all commands)
│   └── config.py                 # Pydantic config models
├── tests/
│   ├── golden/                   # qa_pairs.jsonl golden set
│   ├── test_api.py               # FastAPI endpoint tests
│   ├── test_evidently.py         # Evidently report generation test
│   ├── test_metrics.py           # scoring function unit tests
│   ├── test_promotion.py         # promotion engine rule tests
│   └── test_regression.py        # regression runner integration test
├── artifacts/                    # all generated artifacts (gitignored)
│   ├── runs/                     # *_run_manifest.json
│   ├── gates/                    # per-layer gate JSONs
│   ├── chroma/                   # ChromaDB vector index
│   ├── regression/               # *_regression.json
│   ├── evidently/                # HTML report + JSON summary
│   └── promotion/                # *_promotion.json
├── Dockerfile                    # multi-stage build for Container Apps
├── pyproject.toml
└── README.md
```

## Setup

Requires Python 3.11+.

```bash
git clone <repo-url> && cd lakehouse-mlops-agentic-qa
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
pip install -U pip && pip install -e ".[dev]"

# Windows PowerShell
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -e ".[dev]"
```

The first `lmq qa build-index` will download the `all-MiniLM-L6-v2` ONNX model (~80 MB) to a local cache. No API keys are required — the QA system runs in offline stub mode by default.

## Pipeline flow

The medallion pipeline reads `.md` and `.txt` files from `data/raw/`, transforms them through three layers of increasing quality, and writes Parquet files under `data/lake/`. Each layer transition passes through a quality gate that can fail the entire run.

```bash
lmq pipeline run
```

**Bronze** ingests raw files as-is with metadata. **Silver** cleans and normalizes text, deduplicates by `doc_id`, and computes a content hash. **Gold** splits clean text into fixed-size chunks ready for indexing.

Each run produces:
- Parquet files at `data/lake/{bronze,silver,gold}/`
- Gate results at `artifacts/gates/<layer>_<run_id>.json`
- A run manifest at `artifacts/runs/<run_id>_run_manifest.json` with DuckDB smoke-check metadata

To trigger a gate failure, point the pipeline at the intentionally bad input:

```bash
lmq pipeline run --raw-dir data/raw_fail
```

The bronze gate detects the empty document and exits with code 2.

## QA flow

Build a ChromaDB vector index from the gold layer, then ask questions:

```bash
lmq qa build-index
lmq qa ask "What are quality gates in MLOps?"
```

In offline stub mode (default, no API key needed), the answer is assembled from the top retrieved chunks with source metadata. If `OPENAI_API_KEY` is set, the system calls an OpenAI-compatible API to generate a natural-language answer grounded in the same retrieved context.

## Regression testing

A golden set of question/expected-keyword pairs lives at `tests/golden/qa_pairs.jsonl`. The regression runner executes each question against the index, checks that expected keywords appear in the answer, and writes a JSON artifact with per-case pass/fail and an aggregate pass rate.

```bash
lmq eval regression
```

The same checks run under pytest:

```bash
pytest tests -v
```

## Evidently reporting

Generates a data-drift and data-quality report by comparing two gold Parquet snapshots. The report uses tabular features derived from the gold layer (chunk length, token count, chunk index) so Evidently can run standard statistical tests without touching embeddings.

```bash
# Self-comparison (zero drift, good for verifying the setup)
lmq report evidently

# Baseline vs current comparison
lmq report evidently --baseline data/lake/gold/gold_baseline.parquet --current data/lake/gold/gold.parquet
```

The HTML report is written to `artifacts/evidently/evidently_report.html` and can be opened in any browser. A machine-readable JSON summary is written alongside it.

## Promotion decision

The promotion engine reads the latest run manifest, regression report, and Evidently summary, then applies config-driven rules to produce a reject, canary, or production decision.

```bash
lmq release evaluate
```

The rules (configured in `configs/pipeline.yaml`):

| Condition | Decision |
|-----------|----------|
| Pipeline failed, any gate failed, regression below canary threshold, or drift exceeds limit | **reject** |
| Regression between canary and production thresholds | **canary** |
| All checks green, regression at or above production threshold | **production** |

The decision, reasons, thresholds used, and input values are written to `artifacts/promotion/<timestamp>_promotion.json`.

## FastAPI server

A thin wrapper over the same QA code path used by the CLI:

```bash
lmq serve
# Server runs at http://127.0.0.1:8000
# Interactive docs at http://127.0.0.1:8000/docs
```

Endpoints:
- `GET /health` — returns `{ "status": "ok", "version": "0.1.0" }`
- `POST /v1/qa` — accepts `{ "question": "...", "top_k": 3 }`, returns answer + sources + mode

## Demo walkthrough

### Successful production path

Run the full pipeline, build the index, run regression, generate an Evidently report, and evaluate for promotion:

```bash
lmq pipeline run
lmq qa build-index
lmq eval regression
lmq report evidently
lmq release evaluate
```

Expected output from `lmq release evaluate`:

```
Decision:  PRODUCTION
Reasons:
  - all checks passed
```

### Failure and reject path

Run the regression against a golden set that includes an impossible question (about Kubernetes, which is not in the corpus):

```bash
lmq eval regression --golden tests/golden/qa_pairs_fail.jsonl
lmq release evaluate
```

Expected output:

```
Decision:  REJECT
Reasons:
  - regression pass rate 50.0% < canary minimum 75.0%
```

The promotion engine picked up the latest regression artifact (which now has a 50% pass rate) and rejected the release. Restore the good state by re-running the standard regression:

```bash
lmq eval regression
lmq release evaluate
# Decision:  PRODUCTION
```

## CLI reference

```text
lmq pipeline run    [--config PATH] [--raw-dir PATH]
lmq qa build-index  [--config PATH]
lmq qa ask          QUESTION [--config PATH] [--top-k N]
lmq eval regression [--config PATH] [--golden PATH] [--top-k N]
lmq report evidently [--config PATH] [--baseline PATH] [--current PATH]
lmq release evaluate [--config PATH]
lmq serve           [--config PATH] [--host HOST] [--port PORT]
lmq version
```

## Running tests

```bash
pytest tests -v
```

21 tests covering quality gates, scoring metrics, regression runner, FastAPI endpoints, Evidently report generation, and all promotion engine decision paths.

## Deploy to Azure

**Prerequisites:** Azure CLI, a subscription, a GitHub repository.

### 1. Provision infrastructure

```bash
az group create --name lmq-rg --location eastus

az deployment group create \
  --resource-group lmq-rg \
  --template-file infra/main.bicep \
  --parameters infra/parameters.json
```

### 2. Configure GitHub secrets and variables

| Secret / Variable | Value |
|-------------------|-------|
| `AZURE_CREDENTIALS` (secret) | Service principal JSON (`az ad sp create-for-rbac --sdk-auth`) |
| `ACR_USERNAME` / `ACR_PASSWORD` (secrets) | From ACR admin credentials |
| `ACR_LOGIN_SERVER` (variable) | e.g. `lmqacr<suffix>.azurecr.io` |
| `AZURE_RESOURCE_GROUP` (variable) | e.g. `lmq-rg` |

### 3. Push to main

GitHub Actions runs the full pipeline: lint → test → Docker build → push to ACR → deploy new Container Apps revision.

### 4. Run the pipeline in Databricks

Upload `notebooks/databricks_pipeline.py` to your workspace, install the `lmq` wheel as a cluster library, and configure ADLS access via Unity Catalog or mount points. Results are logged to Azure ML (MLflow) automatically.

### Docker (local)

```bash
docker build -t lmq .
docker run -p 8000:8000 lmq
# API at http://localhost:8000/docs

# Run the pipeline inside the container
docker run lmq pipeline run
```

## Limitations

- **Stub LLM mode.** Without an API key, the QA system returns raw retrieved chunks instead of generated answers. This is intentional: it keeps the regression tests deterministic and the project runnable offline.
- **Small corpus.** The seed documents are three Markdown files. The architecture works the same way with thousands of documents, but the demo is designed to run in seconds.
- **Character-based chunking.** The gold layer uses simple fixed-size character splits. A production system would use semantic or sentence-boundary chunking.
- **No embedding drift.** Evidently reports use tabular features (chunk length, token count) rather than embedding vectors. This avoids heavyweight PCA but means the drift detection does not catch semantic shifts.
- **ChromaDB stays local.** The vector index runs inside the container. A production deployment would replace it with Azure AI Search or a managed vector database.
- **No real canary traffic splitting.** The promotion engine writes a JSON decision — it does not actually route traffic. Container Apps revision-based traffic splitting would be the natural next step.

## Future improvements

- Sentence-boundary or semantic chunking in the gold layer
- LLM-as-judge evaluation alongside keyword recall
- Embedding drift via PCA-reduced vectors in Evidently
- Azure AI Search replacing ChromaDB for managed vector indexing
- Human-in-the-loop approval UI for canary decisions
- Versioned gold snapshots for reproducible baseline comparisons
- Multi-model comparison in the regression runner
