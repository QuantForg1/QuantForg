"""StrategyMetadata aggregate — catalogue entry for a strategy definition.

Why this entity exists
----------------------
StrategyMetadata describes *what* a strategy is (name, type, version, status,
parameter schema keys). It is a catalogue / registry record.

This entity intentionally contains **no** strategy logic, indicators,
signals generation, or execution algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.strategy import StrategyStatus, StrategyType
from app.domain.value_objects.identity import EntitySlug, PersonName, VersionLabel


@dataclass(eq=False, kw_only=True)
class StrategyMetadata(Entity):
    """Rich domain model for strategy catalogue metadata."""

    name: PersonName
    slug: EntitySlug
    version: VersionLabel
    strategy_type: StrategyType = StrategyType.CUSTOM
    status: StrategyStatus = StrategyStatus.DRAFT
    owner_user_id: UUID
    description: str = ""
    parameter_schema: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.tags = tuple(t.strip().lower() for t in self.tags if t.strip())
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(isinstance(self.name, PersonName), "name must be a PersonName")
        require(isinstance(self.slug, EntitySlug), "slug must be an EntitySlug")
        require(
            isinstance(self.version, VersionLabel), "version must be a VersionLabel"
        )
        require(
            len(self.description) <= 2000,
            "description must be at most 2000 characters",
        )
        for key, value_type in self.parameter_schema.items():
            require(bool(key.strip()), "parameter_schema keys must not be blank")
            require(
                value_type in {"string", "number", "boolean", "integer"},
                "parameter_schema value types must be string|number|boolean|integer",
                key=key,
                value_type=value_type,
            )
        require(len(self.tags) <= 20, "at most 20 tags allowed")
        for tag in self.tags:
            require(1 <= len(tag) <= 32, "each tag must be 1-32 characters", tag=tag)

    @classmethod
    def create(
        cls,
        *,
        name: str | PersonName,
        slug: str | EntitySlug,
        version: str | VersionLabel,
        owner_user_id: UUID,
        strategy_type: StrategyType = StrategyType.CUSTOM,
        description: str = "",
        parameter_schema: dict[str, str] | None = None,
        tags: tuple[str, ...] | list[str] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create a DRAFT strategy metadata record."""
        name_vo = name if isinstance(name, PersonName) else PersonName(value=name)
        slug_vo = slug if isinstance(slug, EntitySlug) else EntitySlug(value=slug)
        version_vo = (
            version
            if isinstance(version, VersionLabel)
            else VersionLabel(value=version)
        )
        kwargs: dict[str, object] = {
            "name": name_vo,
            "slug": slug_vo,
            "version": version_vo,
            "strategy_type": strategy_type,
            "status": StrategyStatus.DRAFT,
            "owner_user_id": owner_user_id,
            "description": description.strip(),
            "parameter_schema": dict(parameter_schema or {}),
            "tags": tuple(tags or ()),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def publish(self) -> None:
        """Publish a draft or deprecated strategy to the catalogue."""
        require_state(
            self.status in {StrategyStatus.DRAFT, StrategyStatus.DEPRECATED},
            "Only draft or deprecated strategies can be published",
            status=self.status.value,
        )
        self.status = StrategyStatus.PUBLISHED
        self.touch()

    def deprecate(self) -> None:
        """Mark a published strategy as deprecated."""
        require_state(
            self.status == StrategyStatus.PUBLISHED,
            "Only published strategies can be deprecated",
            status=self.status.value,
        )
        self.status = StrategyStatus.DEPRECATED
        self.touch()

    def archive(self) -> None:
        """Archive the strategy metadata permanently."""
        require_state(
            self.status != StrategyStatus.ARCHIVED,
            "Strategy is already archived",
            status=self.status.value,
        )
        self.status = StrategyStatus.ARCHIVED
        self.touch()

    def update_description(self, description: str) -> None:
        """Update the human-readable description."""
        require_state(
            self.status != StrategyStatus.ARCHIVED,
            "Cannot update an archived strategy",
            status=self.status.value,
        )
        self.description = description.strip()
        self.touch()
        self._validate_invariants()

    def set_parameter_schema(self, schema: dict[str, str]) -> None:
        """Replace the parameter schema map (types only, no runtime values)."""
        require_state(
            self.status in {StrategyStatus.DRAFT, StrategyStatus.DEPRECATED},
            "Parameter schema can only change in draft or deprecated status",
            status=self.status.value,
        )
        self.parameter_schema = dict(schema)
        self.touch()
        self._validate_invariants()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "name": str(self.name),
                "slug": str(self.slug),
                "version": str(self.version),
                "strategy_type": self.strategy_type.value,
                "status": self.status.value,
                "owner_user_id": str(self.owner_user_id),
                "description": self.description,
                "parameter_schema": dict(self.parameter_schema),
                "tags": list(self.tags),
            }
        )
        return base
