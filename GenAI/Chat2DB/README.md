# 🤖 Chat2DB — Chat to Your Database

An LLM-powered chatbot for natural language database queries with comprehensive observability.

## Features
- **Multiple interaction methods** — RAG (Retrieval-Augmented Generation) and TAG (Table-Augmented Generation)
- **LLM provider selection** — OpenAI GPT-4 or Anthropic Claude 3.5 Sonnet
- **Intent classification** — Smart filtering via TF-IDF + SVM classifier
- **Vector search** — PGVector for database documentation retrieval
- **Observability** — Langfuse analytics for LLM tracking
- **Conversation memory** — Chat history persists until browser refresh
- **Docker-based deployment** — Full containerized setup

## Prerequisites
- Docker and Docker Compose
- Python 3.11+
- OpenAI API key (and/or Anthropic API key)

## Quick Start

### 1. Configure environment
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Build and run (Docker)
```bash
make run        # First time: builds + starts all services
make up         # Subsequent starts
```

### 3. Or run in developer mode
```bash
make dev        # Streamlit local, databases in Docker
```

### 4. Access
- **Chatbot UI**: http://localhost:8501
- **Langfuse Dashboard**: http://localhost:3000

### 5. Train the intent classifier (optional)
```bash
make train_classifier
```

## Architecture
- **Frontend**: Streamlit
- **LLM Framework**: LlamaIndex
- **Vector Database**: PostgreSQL + pgvector
- **Domain Database**: PostgreSQL 16 (Chinook)
- **Document Parsing**: Docling
- **Observability**: Langfuse

## CLI Usage
```bash
# RAG pipeline
python -m tools.rag "what is the track with the most revenue" --llm OpenAI --temperature 0.1

# TAG pipeline
python -m tools.tag "what is the track with the most revenue" --llm OpenAI --temperature 0.1
```

## Project Structure
```
Chat2DB/
├── chat2db/          # Main application
│   ├── app.py        # Streamlit entry point
│   ├── classifier/   # Intent classification
│   └── tools/        # RAG, TAG, DB, Ingest modules
├── db/               # Database files & docs
├── eval/             # Evaluation framework
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── requirements.txt
```

## References
- Inspired by [garyzava/chat-to-database-chatbot](https://github.com/garyzava/chat-to-database-chatbot)
- [RAG Paper (Facebook AI)](https://arxiv.org/abs/2005.11401)
- [TAG Paper (UC Berkeley & Stanford)](https://arxiv.org/pdf/2408.14717)
- [Chinook Database](https://github.com/lerocha/chinook-database)

## License
MIT
