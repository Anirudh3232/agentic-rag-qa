# Retrieval-Augmented Generation

Retrieval-Augmented Generation (RAG) combines a retriever that fetches relevant documents with a language model that generates an answer conditioned on those documents. This approach grounds the model's output in factual source material, reducing hallucinations.

## How RAG Works

1. A user submits a question.
2. The retriever searches a vector index for chunks whose embeddings are closest to the question embedding.
3. The top-k chunks are concatenated into a context window.
4. The language model generates an answer using the question and the retrieved context.

## Advantages

- Grounded answers with traceable sources.
- No need to fine-tune the model on every domain update — just re-index the corpus.
- Works with any embedding model and any generative model.

## Limitations

- Answer quality depends on retrieval quality — if the right chunk is not retrieved, the answer will be wrong or fabricated.
- Chunk size and overlap strategy affect recall.
- Embedding models may not capture domain-specific semantics without fine-tuning.
