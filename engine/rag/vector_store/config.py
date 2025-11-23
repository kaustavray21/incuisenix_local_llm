import logging
from django.conf import settings
from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)

def get_embeddings():
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL
    )