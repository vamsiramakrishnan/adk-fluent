"""ArtifactSchema — declarative artifact contracts.

Defines which artifacts an agent produces and consumes,
enabling build-time contract validation (Pass 16).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent._schema_base import DeclarativeField, DeclarativeMetaclass

__all__ = ["ArtifactSchema", "Consumes", "Produces"]


@dataclass(frozen=True)
class Produces:
    """Declares that an agent produces this artifact."""

    filename: str
    mime: str | None = None
    scope: str = "session"


@dataclass(frozen=True)
class Consumes:
    """Declares that an agent requires this artifact from upstream."""

    filename: str
    mime: str | None = None
    scope: str = "session"


class _ArtifactSchemaMeta(DeclarativeMetaclass):
    """Metaclass for ArtifactSchema.

    Extracts Produces/Consumes from class-level default values.
    Unlike other schemas that use Annotated[type, Annotation], ArtifactSchema
    uses default values (Produces/Consumes instances) as the annotation source.
    """

    _schema_base_name = "ArtifactSchema"
    _produces: Any  # tuple[Produces, ...] — set dynamically in __new__
    _consumes: Any  # tuple[Consumes, ...] — set dynamically in __new__

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = type.__new__(mcs, name, bases, namespace)

        if name == "ArtifactSchema":
            cls._fields = {}
            cls._field_list = ()
            cls._produces = ()
            cls._consumes = ()
            return cls

        # Collect fields from class attributes that are Produces/Consumes
        fields: dict[str, DeclarativeField] = {}
        produces_list: list[Produces] = []
        consumes_list: list[Consumes] = []

        hints = getattr(cls, "__annotations__", {})
        for field_name, hint in hints.items():
            if field_name.startswith("_"):
                continue
            default = namespace.get(field_name)
            annotations: dict[type, Any] = {}
            if isinstance(default, Produces):
                annotations[Produces] = default
                produces_list.append(default)
            elif isinstance(default, Consumes):
                annotations[Consumes] = default
                consumes_list.append(default)

            if annotations:
                fields[field_name] = DeclarativeField(
                    name=field_name,
                    type_=hint if isinstance(hint, type) else str,
                    default=default,
                    annotations=annotations,
                )

        cls._fields = fields
        cls._field_list = tuple(fields.values())
        cls._produces = tuple(produces_list)
        cls._consumes = tuple(consumes_list)
        return cls


class ArtifactSchema(metaclass=_ArtifactSchemaMeta):
    """Declarative artifact contract.

    Usage::

        class ResearchArtifacts(ArtifactSchema):
            findings: str = Produces("findings.json", mime="application/json")
            report: str = Produces("report.md", mime="text/markdown")
            source: str = Consumes("raw_data.csv", mime="text/csv")

        Agent("researcher").artifact_schema(ResearchArtifacts)
    """

    _produces: tuple[Produces, ...]
    _consumes: tuple[Consumes, ...]

    @classmethod
    def produces_fields(cls) -> tuple[Produces, ...]:
        """Return all Produces annotations."""
        return cls._produces

    @classmethod
    def consumes_fields(cls) -> tuple[Consumes, ...]:
        """Return all Consumes annotations."""
        return cls._consumes

    @classmethod
    def produced_filenames(cls) -> frozenset[str]:
        """Return set of artifact filenames this schema produces."""
        return frozenset(p.filename for p in cls._produces)

    @classmethod
    def consumed_filenames(cls) -> frozenset[str]:
        """Return set of artifact filenames this schema consumes."""
        return frozenset(c.filename for c in cls._consumes)
