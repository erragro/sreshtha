"""Retrieval-augmented generation over the ``embeddings`` table.

Two consumers today:
- Stage 2 (annotate) retrieves statute chunks per clause batch before
  gpt-4o writes the citation.
- Ingestion scripts populate the corpus once per statute update.

Public surface:
- ``embedder.embed(texts, model=…, dimensions=…)`` — batch-embeds
  strings via OpenAI's ``text-embedding-3-large`` at 1024 dims by
  default. Matches the ``vector(1024)`` column shape from migration
  013.
- ``retriever.retrieve_context(query, source_type, k, threshold,
  tenant_id)`` — top-k similarity search with a cosine threshold
  filter; returns chunks + metadata + similarity scores.
- ``chunker.chunk_statute_markdown(text, source_id, metadata)`` —
  section-boundary-aware chunker for legal text.
"""
