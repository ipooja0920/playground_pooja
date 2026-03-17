import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def get_answer(question: str, context_chunks: list[str]) -> str:
    """
    Send the user's question and retrieved context chunks to GPT-4o.
    Returns the model's answer as a string.
    Raises RuntimeError on API failure.
    """
    context = "\n\n---\n\n".join(context_chunks)

    system_prompt = (
        "You are a helpful assistant that answers questions strictly based on the "
        "provided document context. Do not use any outside knowledge. "
        "Every statement in your answer must be directly supported by the provided context. "
        "Cover all key points from the context that are relevant to the question — "
        "do not leave out important details. "
        "If the answer cannot be found in the context, say so clearly."
    )

    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        response = _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e
