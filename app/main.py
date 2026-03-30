from fastapi import FastAPI

from app.api import fraud
from app.ml.vector_store import rebuild_vector_index, load_sbi_documents

app = FastAPI(title="SBI Fraud Investigation Assistant")


@app.on_event("startup")
def startup_event():
    """
    Startup steps:
    1. Load existing SBI vectors from MongoDB into memory + FAISS
    2. Index only new SBI PDFs that are not already in MongoDB
    """
    print("Starting up system...")

    rebuild_vector_index()
    load_sbi_documents()
    print("System ready. SBI vector index built and SBI PDFs indexed if any.")


# Include routers
app.include_router(fraud.router)


@app.get("/")
def home():
    return {"message": "SBI Fraud Investigation Assistant running"}
