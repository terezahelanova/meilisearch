import os
import json
import sys
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

MEILI_HOST = os.getenv("MEILI_HOST", "http://127.0.0.1:7700")
MEILI_KEY = os.getenv("MEILI_KEY", "devkey")
INDEX_NAME = os.getenv("MEILI_INDEX", "docs")

def process_args() -> str:
    match len(sys.argv):
        case 1:
            return Path("./docs").resolve()
        case 2:
            arg = sys.argv[1]
            path = Path(arg).resolve()

            if path.exists():
                return path
            print("Specified folder does not exist: ", arg)
            sys.exit(1)            
        case _:
            print("Too many arguments.")
            sys.exit(1)            

def create_id(path: Path, source_dir: str) -> str:
    relativePath = path.relative_to(source_dir).as_posix()
    return hashlib.sha1(relativePath.encode("utf8")).hexdigest()

def http_request(method, url, body=None):
    headers = {
        "Authorization": f"Bearer {MEILI_KEY}",
        "Content-Type": "application/json",
    }
    data = None if body is None else json.dumps(body).encode("utf8")
    req = urllib.request.Request(url, data, headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            if res.status in (200, 201, 202):
                content = res.read()
                return json.loads(content.decode("utf8")) if content else None
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        print(f"Request failed: {error}")
        sys.exit(1)   
    return None

def update_index_settings():
    http_request(
        "PATCH",
        f"{MEILI_HOST}/indexes/{INDEX_NAME}/settings",
        {"filterableAttributes": ["scope"]},
    )

def build_docs(source_dir: str):
    docs = []

    for path in source_dir.rglob("*.md"):
        relativePath = path.relative_to(source_dir).as_posix()   
        folders = relativePath.split("/")

        # To be modified
        scope = folders[-2] if len(folders) > 1 else "none"

        with open(path, "r", encoding="utf8") as file:
            content = file.read().strip()

        if not content:
            continue

        docs.append({
            "id": create_id(path, source_dir),
            "url": "/",
            "content": content,
            "scope": scope,
            "title": folders[-1]
        })

    return docs

def upload(source_dir: str):
    docs = build_docs(source_dir)
    if len(docs) == 0:
        print("No documentation to be uploaded")
        return
    print(f"Uploading {len(docs)} documents to index '{INDEX_NAME}'")
    http_request(
        "POST",
        f"{MEILI_HOST}/indexes/{INDEX_NAME}/documents",
        docs,
    )

if __name__ == "__main__":
    source_dir = process_args()
    update_index_settings()
    upload(source_dir)

