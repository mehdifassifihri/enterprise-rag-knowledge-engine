# Publication procedure and initial review

Publication update: the owner explicitly approved committing and pushing. Initial implementation commit `597ad52` was successfully pushed to `main` at https://github.com/mehdifassifihri/enterprise-rag-knowledge-engine. Earlier repository-state notes below describe the prepublication review. No license, tag, GitHub release or Upwork submission was created.

The owner selected `enterprise-rag-knowledge-engine` as the repository name. The current target is `https://github.com/mehdifassifihri/enterprise-rag-knowledge-engine.git`. Older prepublication notes below are historical and do not describe the current published repository.

Suggested description: “Tenant-scoped document ingestion, PostgreSQL hybrid retrieval, cited RAG answers, local MCP tools and reproducible evaluation.”

Suggested topics: `python`, `fastapi`, `postgresql`, `pgvector`, `rag`, `hybrid-search`, `mcp`, `llm-evaluation`, `multi-tenant`.

## Owner review gates

- Licensing stays pending by explicit owner choice. No LICENSE/MIT grant added. Resolve ownership and desired terms before inviting open-source reuse.
- `.env`/local output/build directories are ignored; `.env.example` has placeholders. Inspect staged content and use a full history scanner before publication. The included pattern guard is limited, not assurance that all secrets are absent.
- All committed demo/evaluation business documents are labeled synthetic. Review output artifacts and metadata manually; no real customer information was identified in the reviewed fixture directories.
- Runtime/dev locks exist, without hashes; images/actions use tags. Advisory scan evidence is point-in-time. Dependency-license inventory records installed package declarations, not a legal compatibility certification. Psycopg uses LGPL terms; binaries/bundled libraries may have additional redistribution obligations. Resolve unknown/multiple declarations and the intended distribution model before choosing a project license.
- Docker build/start and remote CI remain verification gates. The current full database suite, migration consistency check and API/MCP demo now pass (see FINAL_VERIFICATION). Do not imply they passed.

## Safe procedure after explicit approval

The owner subsequently approved the initial commit and push. This section preserves the review procedure; consult the final chat result for the published commit and remote status. Run from repository root. Review every file selected; do not stage ignored secrets or unrelated work.

```sh
make lint
make test
RUN_DB_TESTS=1 make test-integration
make evaluate-validate
make audit
bash demo/demo_requests.sh
# On a Docker-capable machine with protected .env configured:
docker compose config --quiet
docker compose build
docker compose up -d
curl --fail http://127.0.0.1:8000/ready
# Inspect intended source set, then stage explicitly:
git status --short
git add .dockerignore .env.example .gitattributes .github .gitignore Dockerfile \
  Makefile README.md alembic.ini docker-compose.yml pyproject.toml \
  requirements.lock requirements-dev.lock src migrations tests scripts docs demo \
  evaluation examples CONTRIBUTING.md
git diff --cached --check
git diff --cached --stat
git diff --cached
# Run a dedicated secret scanner on staged files and all history if any is imported.
# Only after reviewing and approving this exact snapshot:
git commit -m "Initial Enterprise Knowledge Engine portfolio release"
git branch -M main
# Confirm URL, ownership and remote state first; local origin is currently absent:
git remote add origin https://github.com/mehdifassifihri/enterprise-rag-knowledge-engine.git
git ls-remote origin
# If the remote gained commits, reconcile them; never force-push over remote work.
# Separate explicit approval is still required before executing this publication:
git push -u origin main
```

After confirming public visibility, successful remote CI and the published commit, replace the application link placeholder. Tags/releases, repository settings and submission of the Upwork proposal require separate owner action/approval. Availability and rate remain owner-supplied values. No issue templates were added because there is no established contributor workflow needing them.
