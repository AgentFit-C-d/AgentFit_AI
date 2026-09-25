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

This makes six billable calls using UPSTAGE_API_KEY from the environment or root .env. No extra packages are needed. Reports contain outcomes and metadata only.

The Python module agentfit_ai.solar.SolarAnalyzer accepts document text and a generated document ID, returning a validated draft Profile with evidence positions. It does not persist results.

Spec, plan, tasks and measured limitations: [Solar analysis](specs/ai-developer/04-analysis-provider/README.md). Latest development evaluation: 5/6; production quality is not established. HTTP endpoints, PDF extraction and Spring integration remain future work.
