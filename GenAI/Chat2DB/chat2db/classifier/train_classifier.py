"""
Intent Classifier - Trains a TF-IDF + SVM classifier to distinguish
SQL-related queries from non-SQL queries, with multi-label classification
for domain, complexity, and task type.

Produces: combined_sql_classifier.pkl

Datasets used:
  - GretelAI Synthetic Text-to-SQL (HuggingFace)
  - Factoid WebQuestions (GitHub)

Usage:
  python train_classifier.py
"""

import pickle
import numpy as np
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC, LinearSVC
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score


def create_training_data():
    """Create a training dataset for SQL vs Non-SQL classification.
    
    In production, this would load from GretelAI and WebQuestions datasets.
    Here we provide a representative sample for bootstrapping.
    """

    # SQL-related queries (label = 1)
    sql_queries = [
        # Simple SELECT queries
        "What is the total revenue?",
        "Show me all customers",
        "How many tracks are in the database?",
        "List all albums by AC/DC",
        "What is the most expensive track?",
        "Show the top 10 selling artists",
        "How many invoices were created in 2009?",
        "What is the average invoice total?",
        "Which genre has the most tracks?",
        "List all employees and their titles",
        "What tracks are in the Rock genre?",
        "Show all playlists",
        "How many customers are from Brazil?",
        "What is the total number of albums?",
        "Which artist has the most albums?",
        "Show me the tracks longer than 5 minutes",
        "What is the cheapest track?",
        "List all genres",
        "How many media types are there?",
        "What is the most popular playlist?",
        "Show sales by country",
        "What is the revenue per genre?",
        "Which employee has the most customers?",
        "Show the invoice details for customer 1",
        "What tracks were purchased by customer 5?",
        "How many tracks does each album have?",
        "What is the longest track in the database?",
        "Show me all tracks by Led Zeppelin",
        "What is the total revenue for 2010?",
        "Which country has the most customers?",
        "List the top 5 customers by spending",
        "What is the average track length?",
        "Show all tracks in the Jazz genre",
        "How many invoices does each customer have?",
        "What is the revenue by billing country?",
        "Show the most recent invoices",
        "Which track has been purchased the most times?",
        "What albums are in the Metal genre?",
        "List all artists with more than 5 albums",
        "What is the total number of customers?",
        "Show me tracks that cost more than $1",
        "What is the average album price?",
        "How many tracks per media type?",
        "Which city has the most customers?",
        "Show all invoices from 2013",
        "What genre generates the most revenue?",
        "List all tracks composed by U2",
        "How many playlists contain rock tracks?",
        "What is the revenue for each employee?",
        "Show the billing address for invoice 10",
    ]

    # Non-SQL queries (label = 0)
    non_sql_queries = [
        "What is the weather today?",
        "Tell me a joke",
        "How do I cook pasta?",
        "What is Python programming?",
        "Who is the president of the United States?",
        "What is machine learning?",
        "Tell me about artificial intelligence",
        "How do I learn to code?",
        "What is the meaning of life?",
        "Can you help me with my homework?",
        "What is the capital of France?",
        "How does the internet work?",
        "Tell me about climate change",
        "What is quantum computing?",
        "How do I start a business?",
        "What is blockchain technology?",
        "Tell me about space exploration",
        "How do vaccines work?",
        "What is the speed of light?",
        "Can you write me a poem?",
        "What is the GDP of China?",
        "How does photosynthesis work?",
        "Tell me about the solar system",
        "What is deep learning?",
        "How do I invest in stocks?",
        "What are the symptoms of flu?",
        "Tell me about World War II",
        "How do I fix my computer?",
        "What is cryptocurrency?",
        "Can you translate this to Spanish?",
        "What is the best programming language?",
        "How do I lose weight?",
        "Tell me about renewable energy",
        "What is the population of India?",
        "How does a car engine work?",
        "What is the theory of relativity?",
        "Tell me about DNA",
        "How do I make a website?",
        "What is natural language processing?",
        "Can you recommend a good book?",
        "What causes earthquakes?",
        "How does WiFi work?",
        "Tell me about the Roman Empire",
        "What is an API?",
        "How do I meditate?",
        "What is cloud computing?",
        "Tell me about nutrition",
        "How does GPS work?",
        "What is the Pythagorean theorem?",
        "Can you help me plan a trip?",
    ]

    # Domain labels for SQL queries
    domains = [
        "finance", "customer", "inventory", "inventory", "inventory",
        "inventory", "finance", "finance", "inventory", "hr",
        "inventory", "inventory", "customer", "inventory", "inventory",
        "inventory", "inventory", "inventory", "inventory", "inventory",
        "finance", "finance", "hr", "finance", "customer",
        "inventory", "inventory", "inventory", "finance", "customer",
        "customer", "inventory", "inventory", "finance", "finance",
        "finance", "finance", "inventory", "inventory", "customer",
        "inventory", "finance", "inventory", "customer", "finance",
        "finance", "inventory", "inventory", "hr", "finance",
    ]

    # Complexity labels for SQL queries
    complexities = [
        "simple", "simple", "simple", "simple", "simple",
        "complex", "medium", "simple", "medium", "simple",
        "simple", "simple", "simple", "simple", "medium",
        "medium", "simple", "simple", "simple", "medium",
        "complex", "complex", "medium", "medium", "complex",
        "medium", "simple", "medium", "medium", "medium",
        "complex", "simple", "simple", "medium", "complex",
        "medium", "complex", "medium", "complex", "simple",
        "simple", "medium", "medium", "medium", "medium",
        "complex", "medium", "complex", "complex", "medium",
    ]

    # Task type labels for SQL queries
    task_types = [
        "aggregation", "retrieval", "aggregation", "retrieval", "retrieval",
        "ranking", "aggregation", "aggregation", "ranking", "retrieval",
        "retrieval", "retrieval", "aggregation", "aggregation", "ranking",
        "retrieval", "retrieval", "retrieval", "aggregation", "ranking",
        "aggregation", "aggregation", "ranking", "retrieval", "retrieval",
        "aggregation", "retrieval", "retrieval", "aggregation", "ranking",
        "ranking", "aggregation", "retrieval", "aggregation", "aggregation",
        "retrieval", "ranking", "retrieval", "retrieval", "aggregation",
        "retrieval", "aggregation", "aggregation", "ranking", "retrieval",
        "ranking", "retrieval", "aggregation", "aggregation", "retrieval",
    ]

    return sql_queries, non_sql_queries, domains, complexities, task_types


