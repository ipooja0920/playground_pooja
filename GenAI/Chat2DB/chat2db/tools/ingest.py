"""
Vector Store Ingestion - Converts database documentation into vector embeddings
and stores them in PGVector for RAG-based querying.

Uses:
  - Docling for document conversion (MD/DOCX → JSON)
  - HuggingFace BAAI/bge-small-en-v1.5 for embeddings (384-dim)
  - PGVector (PostgreSQL) for vector storage
  - LlamaIndex for indexing and retrieval
"""

from pathlib import Path
import json
import os
import openai

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus

from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings
from llama_index.readers.docling import DoclingReader
from llama_index.node_parser.docling import DoclingNodeParser

from tools.db import DatabaseManager

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set TOKENIZERS_PARALLELISM to false to avoid deadlocks
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Embedding model configuration - using local HuggingFace model (no API key needed)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


class VectorSearch:
    """Manages vector store operations: ingestion, indexing, and querying."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        connection_string = db_manager.get_connection_string()
        async_connection_string = connection_string.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        self.table_name = "vector_store"
        self.vector_store = PGVectorStore(
            connection_string=connection_string,
            async_connection_string=async_connection_string,
            table_name=self.table_name,
            schema_name="public",
            embed_dim=384,
        )

        # Check if vectors exist, create if needed
        self.has_vectors = self._check_vectors_exist()
        if not self.has_vectors:
            print("No vectors found. Creating new vector store...")
            self._initialize_vectors()
            if not self.has_vectors:
                raise RuntimeError("Error initializing vector db")
        else:
            print("Using existing vector store")

    def _initialize_vectors(self):
        """Initialize vector store with database documentation."""
        try:
            # Get base directory - use ENV variable for Docker
            is_docker = os.getenv('ENV', 'true').lower() == 'true'
            base_dir = Path("/app") if is_docker else Path(__file__).parent.parent.parent

            # Define document paths relative to base directory
            doc_paths = [
                "Chinook_Data_Dictionary.md",
                "Chinook_Data_Model.md",
            ]

            # Construct full paths
            input_docs = [base_dir / "db" / doc for doc in doc_paths]

            # Verify all files exist
            if not all(path.exists() for path in input_docs):
                raise FileNotFoundError(f"Documents not found in {base_dir / 'db'}")

            # Set output directory
            output_dir = base_dir / "db" / "converted"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Process documents
            self.convert_documents(input_docs, output_dir)
            self.create_index(output_dir)
            self.has_vectors = True

        except Exception as e:
            print(f"Error initializing vectors: {e}")
            self.has_vectors = False

    def _check_vectors_exist(self) -> bool:
        """Check if vectors already exist in the database."""
        query = f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'data_{self.table_name}'
            );
        """
        try:
            result = self.db_manager.execute_query(query)

            if not (isinstance(result, list) and result and result[0].get('exists', False)):
                return False

            # If table exists, check if it has records
            records_query = f"""
                SELECT EXISTS (
                    SELECT 1 FROM data_{self.table_name} LIMIT 1
                );
            """
            records_result = self.db_manager.execute_query(records_query)
            return isinstance(records_result, list) and bool(records_result) and records_result[0].get('exists', False)

        except Exception as e:
            print(f"Error checking vector store: {e}")
            return False

    def convert_documents(self, input_paths: list, output_dir: Path) -> tuple:
        """Convert documents (MD/DOCX) to JSON format for indexing."""
        output_dir.mkdir(parents=True, exist_ok=True)
        converter = DocumentConverter()

        success_count = partial_success_count = failure_count = 0
        results = converter.convert_all(input_paths, raises_on_error=False)

        for result in results:
            if result.status == ConversionStatus.SUCCESS:
                success_count += 1
                doc_filename = result.input.file.stem
                with (output_dir / f"{doc_filename}.json").open("w") as fp:
                    fp.write(json.dumps(result.document.export_to_dict()))

        if failure_count > 0:
            raise RuntimeError(
                f"Failed converting {failure_count} of {len(input_paths)} documents."
            )

        return success_count, partial_success_count, failure_count

    def create_index(self, docs_dir: Path, force_rebuild: bool = False) -> VectorStoreIndex:
        """Create or load vector index from documents."""
        if self.has_vectors and not force_rebuild:
            return self.load_index()

        print("Creating new vector store...")
        reader = SimpleDirectoryReader(
            input_dir=str(docs_dir),
            file_extractor={
                ".*": DoclingReader(export_type=DoclingReader.ExportType.JSON)
            },
        )

        documents = reader.load_data()
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        index = VectorStoreIndex.from_documents(
            documents,
            transformations=[DoclingNodeParser()],
            storage_context=storage_context,
            show_progress=True,
        )

        return index

    def load_index(self) -> VectorStoreIndex:
        """Load existing index from vector store."""
        print("Loading existing vectors from database...")
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            storage_context=storage_context,
        )

    def query(self, index: VectorStoreIndex, query_text: str) -> str:
        """Query the vector index."""
        return index.as_query_engine().query(query_text)


def main(force_rebuild: bool = False):
    """Standalone entrypoint for testing vector ingestion."""
    input_docs = [
        Path("./db/Chinook_Data_Dictionary.md"),
        Path("./db/Chinook_Data_Model.md"),
    ]
    output_dir = Path("./db/converted")

    db_manager = DatabaseManager(db_type='vecdb')
    if not db_manager.test_connection():
        raise ConnectionError("Database connection failed")

    openai.api_key = os.getenv('OPENAI_API_KEY')
    if not openai.api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    searcher = VectorSearch(db_manager)

    if force_rebuild or not searcher.has_vectors:
        print("Converting documents and creating index...")
        searcher.convert_documents(input_docs, output_dir)
        index = searcher.create_index(output_dir, force_rebuild=force_rebuild)
    else:
        print("Using existing vector index")
        index = searcher.load_index()

    result = searcher.query(index, "What is the album table?")
    print(result)


if __name__ == "__main__":
    main()
