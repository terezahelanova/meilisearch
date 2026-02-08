import os
import json
import sys
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
import markdown
from bs4 import BeautifulSoup

MEILI_HOST = os.getenv("MEILI_HOST", "http://127.0.0.1:7700")
MEILI_KEY = os.getenv("MEILI_KEY", "devkey")
INDEX_NAME = os.getenv("MEILI_INDEX", "docs")

def remove_html_elemets(markdown_text):
    html = markdown.markdown(markdown_text)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()

def format_md_with_fumadocs(content):
    try:
        # To be changed
        url = 'http://localhost:3000/api/toc'

        data = json.dumps({'payload': content}).encode('utf-8')
        request = urllib.request.Request(url, data=data)
        request.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
            else:
                print(f"API request failed with status {response.status}")
                sys.exit(1)

    except Exception as e:
        print(f"Failed to get document structure from API: {e}")
        sys.exit(1)


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

def create_id(path: Path, source_dir: str, anchor: str | None = None) -> str:
    relativePath = path.relative_to(source_dir).as_posix()
    base = relativePath
    if anchor:
        base = f"{relativePath}-{anchor}"
    return hashlib.sha1(base.encode("utf8")).hexdigest()

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

def update_index_settings():
    http_request(
        "PATCH",
        f"{MEILI_HOST}/indexes/{INDEX_NAME}/settings",
        {
            "filterableAttributes": ["scope"],
            "searchableAttributes": ["heading", "content", "pageTitle"]
        } 
    )

def merge_content_by_headings(contents):
    merged_result = []
    heading_groups = {}
    no_heading_content = []
    
    for item in contents:
        content = item.get('content', '')

        if "heading" not in item:
            if len(no_heading_content) > 0:
                no_heading_content.append("\n")
            no_heading_content.append(remove_html_elemets(content))
            continue

        heading = item.get('heading')
        if heading not in heading_groups:
            heading_groups[heading] = []
        else:
            heading_groups[heading].append("\n")
        heading_groups[heading].append(remove_html_elemets(content))

    if no_heading_content:
        merged_result.append({
            'heading': None,  
            'content': "".join(no_heading_content)
        })
    
    for heading, contents in heading_groups.items():
        merged_result.append({
            'heading': heading,  
            'content': "".join(contents)  
        })
    
    return merged_result

def create_documents_per_file(content: str, scope: str, path: Path, source_dir: str):
    documents = []
    response = format_md_with_fumadocs(content)
    structured_data = response["structure"]
    page_title = response["title"]
    page_key = response["key"]

    contents = merge_content_by_headings(structured_data["contents"])
    headings = structured_data["headings"]

    heading_counter = 0

    for item in contents:
        heading_id = item["heading"]
        heading = ""
        anchor = "/" + page_key

        if heading_id is not None:
            heading = headings[heading_counter]["content"]
            anchor = "/" + page_key + "#" + heading_id
            heading_counter += 1
    
        documents.append({
            "id": create_id(path, source_dir, anchor),
            "url": anchor,
            "content": item["content"],
            "scope": scope,
            "heading": heading,
            "pageTitle": page_title
        })

    return documents

def build_docs(source_dir: str):
    final_documents = []

    for path in source_dir.rglob("*.md"):
        relativePath = path.relative_to(source_dir).as_posix()   
        folders = relativePath.split("/")

        # To be modified
        scope = folders[-2] if len(folders) > 1 else "none"

        with open(path, "r", encoding="utf8") as file:
            content = file.read().strip()

        if not content:
            continue

        documents_per_file = create_documents_per_file(content, scope, path, source_dir)
        final_documents.extend(documents_per_file)

    return final_documents

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

