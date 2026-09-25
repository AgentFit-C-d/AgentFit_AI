# AgentFit AI

AI service for AgentFit: document extraction, analysis, Profile validation and evaluation.
Service boundary: Next.js -> Spring Boot -> FastAPI. Only Spring Boot accesses PostgreSQL.

## Workflow

Create feature/<feature-name> before implementation. Follow Spec -> Plan -> Tasks -> Tests -> Implementation -> Validation, then commit and push the feature branch. Merge is a separate action.

## Local setup

Set UPSTAGE_API_KEY in the root .env file. Never commit .env.
On the feature branch, run Profile unit tests from ai_service/ with Python 3.12:

```text
python -m unittest discover -s tests -v
```

Feature scope and validation evidence live under specs/ai-developer/01-profile-contract/.

## Solar text analysis (local development)

From ai_service/ with Python 3.12, run the fixed synthetic evaluation:

```text
python -m agentfit_ai.evaluate --live
```

This makes six analyses (12 to 18 billable calls) using UPSTAGE_API_KEY from the environment or root .env. No extra packages are needed. Reports contain outcomes and metadata only.

The Python module agentfit_ai.solar.SolarAnalyzer accepts document text and a generated document ID, returning a validated draft Profile with evidence positions. By default it does not write files. Optional local diagnostics can retain failed responses for debugging.

Spec, plan, tasks and measured limitations: [Solar analysis](specs/ai-developer/04-analysis-provider/README.md). Latest Solar prompt separation (profile-v18): 70 unit tests, 24/24 existing synthetic runs, 2/2 new synthetic cases, and 3/4 real-document runs passed. All successful final runs passed without repair; one real run timed out. The full quality gate remains unmet. See [current validation](specs/ai-developer/04-analysis-provider/prompt-separation/validation.md). HTTP endpoints, PDF extraction and Spring integration remain future work.

Fixed stability evaluation (24 analyses, 48 to 72 billable calls, no network retries; use a new report filename each time):

```text
python -m agentfit_ai.name_stability --live --report ../output/name-stability.json
```

[Stability spec and evidence](specs/ai-developer/04-analysis-provider/stability/validation.md).

Staged extraction makes two calls (metadata/technology and features), then at most one correction call for invalid fields. Profile shape remains unchanged. Results expose provider_calls, repaired_fields and first_pass_validated; usage totals cover all successful provider responses. Structural validation does not establish semantic correctness.


## Call diagnostics (local)

From ai_service/, enable diagnostic file storage explicitly:

```text
python -m agentfit_ai.evaluate --live --diagnostics-dir ../output/diagnostics --report ../output/new-evaluation.json
python -m agentfit_ai.diagnostics --directory ../output/diagnostics
```

Results and analysis errors expose per-call diagnostics even without file storage.
Records contain timing, size, usage and safe error metadata. Raw responses are stored only for failed calls in a finally failed analysis; repaired successes store no raw responses. Sensitive or unparseable responses are omitted.
Local records expire after seven days and are purged on read, write or the explicit purge command. A stopped process cannot delete files; deployment needs scheduled cleanup and access controls. Windows uses inherited directory ACLs.
86 unit tests and six live synthetic analyses passed. This adds observability; it does not fix the previously observed provider timeout.
See [diagnostics spec and validation](specs/ai-developer/04-analysis-provider/call-diagnostics/validation.md).
