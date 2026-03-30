def generate_answer(query, context):

    prompt = f"""
You are a banking operations assistant.

Use the SOP context below to answer the user query.

Context:
{context}

User Question:
{query}

Answer:
"""

    # Temporary simple response (until we connect real LLM)
    answer = f"Based on SOP documents:\n\n{context[:500]}"

    return answer