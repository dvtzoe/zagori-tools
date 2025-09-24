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
2. Point the server at your TLS certificate and key so it can listen on HTTPS 443:
   ```bash
   echo 'SSL_CERTFILE=/etc/letsencrypt/live/example.com/fullchain.pem' >> .env
   echo 'SSL_KEYFILE=/etc/letsencrypt/live/example.com/privkey.pem' >> .env
   # echo 'SSL_KEYFILE_PASSWORD=...' >> .env  # only if your key is encrypted
   ```
3. Install the project in editable mode:
   ```bash
   pip install -e .
   ```
4. Run the server (defaults to `0.0.0.0:443` with HTTPS enabled):
   ```bash
   zagori-tools
   ```
   or
   ```bash
   uvicorn zagori_tools.server:app --host 0.0.0.0 --port 443 --ssl-certfile $SSL_CERTFILE --ssl-keyfile $SSL_KEYFILE
   ```
5. Open the interactive docs at https://<your-host>/docs.
6. The manifest lives at https://<your-host>/.well-known/ai-plugin.json.

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