def train_classifier():
    """Train and save the intent classifier."""
    print("=" * 60)
    print("Training Intent Classifier")
    print("=" * 60)

    sql_queries, non_sql_queries, domains, complexities, task_types = create_training_data()

    # Prepare binary classification data
    all_texts = sql_queries + non_sql_queries
    all_labels = [1] * len(sql_queries) + [0] * len(non_sql_queries)

    # TF-IDF Vectorizer
    print("\n1. Fitting TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(max_features=5000, stop_words='english', ngram_range=(1, 2))
    X = vectorizer.fit_transform(all_texts)
    y = np.array(all_labels)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Binary classifier (SQL vs Non-SQL)
    print("2. Training binary classifier (SQL vs Non-SQL)...")
    binary_classifier = LinearSVC(random_state=42, max_iter=10000)
    binary_classifier.fit(X_train, y_train)

    y_pred = binary_classifier.predict(X_test)
    print(f"   Binary Accuracy: {accuracy_score(y_test, y_pred):.2f}")
    print(classification_report(y_test, y_pred, target_names=["Non-SQL", "SQL"]))

    # Multi-label classifiers (only for SQL queries)
    sql_X = vectorizer.transform(sql_queries)

    # Domain classifier
    print("3. Training domain classifier...")
    label_encoder_domain = LabelEncoder()
    domain_labels = label_encoder_domain.fit_transform(domains)
    classifier_domain = LinearSVC(random_state=42, max_iter=10000)
    classifier_domain.fit(sql_X, domain_labels)

    # Complexity classifier
    print("4. Training complexity classifier...")
    label_encoder_complexity = LabelEncoder()
    complexity_labels = label_encoder_complexity.fit_transform(complexities)
    classifier_complexity = LinearSVC(random_state=42, max_iter=10000)
    classifier_complexity.fit(sql_X, complexity_labels)

    # Task type classifier
    print("5. Training task type classifier...")
    label_encoder_task_type = LabelEncoder()
    task_type_labels = label_encoder_task_type.fit_transform(task_types)
    classifier_task_type = LinearSVC(random_state=42, max_iter=10000)
    classifier_task_type.fit(sql_X, task_type_labels)

    # Save all models to pickle
    model_dict = {
        "vectorizer": vectorizer,
        "binary_classifier": binary_classifier,
        "classifier_domain": classifier_domain,
        "classifier_complexity": classifier_complexity,
        "classifier_task_type": classifier_task_type,
        "label_encoder_domain": label_encoder_domain,
        "label_encoder_complexity": label_encoder_complexity,
        "label_encoder_task_type": label_encoder_task_type,
    }

    output_path = Path(__file__).parent / "combined_sql_classifier.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(model_dict, f)

    print(f"\n✅ Classifier saved to: {output_path}")
    print(f"   Domain classes: {list(label_encoder_domain.classes_)}")
    print(f"   Complexity classes: {list(label_encoder_complexity.classes_)}")
    print(f"   Task type classes: {list(label_encoder_task_type.classes_)}")

    return model_dict


if __name__ == "__main__":
    train_classifier()
