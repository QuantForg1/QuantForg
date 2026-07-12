"""RegisterUserUseCase — onboard a new platform user.

Why this use case exists
------------------------
User registration is the entry point for every actor on QuantForg. This use
case enforces email uniqueness, constructs a pending User via the domain
factory, and persists it through the Unit of Work — without touching HTTP
or SQL details.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.user import RegisterUserCommand, UserDTO
from app.domain.entities.user import User
from app.domain.exceptions.base import ConflictError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory
from app.domain.value_objects.email import EmailAddress


@dataclass(frozen=True, slots=True)
class RegisterUserUseCase:
    """Register a new pending user account."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: RegisterUserCommand) -> UserDTO:
        """Create and persist a pending user if the email is unused."""
        email = EmailAddress(value=command.email)

        async with self.uow_factory() as uow:
            existing = await uow.users.get_by_email(email)
            if existing is not None:
                raise ConflictError(
                    "A user with this email already exists",
                    details={"email": email.value},
                )

            user = User.create(
                email=email,
                display_name=command.display_name,
                role=command.role,
                password_hash=command.password_hash,
            )
            await uow.users.add(user)
            await uow.commit()
            return UserDTO.from_entity(user)
