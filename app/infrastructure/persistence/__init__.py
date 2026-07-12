"""Persistence adapters package."""

from app.infrastructure.persistence.supabase_identity import (
    SupabaseIdentityUnitOfWorkFactory,
)

__all__ = ["SupabaseIdentityUnitOfWorkFactory"]
