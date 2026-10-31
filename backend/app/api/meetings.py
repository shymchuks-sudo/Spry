from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Agenda, Meeting
from app.schemas import AgendaRead, AgendaSave, MeetingCreate, MeetingRead

router = APIRouter(prefix="/api/meetings")
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[MeetingRead])
def list_meetings(session: SessionDep) -> list[Meeting]:
    statement = select(Meeting).order_by(Meeting.starts_at, Meeting.id)
    return list(session.scalars(statement))


@router.post("", response_model=MeetingRead, status_code=201)
def create_meeting(payload: MeetingCreate, session: SessionDep) -> Meeting:
    meeting = Meeting(**payload.model_dump())
    session.add(meeting)
    session.commit()
    return meeting


@router.get("/{meeting_id}/agenda", response_model=AgendaRead)
def get_agenda(meeting_id: int, session: SessionDep) -> Agenda:
    agenda = session.scalar(select(Agenda).where(Agenda.meeting_id == meeting_id))
    if agenda is None:
        raise HTTPException(status_code=404, detail="Agenda not found")
    return agenda


@router.put("/{meeting_id}/agenda", response_model=AgendaRead)
def save_agenda(meeting_id: int, payload: AgendaSave, session: SessionDep) -> Agenda:
    if session.get(Meeting, meeting_id) is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    agenda = session.scalar(select(Agenda).where(Agenda.meeting_id == meeting_id))
    if agenda is None:
        agenda = Agenda(meeting_id=meeting_id)
        session.add(agenda)
    agenda.content = {
        "items": [i.model_dump(mode="json") for i in payload.items],
        "action_items": [a.model_dump(mode="json") for a in payload.action_items],
    }
    agenda.ai_suggestion = payload.ai_suggestion
    agenda.ai_model = payload.ai_model
    agenda.prompt_version = payload.prompt_version
    session.commit()
    return agenda
