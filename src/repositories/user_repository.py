import asyncio
from abc import ABC, abstractmethod
from typing import final, override
from ..models.user_models import User
import secrets


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        pass

    @abstractmethod
    async def get_by_provider(self, provider: str, provider_id: str) -> User | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    async def create(self, email: str, provider: str, provider_id: str) -> User:
        pass


@final
class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users: dict[str, User] = {}
        self._lock = asyncio.Lock()

    @override
    async def get_by_id(self, user_id: str) -> User | None:
        async with self._lock:
            return self.users.get(user_id)

    @override
    async def get_by_provider(self, provider: str, provider_id: str) -> User | None:
        async with self._lock:
            for user in self.users.values():
                if user.provider == provider and user.provider_id == provider_id:
                    return user
            return None

    @override
    async def get_by_email(self, email: str) -> User | None:
        async with self._lock:
            for user in self.users.values():
                if user.email == email:
                    return user
            return None

    @override
    async def create(self, email: str, provider: str, provider_id: str) -> User:
        async with self._lock:
            user_id = secrets.token_urlsafe(16)
            user = User(
                id=user_id, email=email, provider=provider, provider_id=provider_id
            )
            self.users[user_id] = user
            return user
