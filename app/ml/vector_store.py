import os
import re

import faiss
import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.core.config import SBI_BANK_DIR, SBI_BANK_ID
from app.db.mongodb import documents_collection, fs


model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

vector_dimension = 384
index = faiss.IndexFlatL2(vector_dimension)
vector_store = []


def generate_embedding(text):
    return model.encode(text)


def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"

    return text


def split_by_category(text):
    pattern = r"([A-Z]{1,3}-\d{2}[\s\S]*?)(?=[A-Z]{1,3}-\d{2}|$)"
    matches = re.findall(pattern, text)
    return [match.strip() for match in matches if match.strip()]


def store_pdf(file_path, bank_id=SBI_BANK_ID):
    file_name = os.path.basename(file_path)

    existing = documents_collection.find_one({
        "bankId": bank_id,
        "fileName": file_name,
        "isPDF": True
    })

    if existing and "fileId" in existing:
        return existing["fileId"]

    with open(file_path, "rb") as file_obj:
        file_id = fs.put(
            file_obj,
            filename=file_name,
            bankId=bank_id
        )

    documents_collection.update_one(
        {
            "bankId": bank_id,
            "fileName": file_name
        },
        {
            "$set": {
                "bankId": bank_id,
                "fileName": file_name,
                "fileId": str(file_id),
                "filePath": file_path,
                "isPDF": True
            }
        },
        upsert=True
    )

    print(f"Stored PDF in MongoDB: {file_name}")

    return str(file_id)


def add_vector(embedding, text, bank_id, file_name, file_id, source_file=None):
    vector_np = np.array([embedding]).astype("float32")

    exists = documents_collection.find_one({
        "bankId": bank_id,
        "fileName": file_name,
        "text": text
    })

    if exists:
        print(f"Skipping duplicate chunk for {file_name}")
        return

    index.add(vector_np)

    doc = {
        "bankId": bank_id,
        "fileName": file_name,
        "text": text,
        "embedding": embedding.tolist(),
        "fileId": file_id,
        "sourceFile": source_file or file_name
    }

    vector_store.append(doc)
    documents_collection.insert_one(doc)


def rebuild_vector_index():
    global vector_store

    print("Rebuilding FAISS index from MongoDB...")

    vector_store = []
    index.reset()

    docs = list(documents_collection.find({
        "bankId": SBI_BANK_ID,
        "embedding": {"$exists": True}
    }))

    for doc in docs:
        embedding = np.array(doc["embedding"]).astype("float32")
        index.add(np.array([embedding]))
        vector_store.append(doc)

    print(f"Loaded {len(vector_store)} SBI vectors from MongoDB")


def load_sbi_documents():
    if not os.path.exists(SBI_BANK_DIR):
        print("SBI folder not found")
        return

    for file_name in os.listdir(SBI_BANK_DIR):
        if not file_name.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(SBI_BANK_DIR, file_name)
        print(f"Checking SBI document: {file_name}")

        file_id = store_pdf(file_path, SBI_BANK_ID)

        exists = documents_collection.find_one({
            "bankId": SBI_BANK_ID,
            "$or": [
                {"sourceFile": file_name},
                {"fileName": {"$regex": f"^{re.escape(file_name)}_block"}}
            ],
            "embedding": {"$exists": True}
        })

        if exists:
            print(f"Skipping already indexed file: {file_name}")
            continue

        try:
            text = extract_text_from_pdf(file_path)

            if not text.strip():
                print(f"Skipped empty PDF: {file_name}")
                continue

            blocks = split_by_category(text) or [text]

            for index_number, block in enumerate(blocks, start=1):
                embedding = generate_embedding(block)
                block_file_name = f"{file_name}_block{index_number}"

                add_vector(
                    embedding,
                    block,
                    SBI_BANK_ID,
                    block_file_name,
                    file_id,
                    source_file=file_name
                )

            print(f"Indexed {len(blocks)} blocks from {file_name}")

        except Exception as exc:
            print(f"Error processing {file_name}: {exc}")


def search_vector(query_embedding, bank_id, top_k=3):
    results = []

    for doc in vector_store:
        if doc["bankId"] != bank_id:
            continue

        similarity = np.dot(query_embedding, doc["embedding"]) / (
            np.linalg.norm(query_embedding) *
            np.linalg.norm(doc["embedding"])
        )

        results.append((similarity, doc))

    results.sort(reverse=True)

    return results[:top_k]
