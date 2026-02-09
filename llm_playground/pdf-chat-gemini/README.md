# Chat-with-Multiple-PDF-documents-using-LangChain-and-Google-Gemini-Pro-
# Overview
This repository enables AI-driven interactions with multiple PDF documents using LangChain and Google Gemini Pro. The application facilitates extracting insights, summarization, and real-time question answering from multiple PDFs simultaneously.

# Features
AI-Powered Extraction: Automatically extracts text from multiple PDF documents.

Summarization: Generates concise summaries of document contents using large language models (LLMs).

Question Answering: Allows users to query the content of multiple PDFs and receive contextually accurate responses.

Real-Time Interaction: Provides a seamless chat interface to interact with document contents.

# Installation
To run the application, first install the required dependencies.
Clone the repository first and then intall the requirements.txt file 

    pip install -r requirements.txt


# Usage
Set up your environment variables:

Ensure you have access to Google Gemini Pro API and update your .env file with the appropriate API keys.
Run the application:

     streamlit run app.py

Upload your PDF documents through the interface, and start querying them using the provided chat interface.

# Requirements
The project requires the following packages:

     Streamlit
     Google Generative AI
     Python Dotenv
     Langchain
     PyPDF2
     ChromaDB
     FAISS-CPU
     Langchain Google GenAI

# How It Works

Document Upload: Upload multiple PDF files through the web interface.

Text Extraction: The app uses PyPDF2 to extract text from each PDF.

Query Processing: Leverages LangChain and Google Gemini Pro to understand and process user queries.

Answer Generation: Provides accurate responses and summaries based on the content of the uploaded PDFs.




