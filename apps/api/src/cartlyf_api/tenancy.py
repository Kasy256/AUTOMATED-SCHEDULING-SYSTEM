from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

_SET_CONTEXT = text(
    "SELECT set_config('app.current_org', :org, true), set_config('app.current_user', :usr, true)"
)


async def set_context(
    session: AsyncSession, organisation_id: UUID | None, user_id: UUID | None
) -> None:
    """Set the RLS context for the rest of this transaction (SET LOCAL semantics)."""
    await session.execute(
        _SET_CONTEXT,
        {
            "org": "" if organisation_id is None else str(organisation_id),
            "usr": "" if user_id is None else str(user_id),
        },
    )


@asynccontextmanager
async def scoped_transaction(
    engine: AsyncEngine, organisation_id: UUID | None = None, user_id: UUID | None = None
) -> AsyncGenerator[AsyncSession]:
    """One transaction with RLS context; requests, background tasks and jobs all use this."""
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await set_context(session, organisation_id, user_id)
        yield session


async def db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    async with scoped_transaction(request.app.state.db_engine) as session:
        yield session


# scope="function" commits before the response is sent, so a failed commit is a 500, not a lie.
DbSession = Annotated[AsyncSession, Depends(db_session, scope="function")]
