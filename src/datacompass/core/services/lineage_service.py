"""Service for lineage operations (dependency tracking and graph traversal)."""

from collections import deque
from typing import Any, Literal

from sqlalchemy.orm import Session

from datacompass.core.models.dependency import (
    ExternalNode,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineageSummary,
)
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.dependency import DependencyRepository
from datacompass.core.services.catalog_service import ObjectNotFoundError


class LineageServiceError(Exception):
    """Raised when a lineage service operation fails."""

    pass


class LineageService:
    """Service for lineage operations.

    Handles:
    - Building lineage graphs (upstream/downstream)
    - Ingesting dependencies from adapters
    - Querying dependency relationships
    """

    def __init__(self, session: Session) -> None:
        """Initialize lineage service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.dependency_repo = DependencyRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.source_repo = DataSourceRepository(session)

    def get_lineage(
        self,
        object_id: int,
        direction: Literal["upstream", "downstream"] = "upstream",
        depth: int = 3,
    ) -> LineageGraph:
        """Build lineage graph for an object using BFS traversal.

        Args:
            object_id: ID of the root object.
            direction: "upstream" for dependencies, "downstream" for dependents.
            depth: Maximum traversal depth (1-10).

        Returns:
            LineageGraph containing nodes and edges.

        Raises:
            ObjectNotFoundError: If the object doesn't exist.
        """
        # Validate depth
        depth = max(1, min(depth, 10))

        # Get root object
        root_obj = self.object_repo.get_with_source(object_id)
        if root_obj is None:
            raise ObjectNotFoundError(str(object_id))

        root_node = LineageNode(
            id=root_obj.id,
            source_name=root_obj.source.name,
            schema_name=root_obj.schema_name,
            object_name=root_obj.object_name,
            object_type=root_obj.object_type,
            distance=0,
        )

        # Track visited nodes and build graph
        visited: set[int] = {object_id}
        nodes: list[LineageNode] = []
        external_nodes: list[ExternalNode] = []
        edges: list[LineageEdge] = []
        truncated = False

        # BFS traversal
        queue: deque[tuple[int, int]] = deque([(object_id, 0)])  # (obj_id, distance)

        while queue:
            current_id, current_distance = queue.popleft()

            # Stop if we've reached max depth
            if current_distance >= depth:
                truncated = True
                continue

            # Get dependencies based on direction
            if direction == "upstream":
                deps = self.dependency_repo.get_upstream(current_id)
                for dep in deps:
                    if dep.target_id is not None:
                        # Internal dependency
                        if dep.target_id not in visited:
                            visited.add(dep.target_id)
                            target_obj = self.object_repo.get_with_source(dep.target_id)
                            if target_obj:
                                node = LineageNode(
                                    id=target_obj.id,
                                    source_name=target_obj.source.name,
                                    schema_name=target_obj.schema_name,
                                    object_name=target_obj.object_name,
                                    object_type=target_obj.object_type,
                                    distance=current_distance + 1,
                                )
                                nodes.append(node)
                                queue.append((dep.target_id, current_distance + 1))

                        edges.append(
                            LineageEdge(
                                from_id=current_id,
                                to_id=dep.target_id,
                                dependency_type=dep.dependency_type,
                                confidence=dep.confidence,
                            )
                        )
                    elif dep.target_external:
                        # External dependency
                        external_nodes.append(
                            ExternalNode(
                                schema_name=dep.target_external.get("schema"),
                                object_name=dep.target_external.get(
                                    "name", "unknown"
                                ),
                                object_type=dep.target_external.get("type"),
                                distance=current_distance + 1,
                            )
                        )
                        edges.append(
                            LineageEdge(
                                from_id=current_id,
                                to_id=None,
                                to_external=dep.target_external,
                                dependency_type=dep.dependency_type,
                                confidence=dep.confidence,
                            )
                        )
            else:
                # downstream - get objects that depend on this one
                deps = self.dependency_repo.get_downstream(current_id)
                for dep in deps:
                    if dep.object_id not in visited:
                        visited.add(dep.object_id)
                        dependent_obj = self.object_repo.get_with_source(dep.object_id)
                        if dependent_obj:
                            node = LineageNode(
                                id=dependent_obj.id,
                                source_name=dependent_obj.source.name,
                                schema_name=dependent_obj.schema_name,
                                object_name=dependent_obj.object_name,
                                object_type=dependent_obj.object_type,
                                distance=current_distance + 1,
                            )
                            nodes.append(node)
                            queue.append((dep.object_id, current_distance + 1))

                    edges.append(
                        LineageEdge(
                            from_id=dep.object_id,
                            to_id=current_id,
                            dependency_type=dep.dependency_type,
                            confidence=dep.confidence,
                        )
                    )

        return LineageGraph(
            root=root_node,
            nodes=nodes,
            external_nodes=external_nodes,
            edges=edges,
            direction=direction,
            depth=depth,
            truncated=truncated,
        )

    def get_lineage_summary(self, object_id: int) -> LineageSummary:
        """Get summary counts for an object's lineage.

        Args:
            object_id: ID of the catalog object.

        Returns:
            LineageSummary with counts.
        """
        counts = self.dependency_repo.count_by_object(object_id)

        # Count external references
        upstream_deps = self.dependency_repo.get_upstream(object_id)
        external_count = sum(1 for d in upstream_deps if d.target_id is None)

        return LineageSummary(
            upstream_count=counts["upstream"],
            downstream_count=counts["downstream"],
            external_count=external_count,
        )

    def ingest_dependencies(
        self,
        source_id: int,
        raw_dependencies: list[dict[str, Any]],
        parsing_source: str,
        clear_existing: bool = True,
    ) -> tuple[int, int]:
        """Ingest dependencies from an adapter.

        Expected raw_dependency format:
        {
            "object_schema": str,
            "object_name": str,
            "target_schema": str,
            "target_name": str,
            "dependency_type": str,  # optional, defaults to DIRECT
            "confidence": str,       # optional, defaults to HIGH
        }

        Args:
            source_id: ID of the data source.
            raw_dependencies: List of dependency dicts from adapter.
            parsing_source: Source of the dependency info.
            clear_existing: Whether to clear existing deps from this parsing source.

        Returns:
            Tuple of (created_count, updated_count).
        """
        if clear_existing:
            self.dependency_repo.delete_by_parsing_source(source_id, parsing_source)

        # Build lookup for object IDs
        objects = self.object_repo.get_by_source(source_id)
        obj_lookup: dict[tuple[str, str], int] = {
            (obj.schema_name, obj.object_name): obj.id for obj in objects
        }

        # Process dependencies
        processed_deps: list[dict[str, Any]] = []

        for raw_dep in raw_dependencies:
            obj_key = (raw_dep["object_schema"], raw_dep["object_name"])
            target_key = (raw_dep["target_schema"], raw_dep["target_name"])

            object_id = obj_lookup.get(obj_key)
            if object_id is None:
                # Source object not in catalog - skip
                continue

            target_id = obj_lookup.get(target_key)

            dep_data: dict[str, Any] = {
                "object_id": object_id,
                "target_id": target_id,
                "dependency_type": raw_dep.get("dependency_type", "DIRECT"),
                "confidence": raw_dep.get("confidence", "HIGH"),
            }

            # If target not in catalog, store as external reference
            if target_id is None:
                dep_data["target_external"] = {
                    "schema": raw_dep["target_schema"],
                    "name": raw_dep["target_name"],
                    "type": raw_dep.get("target_type"),
                }

            processed_deps.append(dep_data)

        return self.dependency_repo.upsert_batch(
            source_id=source_id,
            dependencies=processed_deps,
            parsing_source=parsing_source,
        )

    def add_manual_dependency(
        self,
        object_identifier: str,
        target_identifier: str,
        dependency_type: str = "DIRECT",
    ) -> tuple[int, int, int]:
        """Add a manual dependency between two objects.

        Args:
            object_identifier: The dependent object (source.schema.name or ID).
            target_identifier: The target object (source.schema.name or ID).
            dependency_type: DIRECT or INDIRECT.

        Returns:
            Tuple of (dependency_id, object_id, target_id).

        Raises:
            ObjectNotFoundError: If either object doesn't exist.
        """
        # Resolve object identifiers
        from datacompass.core.services.catalog_service import CatalogService

        catalog_service = CatalogService(self.session)

        obj_detail = catalog_service.get_object(object_identifier)
        target_detail = catalog_service.get_object(target_identifier)

        dep, _ = self.dependency_repo.upsert(
            source_id=obj_detail.source_id,
            object_id=obj_detail.id,
            target_id=target_detail.id,
            dependency_type=dependency_type,
            parsing_source="manual",
            confidence="HIGH",
        )
        self.session.flush()

        return dep.id, obj_detail.id, target_detail.id

    def remove_manual_dependency(
        self,
        object_id: int,
        target_id: int,
    ) -> bool:
        """Remove a manual dependency.

        Args:
            object_id: ID of the dependent object.
            target_id: ID of the target object.

        Returns:
            True if dependency was removed, False if not found.
        """
        dep = self.dependency_repo.get_by_natural_key(
            object_id=object_id,
            target_id=target_id,
            parsing_source="manual",
        )
        if dep:
            self.dependency_repo.delete(dep)
            return True
        return False
