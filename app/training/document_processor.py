import os
import json
from typing import List, Tuple
from pypdf import PdfReader
from app.config import get_settings

settings = get_settings()


class DocumentProcessor:
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        try:
            with open(file_path, "rb") as file:
                reader = PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text()
        except Exception as e:
            raise Exception(f"Error extracting PDF text: {str(e)}")
        return text

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error reading TXT file: {str(e)}")

    @staticmethod
    def extract_text_from_md(file_path: str) -> str:
        """Extract text from Markdown file"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error reading Markdown file: {str(e)}")

    @staticmethod
    def extract_text_from_json(file_path: str) -> str:
        """Extract text from JSON file"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                
            text = ""
            if isinstance(data, dict):
                for key, value in data.items():
                    text += f"{key}: {value}\n"
            elif isinstance(data, list):
                for item in data:
                    text += f"{item}\n"
            else:
                text = str(data)
            
            return text
        except Exception as e:
            raise Exception(f"Error reading JSON file: {str(e)}")

    @classmethod
    def extract_text(cls, file_path: str, file_type: str) -> str:
        """Extract text based on file type"""
        file_type = file_type.lower()
        
        if file_type == "pdf":
            return cls.extract_text_from_pdf(file_path)
        elif file_type == "txt":
            return cls.extract_text_from_txt(file_path)
        elif file_type == "md":
            return cls.extract_text_from_md(file_path)
        elif file_type == "json":
            return cls.extract_text_from_json(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    @classmethod
    def chunk_text(cls, text: str) -> List[str]:
        """Split text into chunks with overlap"""
        chunks = []
        words = text.split()
        
        current_chunk = []
        for word in words:
            current_chunk.append(word)
            
            if len(current_chunk) >= cls.CHUNK_SIZE:
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)
                
                overlap_size = cls.CHUNK_OVERLAP
                current_chunk = current_chunk[-overlap_size:]
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks

    @classmethod
    def process_document(cls, file_path: str, file_type: str) -> Tuple[List[str], str]:
        """Process document and return chunks and full text"""
        text = cls.extract_text(file_path, file_type)
        chunks = cls.chunk_text(text)
        return chunks, text
