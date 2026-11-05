from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_session
from app.errors import ApiError, not_found
from app.models import Agent
from app.routers.deps import parse_uuid
from app.services.queries import agent_detail, agent_stats, list_agents, rules_by_code

router = APIRouter()


@router.get("/agents", response_model=list[schemas.Agent])
def get_agents(session: Session = Depends(get_session)) -> list[schemas.Agent]:
    return list_agents(session)


@router.post("/agents", response_model=schemas.Agent, status_code=201)
def create_agent(body: schemas.AgentCreate, session: Session = Depends(get_session)) -> schemas.Agent:
    name = body.name.strip()
    if any(a.name.lower() == name.lower() for a in session.scalars(select(Agent))):
        raise ApiError(409, "conflict", f"An agent named {name} already exists.")
    agent = Agent(name=name, team=body.team.strip() or "Collections")
    session.add(agent)
    session.commit()
    return agent_stats(agent, [], rules_by_code(session))


@router.get("/agents/{agent_id}", response_model=schemas.AgentDetail)
def get_agent(agent_id: str, session: Session = Depends(get_session)) -> schemas.AgentDetail:
    agent = session.get(Agent, parse_uuid(agent_id, "Agent"))
    if agent is None:
        raise not_found("Agent", agent_id)
    return agent_detail(session, agent)
