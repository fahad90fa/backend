import google.generativeai as genai
from app.config import get_settings
from typing import List, Optional

settings = get_settings()


class GeminiEngine:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(
            settings.GEMINI_MODEL,
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
            ]
        )
        self.chat = None

    def start_chat(self, history: Optional[List[dict]] = None):
        """Start a new chat session with optional history"""
        conversation_history = history or []
        self.chat = self.model.start_chat(history=conversation_history)
        return self.chat

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        """Send a message and get response"""
        if context:
            full_message = f"Context:\n{context}\n\nUser Question:\n{message}"
        else:
            full_message = message

        try:
            response = self.chat.send_message(full_message)
            return response.text
        except Exception as e:
            raise Exception(f"Error sending message to Gemini: {str(e)}")

    def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text using Gemini"""
        try:
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="RETRIEVAL_DOCUMENT"
            )
            return result["embedding"]
        except Exception as e:
            raise Exception(f"Error generating embeddings: {str(e)}")

    @staticmethod
    def get_system_prompt() -> str:
        return """You are CyberScholar, an expert cybersecurity educator AI. Your role is to teach cybersecurity concepts with an emphasis on ethical practices and legal compliance.

IMPORTANT GUIDELINES:
1. Always emphasize that all techniques should only be used in authorized environments
2. Recommend legitimate practice platforms: HackTheBox, TryHackMe, PentesterLab, DVWA, OWASP WebGoat
3. Explain both offensive and defensive perspectives
4. Include disclaimers for sensitive topics
5. Provide code examples with explanations
6. Use markdown formatting with code blocks for clarity
7. Be clear about legal and ethical implications

EDUCATIONAL FOCUS AREAS:
- Reconnaissance and information gathering
- Vulnerability assessment and exploitation
- Payload creation and delivery mechanisms
- Python security scripting and automation
- Kali Linux tools and techniques
- Defense strategies and mitigation
- Security concepts and best practices

Always respond helpfully but responsibly, steering conversations toward legitimate learning."""
