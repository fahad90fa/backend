from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query, Form
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime
from app.database import get_db
from app.models import User, TrainingDocument
from app import schemas, security
from app.config import get_settings
from app.training.document_processor import DocumentProcessor
from app.training.vector_store import VectorStore
from app.utils.checksum import ChecksumUtils

settings = get_settings()
router = APIRouter(prefix="/training", tags=["training"])

vector_store = VectorStore()

ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "json"}


def validate_file_extension(filename: str) -> str:
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an extension"
        )
    
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allowed file types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    return ext


@router.post("/upload", response_model=schemas.TrainingDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required"
        )
    
    file_ext = validate_file_extension(file.filename)
    
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    try:
        chunks, full_text = DocumentProcessor.process_document(file_path, file_ext)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )
    
    source_name = f"{file.filename}_{file_id}"
    
    checksum_sha256, file_size = ChecksumUtils.get_file_stats(file_path)
    
    try:
        chunk_count = vector_store.add_documents(
            user_id=current_user.id,
            source_name=source_name,
            chunks=chunks,
            metadata={"filename": file.filename, "checksum": checksum_sha256}
        )
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing document in vector database: {str(e)}"
        )
    
    content_preview = full_text[:500] if full_text else ""
    
    db_document = TrainingDocument(
        user_id=current_user.id,
        filename=file.filename,
        source_name=source_name,
        file_type=file_ext,
        content_preview=content_preview,
        chunk_count=chunk_count,
        checksum_sha256=checksum_sha256,
        file_size=file_size
    )
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    return {
        "id": db_document.id,
        "filename": db_document.filename,
        "source_name": db_document.source_name,
        "file_type": db_document.file_type,
        "chunk_count": db_document.chunk_count,
        "checksum_sha256": db_document.checksum_sha256,
        "file_size": db_document.file_size,
        "created_at": db_document.created_at
    }


