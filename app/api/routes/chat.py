from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app import schemas, security
from app.ai_engine.gemini import GeminiEngine
from app.training.vector_store import VectorStore
from app.safety_filter import SafetyFilter

router = APIRouter(prefix="/chat", tags=["chat"])

gemini_engine = GeminiEngine()
vector_store = VectorStore()


@router.post("/message", response_model=schemas.ChatResponse)
async def send_message(
    chat_request: schemas.ChatRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    is_safe, message_or_redirect = SafetyFilter.filter_query(chat_request.message)
    
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message_or_redirect
        )
    
    session_id = chat_request.session_id
    if not session_id:
        session = ChatSession(user_id=current_user.id)
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    else:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
    
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=chat_request.message
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    retrieved_docs = vector_store.retrieve(current_user.id, chat_request.message, n_results=3)
    context = ""
    if retrieved_docs:
        context = "Retrieved knowledge base:\n"
        for doc in retrieved_docs:
            context += f"- {doc['content'][:200]}...\n"
    
    conversation_history = []
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    for msg in messages[:-1]:
        gemini_role = "model" if msg.role == "assistant" else "user"
        conversation_history.append({
            "role": gemini_role,
            "parts": [{"text": msg.content}]
        })
    
    gemini_engine.start_chat(conversation_history)
    
    system_prompt = GeminiEngine.get_system_prompt()
    full_prompt = f"{system_prompt}\n\n{chat_request.message}"
    
    try:
        ai_response = gemini_engine.send_message(full_prompt, context)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )
    
    ai_response = SafetyFilter.add_educational_disclaimer(ai_response, chat_request.message)
    
    ai_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_response
    )
    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)
    
    # Deduct 1 token for the chat message
    try:
        from app.db.queries import TokenQueries
        await TokenQueries.add_token_transaction(
            user_id=current_user.id,
            amount=1,
            transaction_type="usage",
            reason="Chat message"
        )
    except Exception as e:
        print(f"Warning: Failed to deduct token: {str(e)}")
    
    return {
        "message": {
            "id": user_message.id,
            "role": user_message.role,
            "content": user_message.content,
            "created_at": user_message.created_at
        },
        "session_id": session_id,
        "ai_response": ai_response
    }


@router.get("/sessions", response_model=list[schemas.ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    
    return sessions


@router.get("/session/{session_id}", response_model=schemas.ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return session


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    db.delete(session)
    db.commit()
    
    return {"message": "Chat session deleted successfully"}
