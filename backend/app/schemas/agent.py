from pydantic import BaseModel


class AgentQueryRequest(BaseModel):
    query: str


class AgentStep(BaseModel):
    step: str
    tool: str
    input: dict
    output_preview: str


class AgentQueryResponse(BaseModel):
    query: str
    answer: str
    steps: list[AgentStep]

