# VoiceOS — AI voice calling workspace

A React JSX + Vite + Tailwind dashboard backed by FastAPI, SQLAlchemy, and a real SQLite database. Create and configure agents, converse through a browser, inspect persisted call transcripts, export CSV reports, and configure real Twilio phone calls. No example call records or manufactured analytics are seeded.

## What is implemented

- Argon2 password hashes, eight-hour signed JWT sessions, admin authorization, profile editing, protected APIs and React workspace.
- Agent creation, editing, deletion, validation, three language options, prompt/model/voice/temperature/duration configuration. Agents with history can be deactivated instead of deleted.
- Two browser voice paths: Web Speech STT → authenticated WebSocket → OpenAI Chat Completions → browser speech synthesis, or bidirectional PCM24k audio → OpenAI Realtime with AudioWorklet capture/playback and speech-triggered interruption. Each turn and the greeting are stored in SQLAlchemy. Text input works without browser STT. Microphone mute, explicit turn controls, speech interruption, connection state, transcript consent, and session time limits.
- Database-backed dashboard metrics, daily/weekly/monthly charts, agent performance, call search/status filtering/pagination, transcript dialogs, conversation history, authenticated CSV exports with spreadsheet formula escaping.
- Real Twilio outbound API calls, incoming number routing, signed webhooks, call status callbacks, provider-confirmed termination, provider errors, phone speech recognition and TTS with TwiML Gather/Say, plus optional bidirectional PCMU Media Streams → OpenAI Realtime. Incoming callers explicitly press 1 to consent before transcripts are stored.
- Backend-only provider secrets, restricted CORS and WebSocket origins, single-use short-lived WebSocket tickets, process-local rate limits, recipient allowlist, outbound kill switch, daily call-count cap, and provider-enforced outbound duration cap.
- Initial Alembic migration, backend tests, frontend presentation tests, Dockerfiles, and deployment notes.

## Requirements

Python 3.12+; Node 20.19+; npm. SQLite is the default. A PostgreSQL deployment needs `psycopg[binary]` and a `postgresql+psycopg://` database URL. Browser microphone recognition generally works best in Chrome/Edge on localhost or HTTPS; available Hindi/Marathi STT and voices vary by browser, OS, and provider.

## macOS / Linux setup

From this project folder:

```sh
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set a random JWT_SECRET (32+ characters) and ADMIN_PASSWORD (12+).
# Optional: python -c 'import secrets; print(secrets.token_urlsafe(48))'
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd apps/web
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Sign in with `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`. Visit [API docs](http://127.0.0.1:8000/docs) to inspect REST schemas. The database must be migrated before API startup. Startup creates the initial admin only if the email does not already exist; changing `.env` does not reset an existing user's password.

## Windows PowerShell setup

```powershell
Set-Location services/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set JWT_SECRET and ADMIN_PASSWORD as above.
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal from the project root:

```powershell
Set-Location apps/web
npm ci
npm run dev
```

## First browser conversation

1. Set `OPENAI_API_KEY` in backend `.env`, restart the API, and check Settings for the provider connection indicator. This indicator means credentials are present, not that provider access has been verified.
2. Create an agent in AI Agents. Choose an OpenAI model your account can access. The initial default is `gpt-4o-mini`; arbitrary models may not accept the same temperature/token options.
3. Open Voice Playground, select the agent and agree to transcript storage. Start the conversation.
4. Click **Speak** for each turn, grant browser microphone access, and speak. The response is read aloud using an installed browser voice. Use text input if recognition is unavailable.
5. Clicking Speak or sending a message cancels existing speech playback; Stop voice playback also interrupts it. Mute aborts recognition. Click End to finish. Unexpected disconnects are marked interrupted rather than completed.
6. Review Call History and Conversations. Analytics reflect these actual records.

The browser's own speech service may transmit audio to its vendor. No raw audio or audio recordings are stored by this application. The UI discloses transcript storage before starting.

## Real Twilio setup

Do not enable outbound calling until you have verified provider permissions and obtained recipient consent.

```dotenv
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
PUBLIC_BASE_URL=https://your-public-api.example.com
OUTBOUND_ENABLED=true
OUTBOUND_ALLOWLIST=+919876543210,+12345678900
DAILY_CALL_LIMIT=10
MAX_CALL_SECONDS=300
```

Use E.164 numbers with no spaces in the allowlist. Set a separate hard spending limit/alert in your Twilio account: the local safeguard caps call count and duration, not currency spend. Trial accounts may require verified recipients. The configured from number must belong to your Twilio account. Credentials stay on the backend and are never editable/readable as secrets from React.

- **Outgoing:** Phone Calls → select agent → enter an allowlisted recipient → confirm consent → Place call → confirm the concrete recipient. The API records the actual provider SID/status. Refresh status retrieves webhook-updated state. End call requires provider confirmation.
- **Incoming:** assign your Twilio-owned number to an agent using Phone Calls. In the Twilio number settings, set the voice webhook to `POST https://your-public-api.example.com/api/v1/twilio/incoming`. Set the number's status callback to `POST https://your-public-api.example.com/api/v1/twilio/incoming-status`.
- Outgoing call status callbacks are supplied automatically at creation. Requests validate `X-Twilio-Signature` against the exact configured public URL; keep that URL free of a trailing slash. Preserve the external path/query behind a reverse proxy.
- Incoming calls ask the caller to press 1 before speech processing/transcript storage. Outgoing calls require previously obtained recipient consent in the UI. Calls announce that the participant is an AI and that text transcripts are saved; audio recording is disabled.
- Language recognition and Say support depend on Twilio's current voice/model/region capabilities; validate the chosen language on your account before rollout. Unsupported provider capabilities must not be represented as successfully tested.

