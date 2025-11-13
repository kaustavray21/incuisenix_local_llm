import os
import logging
from django.conf import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/text-embedding-004" 

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )