import os
from typing import List, Dict, Any
from app.config import get_settings

settings = get_settings()


class SimpleCollection:
    def __init__(self, data: Dict):
        self.data = data
    
    def add(self, ids: List[str], documents: List[str], metadatas: List[Dict]):
        self.data["ids"].extend(ids)
        self.data["documents"].extend(documents)
        self.data["embeddings"].extend([[0.0] * 768 for _ in documents])
        # Store metadatas separately
        if "metadatas" not in self.data:
            self.data["metadatas"] = []
        self.data["metadatas"].extend(metadatas)
    
    def query(self, query_texts: List[str], n_results: int = 5) -> Dict:
        docs = self.data.get("documents", [])
        metadatas = self.data.get("metadatas", [])
        ids = self.data.get("ids", [])
        
        if not docs:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        query = query_texts[0] if query_texts else ""
        
        results = []
        for i, doc in enumerate(docs):
            similarity = self._simple_similarity(query, doc)
            results.append({
                "id": ids[i] if i < len(ids) else f"doc_{i}",
                "document": doc,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": 1.0 - similarity
            })
        
        results.sort(key=lambda x: x["distance"])
        top_results = results[:n_results]
        
        return {
            "documents": [[r["document"] for r in top_results]],
            "metadatas": [[r["metadata"] for r in top_results]],
            "distances": [[r["distance"] for r in top_results]]
        }
    
    def get(self, where: Dict = None) -> Dict:
        if where is None:
            return {
                "ids": self.data.get("ids", []),
                "documents": self.data.get("documents", []),
                "metadatas": self.data.get("metadatas", [])
            }
        
        matching_ids = []
        matching_docs = []
        matching_metadatas = []
        
        metadatas = self.data.get("metadatas", [])
        for i, metadata in enumerate(metadatas):
            match = True
            for key, value in where.items():
                if metadata.get(key) != value:
                    match = False
                    break
            if match:
                matching_ids.append(self.data["ids"][i])
                matching_docs.append(self.data["documents"][i])
                matching_metadatas.append(metadata)
        
        return {
            "ids": matching_ids,
            "documents": matching_docs,
            "metadatas": matching_metadatas
        }
    
    def delete(self, ids: List[str]):
        for doc_id in ids:
            if doc_id in self.data["ids"]:
                idx = self.data["ids"].index(doc_id)
                self.data["ids"].pop(idx)
                self.data["documents"].pop(idx)
                self.data["embeddings"].pop(idx)
                if "metadatas" in self.data and idx < len(self.data["metadatas"]):
                    self.data["metadatas"].pop(idx)
    
    def _simple_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


class VectorStore:
    def __init__(self):
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.collections = {}

    def get_or_create_collection(self, user_id: str):
        """Get or create a collection for user"""
        collection_name = f"user_{user_id}"
        
        if collection_name not in self.collections:
            self.collections[collection_name] = {
                "name": collection_name,
                "metadata": {"user_id": user_id},
                "documents": [],
                "embeddings": [],
                "ids": [],
                "metadatas": []
            }
        
        return SimpleCollection(self.collections[collection_name])

    def add_documents(
        self,
        user_id: str,
        source_name: str,
        chunks: List[str],
        metadata: Dict[str, Any] = None
    ) -> int:
        """Add document chunks to vector store"""
        collection = self.get_or_create_collection(user_id)
        
        if metadata is None:
            metadata = {}
        
        ids = []
        documents = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            doc_id = f"{source_name}_{i}"
            ids.append(doc_id)
            documents.append(chunk)
            
            chunk_metadata = {
                "source": source_name,
                "chunk_index": i,
                "user_id": user_id,
                **metadata
            }
            metadatas.append(chunk_metadata)
        
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        return len(chunks)

    def retrieve(self, user_id: str, query: str, n_results: int = 5) -> List[Dict]:
        """Retrieve relevant documents for a query"""
        try:
            collection = self.get_or_create_collection(user_id)
            
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            retrieved_docs = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    retrieved_docs.append({
                        "content": doc,
                        "source": results["metadatas"][0][i].get("source", "unknown"),
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })
            
            return retrieved_docs
        except Exception as e:
            print(f"Error retrieving documents: {str(e)}")
            return []

    def delete_collection_by_source(self, user_id: str, source_name: str):
        """Delete all chunks from a specific source"""
        try:
            collection = self.get_or_create_collection(user_id)
            
            results = collection.get(
                where={"source": source_name}
            )
            
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
        except Exception as e:
            print(f"Error deleting collection: {str(e)}")

    def delete_all_user_collections(self, user_id: str):
        """Delete all collections for a user"""
        try:
            collection_name = f"user_{user_id}"
            if collection_name in self.collections:
                del self.collections[collection_name]
        except Exception as e:
            print(f"Error deleting user collections: {str(e)}")
