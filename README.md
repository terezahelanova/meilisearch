# Meilisearch

Meilisearch instance for testing purposes

## Run Meilisearch locally

```
docker run -d -p 7700:7700 -e MEILI_MASTER_KEY=<master_key> getmeili/meilisearch:latest
```

## Upload test data

```
python3 ./upload_data.py
```
