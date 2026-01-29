from typing import final, override
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import UserTable
from ..models.user_models import User
from .user_repository import UserRepository


@final
class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @override
    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = await self.session.execute(stmt)
        u = result.scalar_one_or_none()
        if not u:
            return None
        return User(
            id=u.id, email=u.email, provider=u.provider, provider_id=u.provider_id
        )

    @override
    async def get_by_provider(self, provider: str, provider_id: str) -> User | None:
        stmt = select(UserTable).where(
            UserTable.provider == provider, UserTable.provider_id == provider_id
        )
        result = await self.session.execute(stmt)
        u = result.scalar_one_or_none()
        if not u:
            return None
        return User(
            id=u.id, email=u.email, provider=u.provider, provider_id=u.provider_id
        )

    @override
    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserTable).where(UserTable.email == email)
        result = await self.session.execute(stmt)
        u = result.scalar_one_or_none()
        if not u:
            return None
        return User(
            id=u.id, email=u.email, provider=u.provider, provider_id=u.provider_id
        )

    @override
    async def create(self, email: str, provider: str, provider_id: str) -> User:
        user_table = UserTable(email=email, provider=provider, provider_id=provider_id)
        self.session.add(user_table)
        await self.session.commit()
        await self.session.refresh(user_table)
        return User(
            id=user_table.id,
            email=user_table.email,
            provider=user_table.provider,
            provider_id=user_table.provider_id,
        )
