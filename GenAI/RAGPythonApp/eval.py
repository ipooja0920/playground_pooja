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
        "question": "Can you name four of the main challenges in machine learning?",
        "reference": "Some of the main challenges in Machine Learning are the lack of data, poor data quality, nonrepresentative data, uninformative features, excessively simple models that underfit the training data, and excessively complex models that overfit the data.",
    },
    {
        "question": "What is out-of-core learning?",
        "reference": "Out-of-core algorithms can handle vast quantities of data that cannot fit in a computer's main memory. An out-of-core learning algorithm chops the data into mini-batches and uses online learning techniques to learn from these mini-batches",
    },
    {
        "question": "What is the train-dev set, when do you need it, and how do you use it?",
        "reference": "The train-dev set is used when there is a risk of mismatch between the training data and the data used in the validation and test datasets (which should always be as close as possible to the data used once the model is in production). The train-dev set is a part of the training set that's held out (the model is not trained on it). The model is trained on the rest of the training set, and evaluated on both the train-dev set and the validation set. If the model performs well on the training set but not on the train-dev set, then the model is likely overfitting the training set. If it performs well on both the training set and the train-dev set, but not on the validation set, then there is probably a significant data mismatch between the training data and the validation + test data, and you should try to improve the training data to make it look more like the validation + test data.",
    },
    {
        "question": "Suppose you want to classify pictures as outdoor/indoor and daytime/nighttime. Should you implement two logistic regression classifiers or one softmax regression classifier?",
        "reference": "If you want to classify pictures as outdoor/indoor and daytime/nighttime, since these are not exclusive classes (i.e., all four combinations are possible) you should train two Logistic Regression classifiers.",
    },
    {
        "question": "Why would you want to use:Ridge regression instead of plain linear regression (i.e., without any regularization)?",
        "reference": "A model with some regularization typically performs better than a model without any regularization, so you should generally prefer Ridge Regression over plain Linear Regression.",
    },
    {
        "question": "How can you choose between LinearSVC, SVC, and SGDClassifier?",
        "reference": "All three classes can be used for large-margin linear classification. The SVC class also supports the kernel trick, which makes it capable of handling nonlinear tasks. However, this comes at a cost: the SVC class does not scale well to datasets with many instances. It does scale well to a large number of features, though. The LinearSVC class implements an optimized algorithm for linear SVMs, while SGDClassifier uses Stochastic Gradient Descent. Depending on the dataset LinearSVC may be a bit faster than SGDClassifier, but not always, and SGDClassifier is more flexible, plus it supports incremental learning.",
    },
    {
        "question": "When would you want to use:SVC instead of LinearSVC?",
        "reference": "SVC can handle nonlinear classification tasks using the kernel trick, while LinearSVC can only handle linear classification tasks.",
    },
    {
        "question": "What is the approximate depth of a decision tree trained (without restrictions) on a training set with one million instances?",
        "reference": "The depth of a well-balanced binary tree containing m leaves is equal to log₂(m), rounded up. log₂ is the binary log; log₂(m) = log(m) / log(2). A binary Decision Tree (one that makes only binary decisions, as is the case with all trees in Scikit-Learn) will end up more or less well balanced at the end of training, with one leaf per training instance if it is trained without restrictions. Thus, if the training set contains one million instances, the Decision Tree will have a depth of log₂(106) ≈ 20 (actually a bit more since the tree will generally not be perfectly well balanced).",
    }
]
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("Loading embedding model and Qdrant client...")
    embed_model = get_embed_model()
    try:
        qdrant_client = get_qdrant_client()
    except Exception as e:
        if "already accessed" in str(e):
            print(
                "\nERROR: Qdrant storage is locked by another process (likely the Streamlit app).\n"
                "Stop the Streamlit app first (Ctrl+C in its terminal), then re-run:\n"
                "  python eval.py\n"
            )
        else:
            print(f"\nERROR: Could not connect to Qdrant: {e}\n")
        return

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
