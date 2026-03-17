"""
RAGAS evaluation script for the RAG pipeline.

Prerequisites:
  1. Index your PDFs first by running the Streamlit app and uploading documents.
  2. Fill in TEST_CASES below with real questions and reference answers
     drawn from those same PDFs.
  3. Make sure your .env has a valid OPENAI_API_KEY with credits.

Run:
  python eval.py
"""

import os
from dotenv import load_dotenv

from ragas import evaluate, EvaluationDataset
from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextRecall, FactualCorrectness
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI

from vector_db import get_embed_model, get_qdrant_client, retrieve
from llm_client import get_answer

load_dotenv()


# ── TEST CASES ───────────────────────────────────────────────────────────────
# Fill these in based on the PDFs you indexed.
# - question : what you'd type into the chat
# - reference: the correct answer you'd expect (used to score Context Recall
#              and Factual Correctness)
#
# Example (replace with real Q&A from your documents):
TEST_CASES = [
    {
        "question": "What is the main topic of the document?",
        "reference": "Replace with the correct answer from your PDF.",
    },
    {
        "question": "What are the key conclusions or findings?",
        "reference": "Replace with the correct answer from your PDF.",
    },
    {
        "question": "What methodology or approach was used?",
        "reference": "Replace with the correct answer from your PDF.",
    },
]
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("Loading embedding model and Qdrant client...")
    embed_model = get_embed_model()
    qdrant_client = get_qdrant_client()

    samples = []
    print(f"\nRunning {len(TEST_CASES)} test cases through the RAG pipeline...\n")

    for i, case in enumerate(TEST_CASES, 1):
        question = case["question"]
        reference = case["reference"]

        print(f"[{i}/{len(TEST_CASES)}] Q: {question}")

        # Step 1 — retrieve relevant chunks from Qdrant
        hits = retrieve(question, embed_model, qdrant_client)
        retrieved_contexts = [text for text, _, _ in hits]

        if not retrieved_contexts:
            print("  ↳ No chunks retrieved — make sure PDFs are indexed first.\n")
            continue

        # Step 2 — generate answer with GPT-4o
        try:
            response = get_answer(question, retrieved_contexts)
        except RuntimeError as e:
            print(f"  ↳ LLM error: {e}\n")
            continue

        print(f"  ↳ Answer: {response[:100]}{'...' if len(response) > 100 else ''}\n")

        samples.append({
            "user_input": question,
            "retrieved_contexts": retrieved_contexts,
            "response": response,
            "reference": reference,
        })

    if not samples:
        print(
            "\nNo samples collected. Check that:\n"
            "  • PDFs are indexed (run the Streamlit app first)\n"
            "  • Your OpenAI API key has credits\n"
        )
        return

    print(f"Evaluating {len(samples)} sample(s) with RAGAS...\n")

    dataset = EvaluationDataset.from_list(samples)

    # RAGAS uses gpt-4o-mini as its judge LLM (cheaper than gpt-4o)
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
    )

    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),        # answer is grounded in retrieved context
            ResponseRelevancy(),   # answer addresses the question asked
            LLMContextRecall(),    # retrieved chunks contain the right info
            FactualCorrectness(),  # answer matches the reference answer
        ],
        llm=evaluator_llm,
    )

    print("\n── RAGAS Evaluation Results ───────────────────────────────────────")
    print(result)
    print("\nPer-sample breakdown:")
    print(result.to_pandas().to_string(index=False))
    print("───────────────────────────────────────────────────────────────────")
    print("\nScore guide: 0.0 (worst) → 1.0 (best)")
    print("  Faithfulness      : answer only uses info from retrieved chunks")
    print("  Response Relevancy: answer actually addresses the question")
    print("  Context Recall    : retrieved chunks contain the correct answer")
    print("  Factual Correctness: answer matches your reference answer")


if __name__ == "__main__":
    main()
