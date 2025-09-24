# Zagori Tools

Proxy a Notion integration through a FastAPI server that ChatGPT can call as a single Action.

## Features
- `GET /healthz` – readiness probe for deployment checks.
- `POST /notion/request` – forwards a method/path/body triple directly to the Notion REST API.
- `GET /.well-known/ai-plugin.json` – manifest pointing ChatGPT at the generated OpenAPI schema.

## Getting Started
1. Provide your Notion integration token via environment variable or a `.env` file (auto-loaded on startup):
   ```bash
   echo 'NOTION_API_TOKEN=secret_token_from_notion' > .env
   echo 'NOTION_API_VERSION=2022-06-28' >> .env  # optional override
   ```
2. Install the project in editable mode:
   ```bash
   pip install -e .
   ```
3. Run the development server (defaults to port 8000):
   ```bash
   zagori-tools
   ```
   or
   ```bash
   uvicorn zagori_tools.server:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Open the interactive docs at http://localhost:8000/docs.
5. The manifest lives at http://localhost:8000/.well-known/ai-plugin.json.

## Testing
- Install the test extras once: `pip install -e .[test]`
- Run the suite with `pytest`

## Wiring into ChatGPT
- Deploy the server somewhere reachable from ChatGPT (for local testing you can use a tunnelling tool like `cloudflared` or `ngrok`).
- In the GPT builder, create a new Action and provide the manifest URL (`https://<your-host>/.well-known/ai-plugin.json`).
- ChatGPT submits JSON bodies like `{ "method": "POST", "path": "/v1/pages", "body": { ... } }` and receives the raw Notion response.

## Next Steps
- Add authentication or IP restrictions before exposing the proxy publicly.
- Log or restrict the forwarded methods/paths if you need finer-grained control.
- Replace placeholder contact/legal URLs in the manifest with your own details.
