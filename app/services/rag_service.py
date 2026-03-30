from app.ml.embeddings import generate_embedding
from app.ml.vector_store import search_vector


def retrieve_context(query, bank_id):

    query_embedding = generate_embedding(query)

    results = search_vector(query_embedding, bank_id, top_k=3)

    context_blocks = []
    reference_files = []

    for r in results:

        text = ""
        file_name = ""

        # result is (similarity, doc)
        if isinstance(r, tuple) and len(r) == 2:

            similarity, doc = r

            if isinstance(doc, dict):
                text = doc.get("text", "")
                file_name = doc.get("fileName", "")

        # fallback
        elif isinstance(r, dict):

            text = r.get("text", "")
            file_name = r.get("fileName", "")

        if text:
            context_blocks.append(text)

        if file_name:
            reference_files.append(file_name)

    context = "\n".join(context_blocks)

    return context, reference_files