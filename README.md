# Zagori Tools

A tool server I vibe coded so that I can plug it into ChatGPT, and documented so I know how to use it.

## Features
- `GET /healthz` – readiness probe for deployment checks.
- `GET /time` – returns the current UTC timestamp (extendable for other timezones).
- `POST /math/sum` – sums a list of floating-point numbers.
- `GET /.well-known/ai-plugin.json` – manifest that points ChatGPT to the generated OpenAPI spec.

## Getting Started
1. Install the project in editable mode:
   ```bash
   pip install -e .
   ```
2. Run the development server (defaults to port 8000):
   ```bash
   zagori-tools
   ```
   or
   ```bash
   uvicorn zagori_tools.server:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Open the interactive docs at http://localhost:8000/docs.
4. The manifest lives at http://localhost:8000/.well-known/ai-plugin.json.

## Testing
- Install the test extras once: `pip install -e .[test]`
- Run the suite with `pytest`

## Wiring into ChatGPT
- Deploy the server somewhere reachable from ChatGPT (for local testing you can use a tunnelling tool like `cloudflared` or `ngrok`).
- In the GPT builder, create a new Action and provide the manifest URL (`https://<your-host>/.well-known/ai-plugin.json`).
- ChatGPT will ingest the OpenAPI schema at `/openapi.json` and can invoke the defined endpoints.

## Next Steps
- Add authentication once you deploy beyond local experiments.
- Expand the utility endpoints with the capabilities your GPT needs.
- Replace placeholder contact/legal URLs in the manifest with your own details.
