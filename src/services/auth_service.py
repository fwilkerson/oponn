from typing import final
from ..repositories.user_repository import UserRepository
from ..models.user_models import User


@final
class AuthService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def get_user_by_id(self, user_id: str) -> User | None:
        return await self.repository.get_by_id(user_id)

    async def authenticate_user(
        self, email: str, provider: str, provider_id: str
    ) -> User:
        """Finds a user by provider info, or creates one if they don't exist."""
        user = await self.repository.get_by_provider(provider, provider_id)
        if user:
            return user

        # Check if email exists with a different provider
        existing_email_user = await self.repository.get_by_email(email)
        if existing_email_user:
            return existing_email_user

        # Create new user
        return await self.repository.create(email, provider, provider_id)
