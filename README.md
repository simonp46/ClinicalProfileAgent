# therapy-meet-copilot

[![CI](https://github.com/simonp46/ClinicalProfileAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/simonp46/ClinicalProfileAgent/actions/workflows/ci.yml)

Clinical documentation copilot MVP for therapists.

## Core Outcome
This system ingests Google Meet transcript events, processes/de-identifies transcript text, generates therapist-facing draft artifacts with OpenAI, and supports review/approval through a Spanish internal dashboard.

It is explicitly **not** an autonomous clinician. All output requires human review.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic
- Queue: Celery + Redis
- DB: PostgreSQL
- Frontend: Next.js 15 + TypeScript + Tailwind
- Auth: local email/password + JWT access/refresh
- AI: OpenAI Responses API through adapter boundary
- Docs: Google Docs/Drive adapter + mock local equivalent
- Quality: Ruff, Black, MyPy, ESLint, Prettier
- Tests: pytest + Playwright smoke

## Monorepo
- `apps/api`
- `apps/web`
- `workers`
- `packages/shared`
- `docs`
- `infra`
- `scripts`

## Quick Start (Docker)
1. Copy env:
   - `cp .env.example .env`
2. Start stack:
   - `docker compose up --build`
3. Seed demo data:
   - `make seed`
4. Run fixture-driven pipeline:
   - `make fix-demo-email` (si vienes de una base vieja)
   - `make demo`
5. Open apps:
   - API docs: `http://localhost:8000/docs`
   - Dashboard: `http://localhost:3000/login`

Demo login:
- email: `demo@clinic.com`
- password: `demo1234`

## One-Click Local Demo Path (No Google/OpenAI Credentials)
Default `.env.example` already uses:
- `USE_MOCK_GOOGLE=true`
- `USE_MOCK_OPENAI=true`

This enables:
- Fixture transcript ingestion (`apps/api/fixtures/sample_transcript.json`)
- Deterministic AI generation
- Mock Google Doc artifact in `data/artifacts`
- DOCX export in `data/artifacts/exports`

## Real Integration Path
Provide these vars and set mocks false:
- `USE_MOCK_GOOGLE=false`
- `USE_MOCK_OPENAI=false`
- `OPENAI_API_KEY`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_SERVICE_ACCOUNT_FILE` (optional fallback for domain-wide delegation)
- `GOOGLE_IMPERSONATED_USER` (optional fallback if you are not using therapist OAuth)
- `GOOGLE_DOCS_OUTPUT_FOLDER_ID` (optional)
- `GOOGLE_WEBHOOK_SHARED_SECRET` (recommended)

Then open `Perfil profesional`, press `Conectar Google`, and authorize the therapist's real Google account. That authorization is what enables reading Google Calendar, Google Meet metadata, and transcript-linked Google Docs with real user consent.

## Make Commands
- `make dev` - full stack
- `make test` - backend + frontend tests
- `make lint` - backend + frontend lint/type checks
- `make seed` - seed therapist/patient/session + prompts
- `make fix-demo-email` - migrate legacy demo email (.local -> .com)
- `make demo` - ingest fixture -> generate draft -> create/export doc
- `make worker` - worker only
- `make migrate` - alembic upgrade

## Migrations
Inside API container:
- `alembic upgrade head`
- `alembic revision --autogenerate -m "message"`

Initial migration file:
- `apps/api/alembic/versions/20260325_0001_initial.py`

## API Surface
Implemented endpoints:
- `POST /webhooks/google/workspace-events`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{id}`
- `GET /api/v1/sessions/{id}/transcript`
- `POST /api/v1/sessions/{id}/process`
- `POST /api/v1/sessions/{id}/generate-draft`
- `POST /api/v1/sessions/{id}/regenerate-draft`
- `POST /api/v1/drafts/{id}/approve`
- `POST /api/v1/drafts/{id}/reject`
- `POST /api/v1/drafts/{id}/create-google-doc`
- `POST /api/v1/documents/{id}/export-docx`
- `GET /api/v1/risk-flags`
- `GET /api/v1/audit-logs`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/profile/me`
- `PATCH /api/v1/profile/me`
- `POST /api/v1/profile/me/google/connect`
- `POST /api/v1/profile/me/google/disconnect`
- `GET /api/v1/profile/google/callback`
- `POST /api/v1/profile/me/photo`
- `POST /api/v1/profile/me/signature`
- `POST /api/v1/profile/me/template`
- `GET /api/v1/profile/me/assets/{asset_type}`
## Sample cURL
Login:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@clinic.com","password":"demo1234"}'
```

Process session synchronously:
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/process?sync=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

Generate draft synchronously:
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/generate-draft?sync=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

Approve draft:
```bash
curl -X POST http://localhost:8000/api/v1/drafts/<DRAFT_ID>/approve \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"therapist_review_notes":"Revisado"}'
```

Create doc:
```bash
curl -X POST http://localhost:8000/api/v1/drafts/<DRAFT_ID>/create-google-doc \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

Export DOCX:
```bash
curl -X POST http://localhost:8000/api/v1/documents/<DOCUMENT_ID>/export-docx \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Testing
Backend:
- `cd apps/api && pytest`

Frontend smoke:
- `cd apps/web && npm test`

## Notes
- UI language and generated clinical text are Spanish.
- Code/comments are English.
- Prompt templates are versioned under `apps/api/prompts/v1` and tracked in DB (`prompt_templates`).
- Audit logs and processing job traces are persisted for traceability.

## Architecture Doc
See `docs/architecture.md`.

## PDF Export y Previsualizacion
- Endpoint para exportar PDF: `POST /api/v1/documents/{id}/export-pdf`
- Endpoint para servir archivo: `GET /api/v1/documents/{id}/file?format=pdf|docx&disposition=inline|attachment`
- La UI ya incluye botones para:
  - Exportar PDF
  - Previsualizar PDF (abre en pestana nueva)
  - Descargar PDF (flujo de descargas del navegador)

### Plantilla PDF con Logo y Firma
- La exportacion PDF mock usa la plantilla base en `apps/api/assets/templates/plantilla_historia_clinica_respira_integral_of.pdf`.
- Se conserva logo/firma/diseno de la plantilla y se sobreescribe solo el contenido clinico.
- La firma del terapeuta se ubica de forma automatica en el campo designado (prioridad: campo PDF/widget con nombre tipo responsable/firma, luego deteccion por texto "Aceptacion y firmas" + "Responsable", y finalmente fallback controlado).
- Si actualizas la plantilla, vuelve a ejecutar `docker compose build api` y luego `docker compose up --build`.
- Limpieza total de cache/legacy templates:
  `docker compose run --rm api bash -lc "cd /app/apps/api && python -m app.scripts.purge_template_cache"`

### Actualizacion de datos personales del paciente
- Endpoint: `PATCH /api/v1/sessions/{id}/patient`
- Campos soportados: `full_name`, `external_patient_id`, `phone`, `birth_date`, `address`, `profession`, `email`.
- Disponible en la UI de detalle de sesion bajo "Datos Personales del Paciente".

## Registro y Perfil del Terapeuta
- La pantalla de login ahora permite `Ingresar` y `Registrar` nuevas cuentas para demo.
- Vista de perfil: `http://localhost:3000/profile` (requiere sesion iniciada).
- Desde perfil se puede:
  - actualizar nombre y datos de contacto del terapeuta
  - cargar foto de perfil
  - cargar firma personal
  - cargar plantilla PDF/DOCX usada para exportaciones de borrador
- Las plantillas y firmas cargadas se aplican en nuevas exportaciones PDF/DOCX del terapeuta.
- La generacion del borrador clinico tambien adapta el orden/secciones segun la plantilla cargada (cuando se puede inferir estructura).
- Al registrar un usuario nuevo se crean automaticamente al menos 3 sesiones demo con transcript y borrador inicial.




## Formato Respiratorio del Borrador
- El borrador clinico se genera en 8 secciones: identificacion, HPI, antecedentes, checklist respiratorio, evaluacion clinica respiratoria, pruebas, impresion y plan terapeutico.
- Cuando falta informacion, se registra como `No referido`.
- Se mantiene redaccion en tercera persona y estilo clinico profesional.
- Si el usuario carga plantilla en perfil, el sistema intenta respetar el orden de encabezados detectado en la plantilla.







