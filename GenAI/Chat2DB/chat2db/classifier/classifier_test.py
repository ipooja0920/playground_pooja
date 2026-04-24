"""
Classifier Test - Standalone script to test the intent classifier.

Loads the pre-trained classifier from combined_sql_classifier.pkl
and classifies sample prompts.

Usage:
  python classifier_test.py
"""

import pickle
from pathlib import Path


def load_classifier():
    """Load the classifier model from pickle file."""
    model_path = Path(__file__).parent / "combined_sql_classifier.pkl"
    if not model_path.exists():
        print(f"Error: Classifier model not found at {model_path}")
        print("Run 'python train_classifier.py' first to generate the model.")
        return None

    with open(model_path, "rb") as f:
        return pickle.load(f)


def classify(classifier, prompt):
    """Classify a single prompt."""
    vectorizer = classifier["vectorizer"]
    binary_classifier = classifier["binary_classifier"]

    prompt_tfidf = vectorizer.transform([prompt])
    is_sql = binary_classifier.predict(prompt_tfidf)[0]

    print(f"\nPrompt: '{prompt}'")

    if is_sql == 0:
        print("  → Classification: Non-SQL Query")
        return False

    # Get detailed classification
    domain = classifier["label_encoder_domain"].inverse_transform(
        [classifier["classifier_domain"].predict(prompt_tfidf)[0]]
    )[0]
    complexity = classifier["label_encoder_complexity"].inverse_transform(
        [classifier["classifier_complexity"].predict(prompt_tfidf)[0]]
    )[0]
    task_type = classifier["label_encoder_task_type"].inverse_transform(
        [classifier["classifier_task_type"].predict(prompt_tfidf)[0]]
    )[0]

    print(f"  → Classification: SQL Query")
    print(f"    Domain: {domain}")
    print(f"    Complexity: {complexity}")
    print(f"    Task Type: {task_type}")
    return True


def main():
    """Test the classifier with sample prompts."""
    classifier = load_classifier()
    if classifier is None:
        return

    print("=" * 60)
    print("Intent Classifier Test")
    print("=" * 60)

    # SQL queries (should be classified as SQL)
    sql_prompts = [
        "What is the track with the most revenue?",
        "How many customers are from Canada?",
        "Show me the top selling genres",
        "List all albums by Metallica",
        "What is the total revenue by country?",
    ]

    # Non-SQL queries (should be classified as Non-SQL)
    non_sql_prompts = [
        "What is the weather today?",
        "Tell me a joke",
        "How do I cook risotto?",
        "What is the meaning of life?",
        "Can you translate this to French?",
    ]

    print("\n--- SQL Queries (Expected: SQL) ---")
    for prompt in sql_prompts:
        classify(classifier, prompt)

    print("\n--- Non-SQL Queries (Expected: Non-SQL) ---")
    for prompt in non_sql_prompts:
        classify(classifier, prompt)


if __name__ == "__main__":
    main()
