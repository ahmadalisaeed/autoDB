
## Quickstart

### Before starting
Create `.env` file and add
```
OPENAI_API_KEY=[YOUR OPEN API KEY]

```


```bash
# 1) Docker
docker build -t autodb .
docker run -p 8000:8000 -v $PWD/data:/data \
  -e AUTODB_CHROMA_DIR=/data/chroma \
  -e AUTODB_SQLITE_URL=sqlite:////data/autodb.sqlite \
  autodb

# or with docker-compose
docker-compose up --build
```

Visit docs: http://localhost:8000/docs

## Endpoints

### POST /save (multipart/form-data)
- **file**: CSV/JSON/TXT file
- **text**: plain text string (alternative to file)
- **json_payload**: stringified JSON (alternative to file)
- **filename**: optional name override

Responses:
```json
{ "message": "CSV stored", "doc_id": "<uuid>", "chunks": 123 }
```

### GET /search?q=...
Returns semantic matches 

```json
{
  "answer": "Based on the stored data, last year ...",
  "sources": ["movies_2024.csv", "movies.csv"],
  "matches": [ {"id": "...", "text": "year: 2024 | name: ABC", ...} ]
}
```

## Example

Upload two CSVs:

```bash
curl -F "file=@movies_2024.csv" http://localhost:8000/save
curl -F "file=@people_2025.csv" http://localhost:8000/save
```

Ask a question:

```bash
curl "http://localhost:8000/search?q=Which movies release last year?"
```

## Notes
- Embeddings done with `sentence-transformers (all-MiniLM-L6-v2)` and stored in persistent Chroma.
- Structured rows are preserved as JSON strings inside match metadata for optional downstream logic.