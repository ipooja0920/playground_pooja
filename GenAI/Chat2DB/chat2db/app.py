"""
Chat2DB - Main Streamlit Application

A web chatbot interface for database interactions using natural language.
Supports multiple interaction methods (RAG, TAG) with different LLMs (OpenAI, Claude).
Includes optional intent classification and comprehensive observability via Langfuse.
"""

import streamlit as st
from dataclasses import dataclass

from dotenv import load_dotenv
from tools.db import DatabaseManager
from tools.rag import RAGSearch  # RAG
from tools.tag import create_tag_pipeline  # TAG

load_dotenv()

import asyncio
import pickle
from pathlib import Path

from langfuse.llama_index import LlamaIndexInstrumentor
from langfuse.decorators import langfuse_context, observe


@dataclass
class ChatConfig:
    """Configuration for chat application."""
    interaction_method: str
    llm_provider: str
    openai_model_name: str = "gpt-4"
    claude_model_name: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.1


class ChatDatabase:
    """Main chat application class — manages DB connections, classifier, and query pipelines."""

    def __init__(self):
        # Initialize Vector Database
        try:
            self.vec_db_manager = DatabaseManager(db_type='vecdb')
            self.vec_db_manager.test_connection()
        except Exception as e:
            st.error(f"Error connecting to vector store: {str(e)}")
            self.vec_db_manager = None

        # Initialize Chat Database
        try:
            self.chat_db_manager = DatabaseManager(db_type='db')
            self.chat_db_manager.test_connection()
        except Exception as e:
            st.error(f"Error connecting to SQL database: {str(e)}")
            self.chat_db_manager = None

        # Load classifier model
        self.classifier = self.load_classifier()

        # Initialize Langfuse instrumentor
        self.instrumentor = LlamaIndexInstrumentor()
        self.instrumentor.start()
        print("Langfuse instrumentor checkpoint: Disregard Langfuse error messages on dev mode.")

    def load_classifier(self):
        """Load the intent classifier model from a pickle file."""
        current_dir = Path(__file__).parent
        model_path = current_dir / 'classifier/combined_sql_classifier.pkl'

        if not model_path.exists():
            print(f"Classifier model not found at {model_path}. Intent classification disabled.")
            return None

        try:
            with open(model_path, 'rb') as file:
                objects = pickle.load(file)
            return objects
        except Exception as e:
            print(f"Error loading classifier: {e}")
            return None

    def classify_prompt(self, prompt):
        """Classify the prompt using the loaded classifier."""
        if self.classifier is None:
            # If no classifier loaded, allow all queries
            return True

        vectorizer = self.classifier["vectorizer"]
        binary_classifier = self.classifier["binary_classifier"]
        classifier_domain = self.classifier["classifier_domain"]
        classifier_complexity = self.classifier["classifier_complexity"]
        classifier_task_type = self.classifier["classifier_task_type"]
        label_encoder_domain = self.classifier["label_encoder_domain"]
        label_encoder_complexity = self.classifier["label_encoder_complexity"]
        label_encoder_task_type = self.classifier["label_encoder_task_type"]

        # Transform the prompt using the vectorizer
        prompt_tfidf = vectorizer.transform([prompt])

        # Binary Classification (SQL vs Non-SQL)
        is_sql = binary_classifier.predict(prompt_tfidf)[0]

        # If not SQL, return early
        if is_sql == 0:
            print("Classification Results: Non-SQL Query")
            return False

        # Predict using the classifiers
        domain_prediction = classifier_domain.predict(prompt_tfidf)[0]
        complexity_prediction = classifier_complexity.predict(prompt_tfidf)[0]
        task_type_prediction = classifier_task_type.predict(prompt_tfidf)[0]

        # Decode predictions
        domain = label_encoder_domain.inverse_transform([domain_prediction])[0]
        complexity = label_encoder_complexity.inverse_transform([complexity_prediction])[0]
        task_type = label_encoder_task_type.inverse_transform([task_type_prediction])[0]

        print("Classification Results: SQL Query")
        print(f"Domain: {domain}")
        print(f"Complexity: {complexity}")
        print(f"Task Type: {task_type}")

        return True

    def rag_pipeline(self, query: str, config: ChatConfig) -> str:
        """RAG pipeline for database queries."""
        try:
            rag_search = RAGSearch(
                self.vec_db_manager, self.chat_db_manager, config=config
            )

            response = rag_search.query(
                f"You are Postgres expert. Generate a SQL based on the following "
                f"question using the additional metadata given to you: {query}"
            )
            print("Generated response:", response)

            sql_query = str(response).strip("`sql\n").strip("`")
            print("Generated SQL:", sql_query)

            # Execute SQL query
            sql_result = rag_search.sql_query(str(sql_query))
            print("SQL Result:", sql_result)

            return sql_result

        except Exception as e:
            return f"Error in RAG pipeline: {str(e)}"

    @observe()
    async def tag_pipeline(self, query: str, config: ChatConfig) -> str:
        """TAG pipeline for database queries."""
        try:
            # Verify database connections
            if not self.vec_db_manager or not self.chat_db_manager:
                return "Error: Database connections not initialized"

            # Initialize TAG workflow
            tag_workflow = create_tag_pipeline(
                vec_db_manager=self.vec_db_manager,
                chat_db_manager=self.chat_db_manager,
                config=config,
            )

            current_trace_id = langfuse_context.get_current_trace_id()
            current_observation_id = langfuse_context.get_current_observation_id()
            with self.instrumentor.observe(
                trace_id=current_trace_id,
                parent_observation_id=current_observation_id,
                update_parent=False,
            ):
                # Execute workflow
                handler = tag_workflow.run(query=query)
                response = await handler
                return str(response)

        except Exception as e:
            return f"Error in TAG pipeline: {str(e)}"


