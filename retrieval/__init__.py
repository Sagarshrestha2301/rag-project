"""Step 5 retrieval: hybrid (BM25 + dense, RRF) over chunks.

`ui/retrieval.py` keeps the page-level BM25 baseline the eval set was measured on;
this package is the chunk-level retriever the UI is moving to.
"""