@router.post("/upload-with-verify", response_model=dict)
async def upload_document_with_two_way_verification(
    file: UploadFile = File(...),
    client_checksum: str = Form(...),
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required"
        )
    
    file_ext = validate_file_extension(file.filename)
    
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    try:
        chunks, full_text = DocumentProcessor.process_document(file_path, file_ext)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )
    
    source_name = f"{file.filename}_{file_id}"
    server_checksum, file_size = ChecksumUtils.get_file_stats(file_path)
    
    verification_match = client_checksum.lower() == server_checksum.lower()
    
    try:
        chunk_count = vector_store.add_documents(
            user_id=current_user.id,
            source_name=source_name,
            chunks=chunks,
            metadata={
                "filename": file.filename,
                "checksum": server_checksum,
                "client_checksum": client_checksum,
                "two_way_verified": verification_match
            }
        )
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing document in vector database: {str(e)}"
        )
    
    content_preview = full_text[:500] if full_text else ""
    
    db_document = TrainingDocument(
        user_id=current_user.id,
        filename=file.filename,
        source_name=source_name,
        file_type=file_ext,
        content_preview=content_preview,
        chunk_count=chunk_count,
        checksum_sha256=server_checksum,
        file_size=file_size,
        client_checksum=client_checksum,
        checksum_verified=verification_match,
        verification_timestamp=datetime.utcnow() if verification_match else None
    )
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    if not verification_match:
        try:
            from sqlalchemy import text
            db.execute(
                text("""
                    INSERT INTO security_events (user_id, event_type, resource_type, resource_id, description, severity, metadata)
                    VALUES (:user_id, :event_type, :resource_type, :resource_id, :description, :severity, :metadata)
                """),
                {
                    "user_id": current_user.id,
                    "event_type": "two_way_checksum_mismatch",
                    "resource_type": "training_document",
                    "resource_id": db_document.id,
                    "description": f"Two-way checksum mismatch detected for {file.filename}",
                    "severity": "critical",
                    "metadata": {
                        "client_checksum": client_checksum,
                        "server_checksum": server_checksum,
                        "verification_type": "upload"
                    }
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to log security event: {str(e)}")
    
    return {
        "id": db_document.id,
        "filename": db_document.filename,
        "source_name": db_document.source_name,
        "file_type": db_document.file_type,
        "chunk_count": db_document.chunk_count,
        "checksum_sha256": db_document.checksum_sha256,
        "file_size": db_document.file_size,
        "created_at": db_document.created_at,
        "verified": True,
        "client_checksum": client_checksum,
        "server_checksum": server_checksum,
        "match": verification_match
    }


@router.get("/documents", response_model=list[schemas.TrainingDocumentResponse])
async def get_documents(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    documents = db.query(TrainingDocument).filter(
        TrainingDocument.user_id == current_user.id
    ).order_by(TrainingDocument.created_at.desc()).all()
    
    return documents


@router.get("/documents/{source_name}/verify")
async def verify_document_integrity(
    source_name: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(TrainingDocument).filter(
        TrainingDocument.source_name == source_name,
        TrainingDocument.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if not document.checksum_sha256:
        return {
            "verified": False,
            "status": "unknown",
            "message": "Document checksum not available (legacy upload)",
            "checksum": None
        }
    
    file_id = document.source_name.split('_')[-1]
    file_path = None
    for fname in os.listdir(settings.UPLOAD_DIR):
        if file_id in fname:
            file_path = os.path.join(settings.UPLOAD_DIR, fname)
            break
    
    if not file_path or not os.path.exists(file_path):
        return {
            "verified": False,
            "status": "file_missing",
            "message": "Original file not found on disk",
            "checksum": document.checksum_sha256[:16] + "..."
        }
    
    current_checksum = ChecksumUtils.compute_sha256_from_file(file_path)
    verified = current_checksum == document.checksum_sha256
    
    if not verified:
        try:
            from sqlalchemy import text
            db.execute(
                text("""
                    INSERT INTO security_events (user_id, event_type, resource_type, resource_id, description, severity, metadata)
                    VALUES (:user_id, :event_type, :resource_type, :resource_id, :description, :severity, :metadata)
                """),
                {
                    "user_id": current_user.id,
                    "event_type": "checksum_mismatch",
                    "resource_type": "training_document",
                    "resource_id": document.id,
                    "description": f"File integrity mismatch detected for {document.filename}",
                    "severity": "critical",
                    "metadata": {"expected": document.checksum_sha256, "computed": current_checksum}
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to log security event: {str(e)}")
    
    return {
        "verified": verified,
        "status": "ok" if verified else "mismatch",
        "message": "Document integrity verified" if verified else "Document integrity verification failed - file may be tampered",
        "checksum": document.checksum_sha256[:16] + "..." if document.checksum_sha256 else None
    }


@router.get("/documents/{source_name}/verify-two-way")
async def verify_two_way_document_integrity(
    source_name: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(TrainingDocument).filter(
        TrainingDocument.source_name == source_name,
        TrainingDocument.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if not document.checksum_sha256 or not document.client_checksum:
        return {
            "verified": False,
            "verification_type": "none",
            "message": "Two-way verification not available (legacy upload)",
            "server_checksum": document.checksum_sha256[:16] + "..." if document.checksum_sha256 else None,
            "client_checksum": None,
            "match": False,
            "server_file_ok": None
        }
    
    file_id = document.source_name.split('_')[-1]
    file_path = None
    for fname in os.listdir(settings.UPLOAD_DIR):
        if file_id in fname:
            file_path = os.path.join(settings.UPLOAD_DIR, fname)
            break
    
    server_file_ok = file_path and os.path.exists(file_path)
    
    if server_file_ok and file_path:
        current_server_checksum = ChecksumUtils.compute_sha256_from_file(file_path)
        server_file_ok = current_server_checksum == document.checksum_sha256
    
    checksums_match = document.client_checksum.lower() == document.checksum_sha256.lower()
    
    if not checksums_match:
        try:
            from sqlalchemy import text
            db.execute(
                text("""
                    INSERT INTO security_events (user_id, event_type, resource_type, resource_id, description, severity, metadata)
                    VALUES (:user_id, :event_type, :resource_type, :resource_id, :description, :severity, :metadata)
                """),
                {
                    "user_id": current_user.id,
                    "event_type": "two_way_checksum_mismatch_detected",
                    "resource_type": "training_document",
                    "resource_id": document.id,
                    "description": f"Two-way checksum verification failed for {document.filename}",
                    "severity": "critical",
                    "metadata": {
                        "client_checksum": document.client_checksum,
                        "server_checksum": document.checksum_sha256,
                        "verification_type": "retrieval",
                        "server_file_integrity": server_file_ok
                    }
                }
            )
            db.commit()
        except Exception as e:
            print(f"Failed to log security event: {str(e)}")
    
    return {
        "verified": checksums_match and server_file_ok,
        "verification_type": "two_way",
        "message": "✓ Two-way verification successful" if (checksums_match and server_file_ok) else "✗ Integrity verification failed",
        "server_checksum": document.checksum_sha256[:16] + "..." if document.checksum_sha256 else None,
        "client_checksum": document.client_checksum[:16] + "..." if document.client_checksum else None,
        "match": checksums_match,
        "server_file_ok": server_file_ok,
        "verification_timestamp": document.verification_timestamp
    }


@router.delete("/documents/{source_name}")
async def delete_document(
    source_name: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(TrainingDocument).filter(
        TrainingDocument.source_name == source_name,
        TrainingDocument.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    vector_store.delete_collection_by_source(current_user.id, source_name)
    
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


@router.get("/test-retrieval", response_model=schemas.RetrievalTestResponse)
async def test_retrieval(
    query: str,
    current_user: User = Depends(security.get_current_user)
):
    results = vector_store.retrieve(current_user.id, query, n_results=5)
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@router.post("/chat", response_model=schemas.TrainingChatResponse)
async def training_chat(
    chat_request: schemas.TrainingChatRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    from app.ai_engine.gemini import GeminiEngine
    from app.safety_filter import SafetyFilter
    
    is_safe, message_or_redirect = SafetyFilter.filter_query(chat_request.message)
    
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message_or_redirect
        )
    
    documents = db.query(TrainingDocument).filter(
        TrainingDocument.user_id == current_user.id
    ).all()
    
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No training documents found. Please upload documents first."
        )
    
    retrieved_docs = vector_store.retrieve(current_user.id, chat_request.message, n_results=5)
    
    if not retrieved_docs:
        doc_list = "\n".join([f"- {d.filename}" for d in documents])
        ai_response = f"""I couldn't find relevant information about your query in your training documents.

**Your uploaded documents:**
{doc_list}

Try asking questions about the topics covered in these documents. For example:
- Summarize what's in [document name]
- What are the main points in [document name]?
- Explain [specific concept or topic] from your documents

Feel free to rephrase your question or ask about specific topics from your training materials."""
        sources = []
    else:
        context = "Answer the user's question based ONLY on the following training documents:\n\n"
        sources = []
        
        for doc in retrieved_docs:
            context += f"From '{doc.get('metadata', {}).get('filename', 'Unknown')}': {doc['content']}\n\n"
            source_name = doc.get('source_name')
            if source_name:
                doc_record = db.query(TrainingDocument).filter(
                    TrainingDocument.source_name == source_name
                ).first()
                if doc_record:
                    sources.append({
                        "filename": doc_record.filename,
                        "source_name": doc_record.source_name
                    })
        
        gemini_engine = GeminiEngine()
        system_prompt = f"""You are an AI assistant that answers questions based ONLY on the provided training documents.
        
IMPORTANT RULES:
1. ONLY use information from the training documents provided
2. If the answer is not in the training documents, say "I couldn't find this information in your training documents"
3. Always cite which document you're using
4. Do not make up information or use general knowledge
5. Be helpful but honest about the limitations of your training data

{context}"""
        
        try:
            ai_response = gemini_engine.send_message(chat_request.message, system_prompt)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating response: {str(e)}"
            )
    
    ai_response = SafetyFilter.add_educational_disclaimer(ai_response, chat_request.message)
    
    try:
        from app.db.queries import TokenQueries
        await TokenQueries.add_token_transaction(
            user_id=current_user.id,
            amount=1,
            transaction_type="usage",
            reason="Training chat message"
        )
    except Exception as e:
        print(f"Warning: Failed to deduct token: {str(e)}")
    
    return {
        "message_id": str(uuid.uuid4()),
        "ai_response": ai_response,
        "sources": list({s['source_name']: s for s in sources}.values()) if sources else []
    }
