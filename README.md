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
