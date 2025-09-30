# Zagori Tools

Proxy a Notion integration through a FastAPI server that ChatGPT and other LLMs can call as a single Action. This tool provides comprehensive access to the Notion API v2024-05-01 with enhanced guidance for AI assistants.

## Features
- `GET /healthz` – readiness probe for deployment checks.
- `POST /notion/request` – forwards a method/path/body triple directly to the Notion REST API.
- `GET /.well-known/ai-plugin.json` – manifest pointing ChatGPT at the generated OpenAPI schema.

## LLM Integration Guide

This tool is designed to teach LLMs how to effectively use the Notion API. Here are the key patterns and examples:

### Common Notion API Operations

#### 1. Retrieve a Page
```json
{
  "method": "GET",
  "path": "/v1/pages/{page_id}"
}
```

#### 2. Query a Database
```json
{
  "method": "POST",
  "path": "/v1/databases/{database_id}/query",
  "body": {
    "filter": {
      "property": "Status",
      "select": {"equals": "In Progress"}
    },
    "sorts": [
      {"property": "Created", "direction": "descending"}
    ],
    "page_size": 50
  }
}
```

#### 3. Create a New Page
```json
{
  "method": "POST",
  "path": "/v1/pages",
  "body": {
    "parent": {"database_id": "{database_id}"},
    "properties": {
      "title": {
        "title": [{"text": {"content": "New Page Title"}}]
      },
      "Status": {
        "select": {"name": "Not Started"}
      }
    }
  }
}
```

#### 4. Update Page Properties
```json
{
  "method": "PATCH",
  "path": "/v1/pages/{page_id}",
  "body": {
    "properties": {
      "Status": {"select": {"name": "Completed"}},
      "Last Updated": {"date": {"start": "2024-01-15"}}
    }
  }
}
```

#### 5. Append Blocks to a Page
```json
{
  "method": "PATCH",
  "path": "/v1/blocks/{page_id}/children",
  "body": {
    "children": [
      {
        "paragraph": {
          "rich_text": [{"text": {"content": "New paragraph content"}}]
        }
      },
      {
        "heading_2": {
          "rich_text": [{"text": {"content": "Section Header"}}]
        }
      }
    ]
  }
}
```

#### 6. Search Across Workspace
```json
{
  "method": "POST",
  "path": "/v1/search",
  "body": {
    "query": "project planning",
    "filter": {"property": "object", "value": "page"},
    "page_size": 10
  }
}
```

### Property Types and Formats

Notion supports various property types. Here are the common formats:

#### Text Properties
```json
{
  "title": {"title": [{"text": {"content": "Page Title"}}]},
  "rich_text": {"rich_text": [{"text": {"content": "Rich text content"}}]}
}
```

#### Select and Multi-select
```json
{
  "status": {"select": {"name": "In Progress"}},
  "tags": {"multi_select": [{"name": "urgent"}, {"name": "feature"}]}
}
```

#### Numbers and Dates
```json
{
  "price": {"number": 29.99},
  "due_date": {"date": {"start": "2024-01-15"}},
  "date_range": {"date": {"start": "2024-01-15", "end": "2024-01-20"}}
}
```

#### Relations and People
```json
{
  "related_page": {"relation": [{"id": "{page_id}"}]},
  "assignee": {"people": [{"id": "{user_id}"}]}
}
```

### Filtering and Sorting

#### Filter Examples
```json
{
  "filter": {
    "and": [
      {"property": "Status", "select": {"equals": "In Progress"}},
      {"property": "Priority", "number": {"greater_than": 5}}
    ]
  }
}
```

#### Sort Examples
```json
{
  "sorts": [
    {"property": "Created", "direction": "descending"},
    {"property": "Title", "direction": "ascending"}
  ]
}
```

### Pagination

Notion APIs use cursor-based pagination:

```json
{
  "method": "POST",
  "path": "/v1/databases/{database_id}/query",
  "body": {
    "page_size": 100,
    "start_cursor": "{cursor_from_previous_response}"
  }
}
```

### Error Handling

The tool returns Notion's error responses directly. Common error patterns:

- `400`: Invalid request (check property names, types, formats)
- `401`: Invalid or missing authentication
- `403`: Insufficient permissions
- `404`: Page, database, or block not found
- `429`: Rate limit exceeded

### Best Practices for LLMs

1. **Always check the response**: Examine `status_code` for success/error
2. **Use proper UUIDs**: Page and database IDs should be valid UUIDs
3. **Respect property schemas**: Query database schema first to understand property types
4. **Handle pagination**: Check for `next_cursor` in responses for multi-page results
5. **Use appropriate methods**: GET for retrieval, POST for creation/queries, PATCH for updates
6. **Include request IDs**: Use `notion_request_id` for debugging issues

### API Version
This tool uses Notion API version `2024-05-01`, the latest stable version.

## Getting Started
1. Provide your Notion integration token via environment variable or a `.env` file (auto-loaded on startup):
   ```bash
   echo 'NOTION_API_TOKEN=secret_token_from_notion' > .env
   echo 'NOTION_API_VERSION=2024-05-01' >> .env  # optional override (defaults to latest)
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
- The enhanced OpenAPI schema now provides comprehensive examples and guidance for effective Notion API usage.

## Next Steps
- Add authentication or IP restrictions before exposing the proxy publicly.
- Log or restrict the forwarded methods/paths if you need finer-grained control.
- Replace placeholder contact/legal URLs in the manifest with your own details.

## MCP Connector
- Launch the SSE server with `zagori-tools-mcp` (set `FASTMCP_HOST`/`FASTMCP_PORT` as needed).
- Deploy it on HTTPS and point ChatGPT's connector URL at `https://<your-host>/sse/`.
- The connector exposes a single tool `notion_request` that mirrors the REST proxy parameters (`method`, `path`, `params`, `body`).
- Responses include `status_code`, `data`, and `notion_request_id`, matching the Action server behavior.

