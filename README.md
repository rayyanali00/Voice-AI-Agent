# CareCloud Voice AI Patient Registration

A time-boxed take-home implementation using **FastAPI, SQLAlchemy, SQLite, and a lightweight dashboard**. The backend is designed to be connected to a hosted voice platform such as Vapi.

## Architecture

Caller → Voice platform (speech recognition, LLM, speech synthesis) → `POST /patients` → FastAPI validation → SQLAlchemy → persistent database. The dashboard reads records from the same API-backed database.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- Dashboard: `http://127.0.0.1:8000/`
- Swagger API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

SQLite creates `patients.db` automatically and preserves data across process restarts when the deployment uses a persistent disk/volume. For ephemeral hosting, configure a persistent volume or use a managed PostgreSQL database.

## API endpoints

- `GET /patients` — list active records; filters `last_name`, `date_of_birth` (YYYY-MM-DD), `phone_number`
- `GET /patients/{patient_id}` — retrieve one record
- `POST /patients` — create; returns 201
- `PUT /patients/{patient_id}` — partial update
- `DELETE /patients/{patient_id}` — soft delete
- `GET /health` — health check

Successful responses use `{ "data": ..., "error": null }`. FastAPI/Pydantic rejects invalid payloads with HTTP 422. Duplicate active phone numbers return HTTP 409 with the existing record to support the returning-patient flow.

## Voice agent prompt / setup

Configure your voice platform to collect required fields, validate and clarify uncertain answers, read all collected fields back to the caller, and only call the create-patient tool after explicit confirmation. Do not ask for optional fields unless the caller opts in.

Recommended system prompt:

> You are a warm, concise patient registration coordinator. Collect first and last name, date of birth, sex (Male, Female, Other, or Decline to Answer), US phone number, street address, city, two-letter state, and ZIP code. Email is optional. Ask one question at a time. Handle corrections by updating the relevant field and repeat it back. Do not invent or assume information. DOB must not be in the future; phone must be a US 10-digit number; state and ZIP must be valid. Once required information is collected, ask whether the caller wants to provide insurance details, emergency contact, or preferred language. Read the full record back and ask the caller to explicitly confirm. Only after confirmation, call the patient-creation API with the structured JSON. If the API reports a duplicate, offer to update the existing record. If the API fails, apologize and do not claim registration succeeded. Never request or store payment information.

The `/voice/create_patient` endpoint accepts the same payload and optionally checks `X-API-Key` against `APP_API_KEY`. For a Vapi custom tool, configure a server tool that POSTs the confirmed JSON to this endpoint and passes the API key as a header. If using `/patients` directly, keep it private or add authentication before production.

## Environment variables

- `DATABASE_URL`: defaults to `sqlite:///./patients.db`; use a managed database URL for production.
- `APP_API_KEY`: optional shared secret for `/voice/create_patient`. Set a strong value in the hosting dashboard; never commit secrets.

## Limitations / next steps

- This is an assessment demo, not a HIPAA-compliant healthcare system. Use synthetic test data only.
- Configure a real US number and hosted voice agent in Vapi/Retell/Twilio; those provider accounts and credentials are not included.
- Add authentication/rate limiting, structured redacted logs, automated tests, database migrations, and a managed persistent database before production.
- For hosted SQLite, attach a persistent disk; otherwise records may be lost on redeploy.
- Configure the voice provider to send a confirmation read-back before invoking the create tool. The backend cannot itself prove that a human confirmation occurred.