def main():
    """Main Streamlit application entry point."""

    # Session state initialization
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False

    # Page config
    st.set_page_config(
        page_title="Chat2DB — Talk to Your Database",
        page_icon="🤖",
        layout="wide",
    )

    # Streamlit UI
    st.title("🤖 Chat To Your Database 🤖")
    st.caption("Ask questions about your database in plain English")

    with st.sidebar:
        st.header("⚙️ Configuration")

        interaction_method = st.selectbox(
            "Interaction Method",
            ["RAG", "TAG"],
            key="interaction_method",
            help="RAG: Vector-augmented SQL generation. TAG: Direct table-augmented generation.",
        )

        llm_provider = st.selectbox(
            "LLM Provider",
            ["OpenAI", "Claude"],
            key="llm_provider",
            help="Choose which LLM to use for query generation.",
        )

        with st.expander("Advanced Settings"):
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.1,
                step=0.1,
                help="Lower = more deterministic, Higher = more creative",
            )
            st.session_state.intent_classifier_enabled = st.toggle(
                "Intent Classifier",
                value=st.session_state.intent_classifier_enabled,
                help="Enable/disable intent classification to filter non-database questions",
            )

        st.divider()
        st.markdown("### 📊 Sample Questions")
        st.markdown(
            """
            - What track has the most revenue?
            - Which customer spent the most?
            - List all jazz albums
            - How many tracks per genre?
            - Show top 5 artists by album count
            """
        )

    # Initialize chat interface
    chat = ChatDatabase()

    # Chat interface
    if query := st.chat_input("Ask a question about your database"):
        config = ChatConfig(
            interaction_method=interaction_method,
            llm_provider=llm_provider,
            temperature=temperature,
        )

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": query})

        with st.spinner("Processing your question..."):
            # Check intent first
            should_process_llm = True
            if st.session_state.intent_classifier_enabled:
                should_process_llm = chat.classify_prompt(query)
                if not should_process_llm:
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": "Message from Classifier: This question doesn't appear to be database-related.",
                        }
                    )

            if should_process_llm:
                # Process query based on selected method
                response = (
                    chat.rag_pipeline(query, config)
                    if interaction_method == "RAG"
                    else asyncio.run(chat.tag_pipeline(query, config))
                )
                # Add assistant response to chat history
                if isinstance(response, str):
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
                else:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response.response}
                    )

    # Display the entire chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])


if __name__ == "__main__":
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False
    main()