## Validation

```sh
cd services/api
.venv/bin/python -m pytest -q
# Windows: .\.venv\Scripts\python -m pytest -q
cd ../../apps/web
npm test
npm run build
```

Backend tests use an isolated test database and mocked AI provider, exercising authentication, agent validation and history preservation, voice session persistence, one-use tickets, call safeguards, signature rejection, and report endpoints. Frontend tests check real call record rendering, empty states, and safe transcript text rendering. Live microphone recognition, actual AI calls, Twilio calls, and provider language support require manual tests with valid credentials; mocked tests do not establish that those integrations work live.

## Deployment

Build the frontend with `npm ci && npm run build`, serve `apps/web/dist` through a TLS reverse proxy, and proxy `/api` (including WebSocket upgrade) to FastAPI. Do not use the Vite development server in production. Run migrations as a separate release step, then start the API. Dockerfiles are supplied for both services. Supply secrets through your deployment environment or mounted secret storage; never bake `.env` into an image. Configure `CORS_ORIGINS` with the exact public frontend origin.

For PostgreSQL install `psycopg[binary]`, set `DATABASE_URL=postgresql+psycopg://...`, and run the same Alembic upgrade. A PostgreSQL instance was not used during local verification.

Run **one API worker** for this version: WebSocket tickets, rate limit state, and the outbound reservation lock are process-local. Multiple replicas require moving those to Redis and using a database-backed atomic quota reservation. Use a shared rate limiter at the reverse proxy, separate webhook rate limits from admin traffic, and verify trusted-proxy configuration. Add database backups, transcript retention/deletion policy, monitoring, credential rotation, and provider billing alerts before handling real customer data. The API does not implement user provisioning, MFA, password-reset email, refresh tokens, token revocation, or a currency-denominated spending ledger. Logging out clears the browser token; previously issued JWTs expire at their normal expiration.

## Current limits / remaining production work

This is a runnable baseline, not a certification of production readiness. Browser speech mode operates in explicit turns; Realtime mode continuously listens while connected and unmuted. Browser speech mode carries transcript text and complete AI responses. Realtime mode streams PCM24k browser audio or PCMU Twilio audio through OpenAI Realtime and persists completed transcript events. Browser speech playback can be interrupted; Realtime mode also uses server VAD for interruption. Gemini, cloud voice catalog discovery, call recording capture/playback, and multilingual provider fallbacks are not implemented. Recording entities are included for later expansion but no recording URL is fabricated or exposed. Settings display backend provider configuration; credentials and safeguards are changed through the server environment. Incoming call duration is checked between turns; configure provider-side inbound duration controls for a hard cap.

Call and conversation lists are administrator workspace data, not tenant-isolated data. Conversation listing is capped at the most recent 100 records. Metrics currently aggregate the full database in memory and should move to SQL aggregate queries for large deployments. The immutable initial migration creates the schema; future schema changes require new revision files using `alembic revision --autogenerate -m "description"`, reviewed before applying.

Provider references: [Twilio Call resource](https://www.twilio.com/docs/voice/api/call-resource), [Twilio Gather](https://www.twilio.com/docs/voice/twiml/gather), [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat).

## Realtime audio mode

On an agent, choose **OpenAI Realtime (streaming audio)**. This sets the model to `gpt-realtime`; choose a compatible model your account can access and a compatible voice name (default `alloy`). The same agent supports streaming browser and phone conversations. Temperature is only used by Chat Completions agents; Realtime does not receive this parameter.

In the browser, Start conversation requests microphone access and opens a PCM24k AudioWorklet transport. Audio flows only after an authenticated provider session is accepted. Mute disables microphone tracks; End and navigating away stop all tracks and close the audio context. Output audio chunks are queued in order; speaking triggers provider VAD interruption and clears queued playback. Text messages are also supported. This mode requires `getUserMedia`, AudioWorklet, and a 24kHz AudioContext on localhost/HTTPS; otherwise use a browser speech agent.

On Twilio, the consent flow and AI disclosure precede `<Connect><Stream>`. The signed WSS endpoint validates the call SID/account, bridges PCMU frames to OpenAI, sends generated frames back, and clears buffered audio on speech interruption. The bridge enforces its own duration limit and hangs up through the following TwiML. Provider callbacks remain the authority for final phone-call status. Completed transcript events may include text generated before an interruption; they are not an exact record of the audio the caller heard.

Realtime transports are covered with mocked provider events and TwiML configuration tests. No credentialed OpenAI/Twilio audio session has been verified. Validate model access, audio quality, browser echo cancellation, interruption timing, multilingual recognition, signed WSS handshakes, and provider billing on your own accounts before deployment.

References: [Realtime client events](https://developers.openai.com/api/reference/resources/realtime/client-events), [Twilio Media Streams messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages), [Twilio request security](https://www.twilio.com/docs/usage/security).

## Local verification result

The delivered workspace was checked with Python 3.14 and Node 20/22 tooling: 22 backend tests and 6 frontend tests passed, the Vite production build passed, a fresh SQLite migration and Alembic schema-drift check passed, and the frontend npm audit reported zero vulnerabilities. Login, agent creation, and desktop/mobile dashboard rendering were inspected locally; the 390px layout showed no horizontal overflow. The included GitHub Actions workflow has not been run remotely, and Docker images have not been built here. A harmless upstream Starlette/httpx TestClient deprecation warning appears in backend test output.

Local credentials, API keys, database records, installed dependencies, and build artifacts are excluded from Git. After cloning, copy `services/api/.env.example` to `.env` and configure your own administrator credentials and provider keys. No local users, agents, or conversations are included in the repository. Outbound calling defaults to disabled.
