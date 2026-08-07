# Relay Messenger

A complete Messenger-style starter built from the guided backend workbook. It includes a responsive Next.js client, FastAPI REST/WebSocket API, PostgreSQL persistence, Redis presence/typing state, private MinIO media storage, JWT authentication, Alembic migrations, cursor pagination, and duplicate-message protection.

## Run everything with Docker

From `D:\chat-app`:

```powershell
docker compose up --build -d
docker compose ps
```

Open <http://localhost:3000>. The API documentation is available at <http://localhost:8000/docs>.
MinIO's local administration console is available at <http://localhost:9001>;
its credentials come from `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` in `.env`.
Use the paperclip beside the message box to upload an image, video, audio clip,
PDF, or other file. Files are private, limited to 10 MB by default, and can only
be downloaded by members of the conversation.

Follow logs or stop the complete stack with:

```powershell
docker compose logs -f api web
docker compose down
```

The API and web services use multi-stage builds. The API runtime contains only
its production virtual environment, while the frontend is exported to static
files and served by unprivileged Nginx. Build tools, source caches, tests, and
local dependencies are excluded from both images.

Set a deployment-safe secret before starting outside local development:

```powershell
$env:JWT_SECRET_KEY = "replace-with-a-long-random-secret"
$env:COOKIE_SECURE = "true"
$env:COOKIE_SAMESITE = "none"
$env:MINIO_SECRET_KEY = "replace-with-a-long-random-secret"
docker compose up --build -d
```

Authentication uses `HttpOnly`, `SameSite=Lax` access and refresh cookies. Keep
`COOKIE_SECURE=false` only for local HTTP development; enable it behind HTTPS.
When the frontend and backend use different hosted domains, such as Vercel plus
ngrok, set `COOKIE_SAMESITE=none` so browser fetch requests can include the auth
cookies.

### Google sign-in

Create a Google OAuth client with the **Web application** type, then add this
authorized redirect URI exactly:

```text
http://localhost:8000/api/v1/auth/google/callback
```

Google requires an exact match, including the scheme, hostname, path, and
trailing slash. For ngrok, add the current tunnel callback as a second
authorized redirect URI, for example:

```text
https://your-ngrok-domain.ngrok-free.dev/api/v1/auth/google/callback
```

The value in Google Cloud and `GOOGLE_REDIRECT_URI` must be identical. Every
time the ngrok hostname changes, update both places and restart the API.

Copy `.env.example` to `.env`, set `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET`, then rebuild the API and web containers. For deployment,
also set `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, and `COOKIE_SECURE=true` to the
HTTPS production URLs.

### Netlify frontend deployment

Connect the repository to Netlify. The root `netlify.toml` tells Netlify to
build `apps/web` and publish the static `apps/web/out` directory, so you do not
need to enter the monorepo paths manually.

Before the deploy, set this Netlify environment variable to the public origin
of the backend (not the Netlify frontend URL):

```text
NEXT_PUBLIC_BACKEND_DOMAIN=https://api.example.com
```

The frontend derives `https://api.example.com/api/v1` for HTTP requests and
`wss://api.example.com/api/v1/ws` for WebSocket connections. If you move the
backend to a new domain, update only `NEXT_PUBLIC_BACKEND_DOMAIN` and redeploy
the Netlify frontend. `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_WS_URL` are
still supported as optional advanced overrides.

The first frontend build does **not** need to know its own Netlify domain.
After Netlify creates the site, copy the stable site URL shown in Netlify (for
example, `https://your-site-name.netlify.app`) into the backend environment:

```text
FRONTEND_URL=https://your-site-name.netlify.app
CORS_ORIGINS=https://your-site-name.netlify.app
COOKIE_SECURE=true
COOKIE_SAMESITE=none
```

Restart/redeploy only the backend after changing those values. You do not need
to rebuild the frontend unless `NEXT_PUBLIC_BACKEND_DOMAIN` changes. Netlify
also exposes its generated main site URL as `URL` during builds, but it is not
the API endpoint and should not be assigned to `NEXT_PUBLIC_BACKEND_DOMAIN`.

For a temporary ngrok backend, set the backend environment like this:

```text
FRONTEND_URL=https://your-site-name.netlify.app
CORS_ORIGINS=https://your-site-name.netlify.app
COOKIE_SECURE=true
COOKIE_SAMESITE=none
GOOGLE_REDIRECT_URI=https://your-ngrok-domain.ngrok-free.app/api/v1/auth/google/callback
```

Also add that exact `GOOGLE_REDIRECT_URI` under **Google Cloud Console → APIs &
Services → Credentials → your Web application OAuth client → Authorized
redirect URIs**. A valid backend environment must use the same Netlify origin
for both `FRONTEND_URL` and `CORS_ORIGINS`; neither value may include a path.

Then set the Netlify frontend environment to:

```text
NEXT_PUBLIC_BACKEND_DOMAIN=https://your-ngrok-domain.ngrok-free.app
```

The web client automatically sends ngrok's `ngrok-skip-browser-warning`
header for `ngrok-free.app` and `ngrok-free.dev` API domains. Without that
header, a fresh browser can receive ngrok's interstitial HTML instead of the
API response, which browsers often surface as a missing CORS header.
Google sign-in also obtains its authorization URL through this API client and
then navigates directly to Google, avoiding the interstitial on the OAuth entry
route.

## Run locally without application containers (PowerShell)

From `D:\chat-app`:

```powershell
docker compose up -d

cd apps\api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd D:\chat-app\apps\web
npm install
npm run dev
```

Open <http://localhost:3000>. API docs are at <http://localhost:8000/docs>.

Register two users in separate browser profiles, search for the other username, start a conversation, and send messages in real time.

## Local Ollama support assistant

Relay includes an authenticated support assistant that sends prompts from the API server to your local Ollama instance. Install Ollama on the host, then download the configured model and start the stack:

```powershell
ollama pull gemma4:latest
docker compose up --build -d
```

Open Relay and select the robot button beside **New message**. The default Docker configuration connects the API container to Ollama on the host at `http://host.docker.internal:11434`. When running the API directly (without its container), it uses `http://localhost:11434`.

You can select another installed model in `.env`:

```text
OLLAMA_MODEL=gemma4:latest
```

Use `OLLAMA_BASE_URL` if Ollama runs on another machine or port. Keep that endpoint on a trusted private network; the browser never connects to Ollama directly.

## Verification commands

```powershell
cd D:\chat-app\apps\api
uv run pytest -p no:cacheprovider -v
uv run ruff check . --no-cache
uv run python -m scripts.smoke

cd ..\web
npm run lint
npm run build
```

## Configuration

- Backend defaults are in `apps/api/.env`; replace `JWT_SECRET_KEY` before any deployment.
- Frontend endpoints can be overridden by copying `apps/web/.env.example` to `apps/web/.env.local`.
- `POST /auth/logout` is stateless in this starter. Production logout should revoke a rotated refresh-token record.
- The connection manager supports multiple tabs/devices on one API process. Add Redis Pub/Sub forwarding before scaling to multiple API processes.

Stop the infrastructure with `docker compose down`. Add `-v` only when you intentionally want to erase local database and Redis data.
