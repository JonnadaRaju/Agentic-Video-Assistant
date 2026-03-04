from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import User
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.agent_service import execute_agent_query
from app.services.ai_service import AIServiceError
from app.services.auth_service import get_current_user


router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(
    request: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        answer, steps = await execute_agent_query(db, current_user, request.query)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return AgentQueryResponse(query=request.query, answer=answer, steps=steps)

