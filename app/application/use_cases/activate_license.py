"""ActivateLicenseUseCase — activate a pending or suspended license.

Why this use case exists
------------------------
Licenses gate commercial access. Activation is a deliberate workflow step
(e.g. after payment confirmation) that transitions PENDING/SUSPENDED → ACTIVE
via the License aggregate, keeping entitlement rules inside the domain.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.license import ActivateLicenseCommand, LicenseDTO
from app.domain.exceptions.base import NotFoundError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ActivateLicenseUseCase:
    """Activate an existing license grant."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: ActivateLicenseCommand) -> LicenseDTO:
        """Load the license, activate it, and persist the change."""
        async with self.uow_factory() as uow:
            license_ = await uow.licenses.get_by_id(command.license_id)
            if license_ is None:
                raise NotFoundError(
                    "License not found",
                    details={"license_id": str(command.license_id)},
                )

            license_.activate()
            await uow.licenses.update(license_)
            await uow.commit()
            return LicenseDTO.from_entity(license_)
