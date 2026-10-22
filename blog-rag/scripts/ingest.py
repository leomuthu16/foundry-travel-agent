"""Ingest blog posts into Azure AI Search, the way the platform's refresh functions would.

    python scripts/ingest.py --full          # (re)load every post; removes chunks of deleted posts
    python scripts/ingest.py --incremental   # only new or changed posts since the last run

Each post is split into chunks by its '##' headings. Every chunk gets an embedding and
carries the post's title, URL and publish date, so the agent can cite the exact post
and prefer recent content. Every chunk also stores a hash of its post, so an incremental
run can tell which posts changed by asking the index itself (no local state file), which
is what lets the same script run from a scheduled pipeline.
"""
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from common import ROOT, openai_client, load_config, need, search_credential

POSTS_DIR = ROOT / "content" / "posts"


# ---------- reading and chunking ----------

def read_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        sys.exit(f"{path.name}: missing the --- front matter block")
    meta = dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)
    meta["body"] = match.group(2).strip()
    meta["hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return meta


def chunk_post(post: dict) -> list[dict]:
    """One chunk for the introduction, then one per '## ' section."""
    parts = re.split(r"^## (.+)$", post["body"], flags=re.M)
    sections = [("Overview", parts[0].strip())] + [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]
    chunks = []
    for i, (heading, text) in enumerate(sections):
        if not text:
            continue
        # Contextual chunk header: the agent's search tool may pass only the chunk text and title to the
        # model, so the URL and date travel inside the text too. It also helps retrieval, because a
        # section like "Pipelines" now carries the release it belongs to.
        header = f"Post: {post['title']} | Published: {post['publish_date']} | URL: {post['url']} | Section: {heading}"
        chunks.append({
            "id": f"{post['id']}--{i}",
            "post_id": post["id"],
            "title": post["title"],
            "url": post["url"],
            "publish_date": f"{post['publish_date']}T00:00:00Z",
            "heading": heading,
            "content": f"{header}\n{text}",
            "content_hash": post["hash"],
        })
    return chunks


# ---------- index ----------

def build_index(cfg: dict) -> SearchIndex:
    vectorizer = AzureOpenAIVectorizer(
        vectorizer_name="openai-vectorizer",
        parameters=AzureOpenAIVectorizerParameters(
            resource_url=need("AZURE_OPENAI_ENDPOINT"),
            deployment_name=cfg["embedding_deployment"],
            model_name=cfg["embedding_model"],
            # Free tier can't use a managed identity for outbound calls, so the vectorizer uses a key.
            # On Basic or higher, use the search service's managed identity instead.
            api_key=os.getenv("FOUNDRY_RESOURCE_KEY") or None,
        ),
    )
    return SearchIndex(
        name=cfg["index_name"],
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="post_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SimpleField(name="url", type=SearchFieldDataType.String),
            SimpleField(name="publish_date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SearchableField(name="heading", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="content_hash", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=cfg["embedding_dimensions"],
                vector_search_profile_name="vector-profile",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vector-profile", algorithm_configuration_name="hnsw", vectorizer_name="openai-vectorizer")],
            vectorizers=[vectorizer],
        ),
        semantic_search=SemanticSearch(
            default_configuration_name="default",
            configurations=[SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="heading")],
                ),
            )],
        ),
    )


# ---------- main ----------

def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--full", action="store_true", help="reload all posts and remove deleted ones")
    mode.add_argument("--incremental", action="store_true", help="only new or changed posts")
    parser.add_argument("--recreate", action="store_true", help="delete and recreate the index first")
    args = parser.parse_args()

    cfg = load_config()
    endpoint, credential = need("SEARCH_ENDPOINT"), search_credential()
    index_client = SearchIndexClient(endpoint, credential)
    existing = {name for name in index_client.list_index_names()}
    if args.recreate and cfg["index_name"] in existing:
        index_client.delete_index(cfg["index_name"])
        existing.discard(cfg["index_name"])
    if cfg["index_name"] not in existing:
        index = build_index(cfg)
        try:
            index_client.create_index(index)
        except Exception as error:
            if "semantic" not in str(error).lower():
                raise
            # Semantic ranker is switched off on this search service: create the index without it.
            index.semantic_search = None
            index_client.create_index(index)
            print("Note: semantic ranker is not enabled on this service; index created without it.")
        print(f"Created index '{cfg['index_name']}'")
    search = SearchClient(endpoint, cfg["index_name"], credential)

    posts = [read_post(p) for p in sorted(POSTS_DIR.glob("*.md"))]
    # What the index already holds: post id -> hash of the version that was indexed.
    indexed = {d["post_id"]: d.get("content_hash") for d in search.search(search_text="*", select=["post_id", "content_hash"], top=1000)}
    changed = posts if args.full else [p for p in posts if indexed.get(p["id"]) != p["hash"]]
    print(f"{len(posts)} posts found, {len(changed)} to (re)index ({'full' if args.full else 'incremental'} refresh)")

    chunks = [c for p in changed for c in chunk_post(p)]
    if chunks:
        client = openai_client()
        texts = [c["content"] for c in chunks]  # the header already holds title, date and section
        vectors = client.embeddings.create(model=cfg["embedding_deployment"], input=texts).data
        for chunk, vec in zip(chunks, vectors):
            chunk["content_vector"] = vec.embedding
        for post in changed:  # remove the post's old chunks first, in case it lost a section
            old = list(search.search(search_text="*", filter=f"post_id eq '{post['id']}'", select=["id"]))
            if old:
                search.delete_documents([{"id": d["id"]} for d in old])
        result = search.upload_documents(chunks)
        print(f"Uploaded {sum(1 for r in result if r.succeeded)}/{len(chunks)} chunks")

    if args.full:  # deletions: remove chunks of posts that no longer exist
        current = {p["id"] for p in posts}
        for gone in sorted(set(indexed) - current):
            old = list(search.search(search_text="*", filter=f"post_id eq '{gone}'", select=["id"]))
            search.delete_documents([{"id": d["id"]} for d in old])
            print(f"Removed {len(old)} chunks of deleted post '{gone}'")

    print("Done.")


if __name__ == "__main__":
    main()
