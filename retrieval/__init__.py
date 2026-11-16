"""Step 5 retrieval: hybrid (BM25 + dense, RRF) over chunks.

`corpus.py` keeps the page-level BM25 baseline the eval set was measured on and owns
every page lookup; this package is the chunk-level retriever the UI is moving to.
"""
