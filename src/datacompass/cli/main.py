"""Main CLI entry point for Data Compass."""

import json
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from datacompass import __version__
from datacompass.cli.helpers import get_session, handle_error, serialize_for_json
from datacompass.core.services import (
    CatalogService,
    DocumentationService,
    ObjectNotFoundError,
    SearchService,
    SourceService,
)
from datacompass.core.models.dependency import LineageGraph
from datacompass.core.services.lineage_service import LineageService
from datacompass.core.services.deprecation_service import (
    CampaignNotFoundError,
    DeprecationNotFoundError,
    DeprecationService,
)
from datacompass.core.services.dq_service import (
    DQService,
    DQServiceError,
    DQConfigNotFoundError,
    DQBreachNotFoundError,
)
from datacompass.core.services.scheduling_service import (
    SchedulingService,
    ScheduleNotFoundError,
    ScheduleExistsError,
)
from datacompass.core.services.notification_service import (
    NotificationService,
    ChannelNotFoundError,
    ChannelExistsError,
    RuleNotFoundError,
)
from datacompass.core.services.auth_service import (
    AuthService,
    AuthServiceError,
    AuthDisabledError,
    InvalidCredentialsError,
    UserNotFoundError,
    UserExistsError,
    APIKeyNotFoundError,
    TokenExpiredError,
)
from datacompass.core.models.auth import UserCreate

# Console instances for stdout/stderr
console = Console()
err_console = Console(stderr=True)


class OutputFormat(str, Enum):
    """Output format options."""

    json = "json"
    table = "table"


class LineageOutputFormat(str, Enum):
    """Output format options for lineage commands."""

    json = "json"
    table = "table"
    tree = "tree"


class LineageDirection(str, Enum):
    """Direction for lineage traversal."""

    upstream = "upstream"
    downstream = "downstream"


# Main app
app = typer.Typer(
    name="datacompass",
    help="Terminal-first metadata catalog with data quality monitoring and lineage visualization.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Command groups
source_app = typer.Typer(
    help="Manage data sources.",
    no_args_is_help=True,
)
objects_app = typer.Typer(
    help="Browse and inspect catalog objects.",
    no_args_is_help=True,
)
dq_app = typer.Typer(
    help="Data quality monitoring commands.",
    no_args_is_help=True,
)
deprecate_app = typer.Typer(
    help="Deprecation campaign management.",
    no_args_is_help=True,
)
adapters_app = typer.Typer(
    help="List and inspect available adapters.",
    no_args_is_help=True,
)
schedule_app = typer.Typer(
    help="Manage scheduled jobs.",
    no_args_is_help=True,
)
scheduler_app = typer.Typer(
    help="Control the scheduler daemon.",
    no_args_is_help=True,
)
notify_app = typer.Typer(
    help="Manage notifications.",
    no_args_is_help=True,
)
auth_app = typer.Typer(
    help="Authentication management.",
    no_args_is_help=True,
)
auth_user_app = typer.Typer(
    help="User management (admin).",
    no_args_is_help=True,
)
auth_apikey_app = typer.Typer(
    help="API key management.",
    no_args_is_help=True,
)

app.add_typer(source_app, name="source")
app.add_typer(objects_app, name="objects")
app.add_typer(dq_app, name="dq")
app.add_typer(deprecate_app, name="deprecate")
app.add_typer(adapters_app, name="adapters")
app.add_typer(schedule_app, name="schedule")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(notify_app, name="notify")
app.add_typer(auth_app, name="auth")
auth_app.add_typer(auth_user_app, name="user")
auth_app.add_typer(auth_apikey_app, name="apikey")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"datacompass {__version__}")
        raise typer.Exit()


def output_result(data: dict | list, format: OutputFormat) -> None:
    """Output data in the specified format."""
    if format == OutputFormat.json:
        console.print_json(json.dumps(serialize_for_json(data)))
    else:
        # Table format - implementation depends on data structure
        if isinstance(data, list) and data:
            table = Table()
            # Use keys from first item as columns
            for key in data[0]:
                table.add_column(key)
            for row in data:
                table.add_row(*[str(v) if v is not None else "" for v in row.values()])
            console.print(table)
        elif isinstance(data, dict):
            table = Table(show_header=False)
            table.add_column("Key", style="bold")
            table.add_column("Value")
            for key, value in data.items():
                table.add_row(key, str(value) if value is not None else "")
            console.print(table)
        else:
            console.print(data)


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file.",
            envvar="DATACOMPASS_CONFIG_FILE",
        ),
    ] = None,
) -> None:
    """Data Compass - Terminal-first metadata catalog."""
    # Config path is handled by settings if provided
    pass


# =============================================================================
# Source commands
# =============================================================================


@source_app.command("add")
def source_add(
    name: Annotated[str, typer.Argument(help="Name for the data source.")],
    source_type: Annotated[
        str, typer.Option("--type", "-t", help="Source type (e.g., databricks).")
    ],
    config_file: Annotated[
        Path, typer.Option("--config", "-c", help="Path to source configuration YAML.")
    ],
    display_name: Annotated[
        str | None, typer.Option("--display-name", "-d", help="Human-readable display name.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Add a new data source."""
    try:
        with get_session() as session:
            service = SourceService(session)
            source = service.add_source(
                name=name,
                source_type=source_type,
                config_path=config_file,
                display_name=display_name,
            )
            session.commit()

            result = {
                "name": source.name,
                "type": source.source_type,
                "display_name": source.display_name,
                "created_at": source.created_at,
            }
            output_result(result, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@source_app.command("list")
def source_list(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List configured data sources."""
    try:
        with get_session() as session:
            service = SourceService(session)
            sources = service.list_sources()

            result = [
                {
                    "name": s.name,
                    "type": s.source_type,
                    "display_name": s.display_name,
                    "is_active": s.is_active,
                    "last_scan_at": s.last_scan_at,
                    "last_scan_status": s.last_scan_status,
                }
                for s in sources
            ]
            output_result(result, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@source_app.command("test")
def source_test(
    name: Annotated[str, typer.Argument(help="Name of the data source to test.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Test connection to a data source."""
    try:
        with get_session() as session:
            service = SourceService(session)

            with console.status(f"Testing connection to [bold]{name}[/bold]..."):
                result = service.test_source(name)

            output_result(result.model_dump(), format)

            if not result.connected:
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@source_app.command("remove")
def source_remove(
    name: Annotated[str, typer.Argument(help="Name of the data source to remove.")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation.")
    ] = False,
) -> None:
    """Remove a data source."""
    try:
        with get_session() as session:
            service = SourceService(session)

            # Get source first to confirm it exists (raises SourceNotFoundError)
            service.get_source(name)

            if not force:
                confirm = typer.confirm(
                    f"Remove data source '{name}' and all its catalog objects?"
                )
                if not confirm:
                    raise typer.Abort()

            service.remove_source(name)
            session.commit()
            console.print(f"[green]Removed data source:[/green] {name}")
    except typer.Abort:
        raise
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Scan command (top-level)
# =============================================================================


@app.command()
def scan(
    source: Annotated[str, typer.Argument(help="Name of the source to scan.")],
    full: Annotated[
        bool, typer.Option("--full", help="Perform a full scan instead of incremental.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Scan a data source to update the catalog."""
    try:
        with get_session() as session:
            service = CatalogService(session)

            with console.status(f"Scanning [bold]{source}[/bold]..."):
                result = service.scan_source(source, full=full)
                session.commit()

            output_result(result.model_dump(), format)

            if result.status == "failed":
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Objects commands
# =============================================================================


@objects_app.command("list")
def objects_list(
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Filter by source name.")
    ] = None,
    object_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by object type.")
    ] = None,
    schema: Annotated[
        str | None, typer.Option("--schema", help="Filter by schema name.")
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-l", help="Maximum results.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List catalog objects."""
    try:
        with get_session() as session:
            service = CatalogService(session)
            objects = service.list_objects(
                source=source,
                object_type=object_type,
                schema=schema,
                limit=limit,
            )

            result = [obj.model_dump() for obj in objects]
            output_result(result, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@objects_app.command("show")
def objects_show(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name or ID).")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show details for a specific object."""
    try:
        with get_session() as session:
            service = CatalogService(session)
            obj = service.get_object(object_id)
            output_result(obj.model_dump(), format)
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        err_console.print(
            "[dim]Use 'datacompass objects list' to see available objects.[/dim]"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@objects_app.command("describe")
def objects_describe(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name or ID).")
    ],
    set_description: Annotated[
        str | None, typer.Option("--set", help="Set the description to this value.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Get or set the description for an object.

    Examples:
        datacompass objects describe prod.analytics.customers
        datacompass objects describe prod.analytics.customers --set "Main customer table"
    """
    try:
        with get_session() as session:
            doc_service = DocumentationService(session)

            if set_description is not None:
                # Set the description
                obj = doc_service.set_description(object_id, set_description)
                session.commit()

                result = {
                    "object": f"{obj.source.name}.{obj.schema_name}.{obj.object_name}",
                    "description": set_description,
                    "status": "updated",
                }
                output_result(result, format)
            else:
                # Get the description
                description = doc_service.get_description(object_id)
                result = {
                    "object": object_id,
                    "description": description,
                }
                output_result(result, format)
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        err_console.print(
            "[dim]Use 'datacompass objects list' to see available objects.[/dim]"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@objects_app.command("tag")
def objects_tag(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name or ID).")
    ],
    add: Annotated[
        list[str] | None, typer.Option("--add", "-a", help="Tag(s) to add.")
    ] = None,
    remove: Annotated[
        list[str] | None, typer.Option("--remove", "-r", help="Tag(s) to remove.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Manage tags on an object.

    Examples:
        datacompass objects tag prod.analytics.customers
        datacompass objects tag prod.analytics.customers --add pii --add core
        datacompass objects tag prod.analytics.customers --remove pii
    """
    try:
        with get_session() as session:
            doc_service = DocumentationService(session)

            if add or remove:
                # Modify tags
                if add:
                    doc_service.add_tags(object_id, add)
                if remove:
                    doc_service.remove_tags(object_id, remove)

                session.commit()

                # Get final state
                tags = doc_service.get_tags(object_id)
                result = {
                    "object": object_id,
                    "tags": tags,
                    "added": add or [],
                    "removed": remove or [],
                }
                output_result(result, format)
            else:
                # Just show current tags
                tags = doc_service.get_tags(object_id)
                result = {
                    "object": object_id,
                    "tags": tags,
                }
                output_result(result, format)
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        err_console.print(
            "[dim]Use 'datacompass objects list' to see available objects.[/dim]"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Adapters commands
# =============================================================================


@adapters_app.command("list")
def adapters_list(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List available adapter types."""
    from datacompass.core.adapters import AdapterRegistry

    adapters = AdapterRegistry.list_adapters()
    result = [
        {
            "type": info.source_type,
            "display_name": info.display_name,
            "object_types": info.supported_object_types,
        }
        for info in adapters
    ]
    output_result(result, format)


# =============================================================================
# Search commands
# =============================================================================


@app.command("search")
def search_command(
    query: Annotated[str, typer.Argument(help="Search query string.")],
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Filter by source.")
    ] = None,
    object_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by object type.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum results.")] = 50,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Search the catalog using full-text search.

    Examples:
        datacompass search "customer"
        datacompass search "pii" --source prod
        datacompass search "orders" --type TABLE
    """
    try:
        with get_session() as session:
            service = SearchService(session)
            results = service.search(
                query=query,
                source=source,
                object_type=object_type,
                limit=limit,
            )

            if not results:
                console.print("[dim]No results found.[/dim]")
                return

            result = [r.model_dump() for r in results]
            output_result(result, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@app.command("reindex")
def search_reindex(
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Reindex specific source only.")
    ] = None,
) -> None:
    """Rebuild the search index.

    Use this if search results seem stale or after manual database changes.
    """
    try:
        with get_session() as session:
            service = SearchService(session)

            with console.status("Rebuilding search index..."):
                count = service.reindex(source=source)
                session.commit()

            console.print(f"[green]Indexed {count} objects.[/green]")
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Lineage command
# =============================================================================


def _format_lineage_table(graph: LineageGraph, direction: str) -> None:
    """Format lineage as a table."""

    direction_label = "UPSTREAM DEPENDENCIES" if direction == "upstream" else "DOWNSTREAM DEPENDENTS"
    console.print(f"\n[bold]{direction_label} FOR[/bold] {graph.root.full_name}\n")

    if not graph.nodes and not graph.external_nodes:
        console.print("[dim]No dependencies found.[/dim]")
        return

    table = Table()
    table.add_column("Distance", justify="center")
    table.add_column("Source")
    table.add_column("Schema")
    table.add_column("Object")
    table.add_column("Type")

    # Sort nodes by distance
    sorted_nodes = sorted(graph.nodes, key=lambda n: (n.distance, n.full_name))
    for node in sorted_nodes:
        table.add_row(
            str(node.distance),
            node.source_name,
            node.schema_name,
            node.object_name,
            node.object_type,
        )

    # Add external nodes
    for ext_node in graph.external_nodes:
        table.add_row(
            str(ext_node.distance),
            "[dim]external[/dim]",
            ext_node.schema_name or "[dim]?[/dim]",
            ext_node.object_name,
            ext_node.object_type or "[dim]?[/dim]",
        )

    console.print(table)

    if graph.truncated:
        console.print(f"\n[yellow]Graph truncated at depth {graph.depth}. Use --depth to see more.[/yellow]")


def _format_lineage_tree(graph: LineageGraph, direction: str) -> None:
    """Format lineage as a tree."""
    # Build adjacency list
    if direction == "upstream":
        # from_id -> list of to_ids
        adj: dict[int, list[tuple[int | None, dict | None]]] = {}
        for edge in graph.edges:
            if edge.from_id not in adj:
                adj[edge.from_id] = []
            adj[edge.from_id].append((edge.to_id, edge.to_external))
    else:
        # to_id -> list of from_ids
        adj = {}
        for edge in graph.edges:
            if edge.to_id is not None:
                if edge.to_id not in adj:
                    adj[edge.to_id] = []
                adj[edge.to_id].append((edge.from_id, None))

    # Build node lookup
    node_lookup = {graph.root.id: graph.root}
    for node in graph.nodes:
        node_lookup[node.id] = node

    # Build tree recursively
    root_label = f"[bold]{graph.root.full_name}[/bold] ({graph.root.object_type})"
    tree = Tree(root_label)

    def add_children(parent_tree: Tree, node_id: int, visited: set[int]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)

        children = adj.get(node_id, [])
        for child_id, external in children:
            if child_id is not None and child_id in node_lookup:
                child_node = node_lookup[child_id]
                label = f"{child_node.full_name} ({child_node.object_type})"
                child_tree = parent_tree.add(label)
                add_children(child_tree, child_id, visited.copy())
            elif external:
                ext_name = f"{external.get('schema', '?')}.{external.get('name', '?')}"
                parent_tree.add(f"[dim]{ext_name} (external)[/dim]")

    add_children(tree, graph.root.id, set())
    console.print(tree)

    if graph.truncated:
        console.print(f"\n[yellow]Graph truncated at depth {graph.depth}. Use --depth to see more.[/yellow]")


@app.command("lineage")
def lineage_command(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name or ID).")
    ],
    direction: Annotated[
        LineageDirection,
        typer.Option("--direction", "-d", help="Traversal direction."),
    ] = LineageDirection.upstream,
    depth: Annotated[
        int, typer.Option("--depth", help="Maximum traversal depth (1-10).")
    ] = 3,
    format: Annotated[
        LineageOutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = LineageOutputFormat.json,
) -> None:
    """Show lineage (dependencies) for a catalog object.

    Examples:
        datacompass lineage demo.analytics.daily_sales
        datacompass lineage demo.core.users --direction downstream
        datacompass lineage demo.reporting.revenue_v --depth 5 --format tree
    """
    try:
        with get_session() as session:
            # Resolve object identifier to ID
            catalog_service = CatalogService(session)
            obj = catalog_service.get_object(object_id)

            lineage_service = LineageService(session)
            graph = lineage_service.get_lineage(
                object_id=obj.id,
                direction=direction.value,
                depth=depth,
            )

            if format == LineageOutputFormat.json:
                output_result(graph.model_dump(), OutputFormat.json)
            elif format == LineageOutputFormat.table:
                _format_lineage_table(graph, direction.value)
            else:  # tree
                _format_lineage_tree(graph, direction.value)

    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        err_console.print(
            "[dim]Use 'datacompass objects list' to see available objects.[/dim]"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# DQ commands
# =============================================================================

# Create breaches subcommand group
dq_breaches_app = typer.Typer(
    help="Manage DQ breaches.",
    no_args_is_help=True,
)
dq_app.add_typer(dq_breaches_app, name="breaches")


@dq_app.command("init")
def dq_init(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name).")
    ],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output path for YAML file.")
    ] = None,
) -> None:
    """Generate a DQ configuration template for an object.

    Examples:
        datacompass dq init demo.core.orders
        datacompass dq init demo.core.orders --output dq/orders.yaml
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)
            template = dq_service.generate_yaml_template(object_id)

            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(template)
                console.print(f"[green]Created DQ template:[/green] {output}")
            else:
                console.print(template)
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_app.command("apply")
def dq_apply(
    config_file: Annotated[
        Path, typer.Argument(help="Path to DQ configuration YAML file.")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Apply a DQ configuration from YAML file.

    Examples:
        datacompass dq apply dq/orders.yaml
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            config = dq_service.create_config_from_yaml(config_file)
            session.commit()

            result = {
                "config_id": config.id,
                "object": f"{config.source_name}.{config.schema_name}.{config.object_name}",
                "expectations": len(config.expectations),
                "status": "applied",
            }
            output_result(result, format)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] File not found: {config_file}")
        raise typer.Exit(1) from None
    except ObjectNotFoundError as e:
        err_console.print(f"[red]Error:[/red] Object not found in config: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_app.command("list")
def dq_list(
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Filter by source name.")
    ] = None,
    enabled_only: Annotated[
        bool, typer.Option("--enabled", help="Only show enabled configs.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List DQ configurations.

    Examples:
        datacompass dq list
        datacompass dq list --source demo
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            # Get source ID if name provided
            source_id = None
            if source:
                source_service = SourceService(session)
                src = source_service.get_source(source)
                source_id = src.id

            configs = dq_service.list_configs(
                source_id=source_id,
                enabled_only=enabled_only,
            )

            if format == OutputFormat.table:
                if not configs:
                    console.print("[dim]No DQ configurations found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Object")
                table.add_column("Grain")
                table.add_column("Expectations", justify="right")
                table.add_column("Open Breaches", justify="right")
                table.add_column("Enabled")

                for cfg in configs:
                    obj_name = f"{cfg.source_name}.{cfg.schema_name}.{cfg.object_name}"
                    enabled = "[green]Yes[/green]" if cfg.is_enabled else "[dim]No[/dim]"
                    breaches = f"[red]{cfg.open_breach_count}[/red]" if cfg.open_breach_count > 0 else "0"
                    table.add_row(
                        str(cfg.id),
                        obj_name,
                        cfg.grain,
                        str(cfg.expectation_count),
                        breaches,
                        enabled,
                    )
                console.print(table)
            else:
                result = [cfg.model_dump() for cfg in configs]
                output_result(result, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_app.command("run")
def dq_run(
    object_id: Annotated[
        str | None, typer.Argument(help="Object identifier (source.schema.name).")
    ] = None,
    all_configs: Annotated[
        bool, typer.Option("--all", help="Run checks for all enabled configs.")
    ] = False,
    snapshot_date: Annotated[
        str | None, typer.Option("--date", help="Snapshot date (YYYY-MM-DD).")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Run data quality checks.

    Examples:
        datacompass dq run demo.core.orders
        datacompass dq run --all
    """
    from datetime import date as dt_date

    try:
        with get_session() as session:
            dq_service = DQService(session)

            # Parse date
            run_date = None
            if snapshot_date:
                run_date = dt_date.fromisoformat(snapshot_date)

            if object_id:
                # Get config for object
                config = dq_service.get_config_by_object(object_id)

                with console.status(f"Running DQ checks for [bold]{object_id}[/bold]..."):
                    result = dq_service.run_expectations(config.id, run_date)
                    session.commit()

                if format == OutputFormat.table:
                    _format_dq_run_result(result)
                else:
                    output_result(result.model_dump(), format)

            elif all_configs:
                # Run all enabled configs
                configs = dq_service.list_configs(enabled_only=True)
                results = []

                for cfg in configs:
                    obj_name = f"{cfg.source_name}.{cfg.schema_name}.{cfg.object_name}"
                    with console.status(f"Running DQ checks for [bold]{obj_name}[/bold]..."):
                        run_result = dq_service.run_expectations(cfg.id, run_date)
                        results.append(run_result)

                session.commit()

                if format == OutputFormat.table:
                    for result in results:
                        _format_dq_run_result(result)
                        console.print()
                else:
                    output_result([r.model_dump() for r in results], format)
            else:
                err_console.print("[red]Error:[/red] Specify an object or use --all")
                raise typer.Exit(1)

    except DQConfigNotFoundError as e:
        err_console.print(f"[red]Error:[/red] DQ config not found: {e.identifier}")
        err_console.print("[dim]Use 'datacompass dq apply' to create a configuration.[/dim]")
        raise typer.Exit(1) from None
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


def _format_dq_run_result(result) -> None:
    """Format DQ run result as table."""
    obj_name = f"{result.source_name}.{result.schema_name}.{result.object_name}"
    console.print(f"\n[bold]DQ Results for[/bold] {obj_name} ({result.snapshot_date})\n")

    table = Table()
    table.add_column("Type")
    table.add_column("Column")
    table.add_column("Value", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status")

    for item in result.results:
        low = item.computed_threshold_low
        high = item.computed_threshold_high

        if low is not None and high is not None:
            threshold_str = f"{low:.0f}-{high:.0f}"
        elif low is not None:
            threshold_str = f">={low:.0f}"
        elif high is not None:
            threshold_str = f"<={high:.0f}"
        else:
            threshold_str = "-"

        status = "[green]PASS[/green]" if item.status == "pass" else "[red]BREACH[/red]"

        table.add_row(
            item.expectation_type,
            item.column_name or "-",
            f"{item.metric_value:,.0f}",
            threshold_str,
            status,
        )

    console.print(table)
    console.print(f"\nTotal: {result.total_checks} | Passed: {result.passed} | Breached: {result.breached}")


@dq_app.command("status")
def dq_status(
    object_id: Annotated[
        str | None, typer.Argument(help="Object identifier (source.schema.name).")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show DQ status for an object or overall hub summary.

    Examples:
        datacompass dq status
        datacompass dq status demo.core.orders
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            if object_id:
                config = dq_service.get_config_by_object(object_id)

                if format == OutputFormat.table:
                    obj_name = f"{config.source_name}.{config.schema_name}.{config.object_name}"
                    console.print(f"\n[bold]DQ Config for[/bold] {obj_name}\n")

                    table = Table(show_header=False)
                    table.add_column("Key", style="bold")
                    table.add_column("Value")
                    table.add_row("Config ID", str(config.id))
                    table.add_row("Date Column", config.date_column or "-")
                    table.add_row("Grain", config.grain)
                    table.add_row("Enabled", "Yes" if config.is_enabled else "No")
                    table.add_row("Expectations", str(len(config.expectations)))
                    console.print(table)

                    if config.expectations:
                        console.print("\n[bold]Expectations:[/bold]\n")
                        exp_table = Table()
                        exp_table.add_column("ID")
                        exp_table.add_column("Type")
                        exp_table.add_column("Column")
                        exp_table.add_column("Priority")
                        exp_table.add_column("Threshold Type")

                        for exp in config.expectations:
                            exp_table.add_row(
                                str(exp.id),
                                exp.expectation_type,
                                exp.column_name or "-",
                                exp.priority,
                                exp.threshold_config.get("type", "-"),
                            )
                        console.print(exp_table)
                else:
                    output_result(config.model_dump(), format)
            else:
                # Show hub summary
                summary = dq_service.get_hub_summary()

                if format == OutputFormat.table:
                    console.print("\n[bold]DQ Hub Summary[/bold]\n")

                    table = Table(show_header=False)
                    table.add_column("Metric", style="bold")
                    table.add_column("Value", justify="right")
                    table.add_row("Total Configs", str(summary.total_configs))
                    table.add_row("Enabled Configs", str(summary.enabled_configs))
                    table.add_row("Total Expectations", str(summary.total_expectations))
                    table.add_row("Open Breaches", f"[red]{summary.open_breaches}[/red]" if summary.open_breaches else "0")
                    console.print(table)

                    if summary.breaches_by_priority:
                        console.print("\n[bold]Open Breaches by Priority:[/bold]")
                        for priority, count in summary.breaches_by_priority.items():
                            color = "red" if priority == "critical" else "yellow" if priority == "high" else "white"
                            console.print(f"  [{color}]{priority}[/{color}]: {count}")
                else:
                    output_result(summary.model_dump(), format)

    except DQConfigNotFoundError as e:
        err_console.print(f"[red]Error:[/red] DQ config not found: {e.identifier}")
        raise typer.Exit(1) from None
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_app.command("history")
def dq_history(
    object_id: Annotated[
        str, typer.Argument(help="Object identifier (source.schema.name).")
    ],
    days: Annotated[
        int, typer.Option("--days", "-d", help="Number of days to show.")
    ] = 30,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show DQ check history for an object.

    Examples:
        datacompass dq history demo.core.orders
        datacompass dq history demo.core.orders --days 7
    """
    # Note: This is a placeholder - full implementation would query dq_results
    err_console.print("[yellow]History view coming soon - use 'dq breaches list' to see breaches.[/yellow]")


@dq_breaches_app.command("list")
def dq_breaches_list(
    status: Annotated[
        str | None, typer.Option("--status", "-s", help="Filter by status (open, acknowledged, dismissed, resolved).")
    ] = None,
    priority: Annotated[
        str | None, typer.Option("--priority", "-p", help="Filter by priority (critical, high, medium, low).")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum results.")
    ] = 50,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List DQ breaches.

    Examples:
        datacompass dq breaches list --status open
        datacompass dq breaches list --priority critical
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            breaches = dq_service.list_breaches(
                status=status,
                priority=priority,
                limit=limit,
            )

            if format == OutputFormat.table:
                if not breaches:
                    console.print("[dim]No breaches found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Object")
                table.add_column("Type")
                table.add_column("Date")
                table.add_column("Direction")
                table.add_column("Deviation")
                table.add_column("Priority")
                table.add_column("Status")

                for breach in breaches:
                    obj_name = f"{breach.schema_name}.{breach.object_name}"

                    # Color based on priority
                    priority_color = {
                        "critical": "red",
                        "high": "yellow",
                        "medium": "white",
                        "low": "dim",
                    }.get(breach.priority, "white")

                    # Color based on status
                    status_style = {
                        "open": "[red]open[/red]",
                        "acknowledged": "[yellow]acknowledged[/yellow]",
                        "dismissed": "[dim]dismissed[/dim]",
                        "resolved": "[green]resolved[/green]",
                    }.get(breach.status, breach.status)

                    direction_icon = "[red]\u2191[/red]" if breach.breach_direction == "high" else "[blue]\u2193[/blue]"

                    table.add_row(
                        str(breach.id),
                        obj_name,
                        breach.expectation_type,
                        str(breach.snapshot_date),
                        direction_icon,
                        f"{breach.deviation_percent:.1f}%",
                        f"[{priority_color}]{breach.priority}[/{priority_color}]",
                        status_style,
                    )

                console.print(table)
            else:
                result = [b.model_dump() for b in breaches]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_breaches_app.command("update")
def dq_breaches_update(
    breach_id: Annotated[
        int, typer.Argument(help="Breach ID.")
    ],
    status: Annotated[
        str, typer.Option("--status", "-s", help="New status (acknowledged, dismissed, resolved).")
    ],
    notes: Annotated[
        str | None, typer.Option("--notes", "-n", help="Notes for the status change.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Update breach status.

    Examples:
        datacompass dq breaches update 1 --status acknowledged
        datacompass dq breaches update 1 --status resolved --notes "Fixed upstream data issue"
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            breach = dq_service.update_breach_status(
                breach_id=breach_id,
                status=status,
                notes=notes,
                updated_by="cli",
            )
            session.commit()

            result = {
                "breach_id": breach.id,
                "status": breach.status,
                "notes": notes,
                "updated": True,
            }
            output_result(result, format)

    except DQBreachNotFoundError:
        err_console.print(f"[red]Error:[/red] Breach not found: {breach_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@dq_breaches_app.command("show")
def dq_breaches_show(
    breach_id: Annotated[
        int, typer.Argument(help="Breach ID.")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show breach details.

    Examples:
        datacompass dq breaches show 1
    """
    try:
        with get_session() as session:
            dq_service = DQService(session)

            breach = dq_service.get_breach(breach_id)

            if format == OutputFormat.table:
                obj_name = f"{breach.source_name}.{breach.schema_name}.{breach.object_name}"
                console.print(f"\n[bold]Breach #{breach.id}[/bold]\n")

                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Object", obj_name)
                table.add_row("Expectation", f"{breach.expectation_type}" + (f" ({breach.column_name})" if breach.column_name else ""))
                table.add_row("Date", str(breach.snapshot_date))
                table.add_row("Metric Value", f"{breach.metric_value:,.2f}")
                table.add_row("Threshold", f"{breach.threshold_value:,.2f}")
                table.add_row("Direction", breach.breach_direction)
                table.add_row("Deviation", f"{breach.deviation_percent:.1f}%")
                table.add_row("Priority", breach.priority)
                table.add_row("Status", breach.status)
                table.add_row("Detected At", str(breach.detected_at))
                console.print(table)

                if breach.lifecycle_events:
                    console.print("\n[bold]Lifecycle Events:[/bold]")
                    for event in breach.lifecycle_events:
                        console.print(f"  - {event.get('at', '?')}: {event.get('status', '?')} by {event.get('by', '?')}")
                        if event.get("notes"):
                            console.print(f"    Notes: {event['notes']}")
            else:
                output_result(breach.model_dump(), format)

    except DQBreachNotFoundError:
        err_console.print(f"[red]Error:[/red] Breach not found: {breach_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Deprecation commands
# =============================================================================

# Create campaign subcommand group
deprecate_campaign_app = typer.Typer(
    help="Manage deprecation campaigns.",
    no_args_is_help=True,
)
deprecate_app.add_typer(deprecate_campaign_app, name="campaign")


@deprecate_campaign_app.command("create")
def deprecate_campaign_create(
    name: Annotated[str, typer.Argument(help="Campaign name.")],
    source: Annotated[
        str, typer.Option("--source", "-s", help="Source name.")
    ],
    target_date: Annotated[
        str, typer.Option("--target-date", "-t", help="Target date (YYYY-MM-DD).")
    ],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Campaign description.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a new deprecation campaign.

    Examples:
        datacompass deprecate campaign create "Q2 Cleanup" --source demo --target-date 2025-06-01
    """
    from datetime import date as dt_date

    try:
        with get_session() as session:
            # Get source ID
            source_service = SourceService(session)
            src = source_service.get_source(source)

            # Parse date
            parsed_date = dt_date.fromisoformat(target_date)

            deprecation_service = DeprecationService(session)
            campaign = deprecation_service.create_campaign(
                source_id=src.id,
                name=name,
                target_date=parsed_date,
                description=description,
            )
            session.commit()

            result = {
                "id": campaign.id,
                "name": campaign.name,
                "source": campaign.source_name,
                "status": campaign.status,
                "target_date": str(campaign.target_date),
                "days_remaining": campaign.days_remaining,
            }
            output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_campaign_app.command("list")
def deprecate_campaign_list(
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Filter by source name.")
    ] = None,
    status: Annotated[
        str | None, typer.Option("--status", help="Filter by status (draft, active, completed).")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List deprecation campaigns.

    Examples:
        datacompass deprecate campaign list
        datacompass deprecate campaign list --source demo --status active
    """
    try:
        with get_session() as session:
            # Get source ID if name provided
            source_id = None
            if source:
                source_service = SourceService(session)
                src = source_service.get_source(source)
                source_id = src.id

            deprecation_service = DeprecationService(session)
            campaigns = deprecation_service.list_campaigns(
                source_id=source_id,
                status=status,
            )

            if format == OutputFormat.table:
                if not campaigns:
                    console.print("[dim]No campaigns found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Source")
                table.add_column("Name")
                table.add_column("Status")
                table.add_column("Target Date")
                table.add_column("Objects", justify="right")
                table.add_column("Days Left", justify="right")

                for c in campaigns:
                    status_style = {
                        "draft": "[dim]draft[/dim]",
                        "active": "[yellow]active[/yellow]",
                        "completed": "[green]completed[/green]",
                    }.get(c.status, c.status)

                    days = str(c.days_remaining) if c.days_remaining is not None else "-"
                    if c.days_remaining is not None and c.days_remaining < 7:
                        days = f"[red]{days}[/red]"

                    table.add_row(
                        str(c.id),
                        c.source_name,
                        c.name,
                        status_style,
                        str(c.target_date),
                        str(c.object_count),
                        days,
                    )

                console.print(table)
            else:
                result = [c.model_dump() for c in campaigns]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_campaign_app.command("show")
def deprecate_campaign_show(
    campaign_id: Annotated[int, typer.Argument(help="Campaign ID.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show campaign details.

    Examples:
        datacompass deprecate campaign show 1
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)
            campaign = deprecation_service.get_campaign(campaign_id)

            if format == OutputFormat.table:
                console.print(f"\n[bold]Campaign #{campaign.id}:[/bold] {campaign.name}\n")

                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Source", campaign.source_name)
                table.add_row("Status", campaign.status)
                table.add_row("Target Date", str(campaign.target_date))
                table.add_row("Days Remaining", str(campaign.days_remaining) if campaign.days_remaining is not None else "-")
                table.add_row("Description", campaign.description or "-")
                table.add_row("Objects", str(len(campaign.deprecations)))
                console.print(table)

                if campaign.deprecations:
                    console.print("\n[bold]Deprecated Objects:[/bold]\n")
                    dep_table = Table()
                    dep_table.add_column("ID", justify="right")
                    dep_table.add_column("Object")
                    dep_table.add_column("Type")
                    dep_table.add_column("Replacement")
                    dep_table.add_column("Notes")

                    for dep in campaign.deprecations:
                        obj_name = f"{dep.schema_name}.{dep.object_name}"
                        dep_table.add_row(
                            str(dep.id),
                            obj_name,
                            dep.object_type,
                            dep.replacement_name or "-",
                            (dep.migration_notes[:40] + "...") if dep.migration_notes and len(dep.migration_notes) > 40 else (dep.migration_notes or "-"),
                        )
                    console.print(dep_table)
            else:
                output_result(campaign.model_dump(), format)

    except CampaignNotFoundError:
        err_console.print(f"[red]Error:[/red] Campaign not found: {campaign_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_campaign_app.command("update")
def deprecate_campaign_update(
    campaign_id: Annotated[int, typer.Argument(help="Campaign ID.")],
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="New name.")
    ] = None,
    status: Annotated[
        str | None, typer.Option("--status", "-s", help="New status (draft, active, completed).")
    ] = None,
    target_date: Annotated[
        str | None, typer.Option("--target-date", "-t", help="New target date.")
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Update a campaign.

    Examples:
        datacompass deprecate campaign update 1 --status active
    """
    from datetime import date as dt_date

    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)

            parsed_date = dt_date.fromisoformat(target_date) if target_date else None

            campaign = deprecation_service.update_campaign(
                campaign_id=campaign_id,
                name=name,
                description=description,
                status=status,
                target_date=parsed_date,
            )
            session.commit()

            result = {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "target_date": str(campaign.target_date),
                "updated": True,
            }
            output_result(result, format)

    except CampaignNotFoundError:
        err_console.print(f"[red]Error:[/red] Campaign not found: {campaign_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_campaign_app.command("delete")
def deprecate_campaign_delete(
    campaign_id: Annotated[int, typer.Argument(help="Campaign ID.")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation.")
    ] = False,
) -> None:
    """Delete a campaign.

    Examples:
        datacompass deprecate campaign delete 1 --force
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)

            # Get campaign first to show name
            campaign = deprecation_service.get_campaign(campaign_id)

            if not force:
                confirm = typer.confirm(
                    f"Delete campaign '{campaign.name}' and all its deprecations?"
                )
                if not confirm:
                    raise typer.Abort()

            deprecation_service.delete_campaign(campaign_id)
            session.commit()
            console.print(f"[green]Deleted campaign:[/green] {campaign.name}")

    except typer.Abort:
        raise
    except CampaignNotFoundError:
        err_console.print(f"[red]Error:[/red] Campaign not found: {campaign_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_app.command("add")
def deprecate_add(
    object_id: Annotated[str, typer.Argument(help="Object identifier (source.schema.name).")],
    campaign: Annotated[
        int, typer.Option("--campaign", "-c", help="Campaign ID.")
    ],
    replacement: Annotated[
        str | None, typer.Option("--replacement", "-r", help="Replacement object identifier.")
    ] = None,
    notes: Annotated[
        str | None, typer.Option("--notes", "-n", help="Migration notes.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Add an object to a deprecation campaign.

    Examples:
        datacompass deprecate add demo.analytics.old_table --campaign 1
        datacompass deprecate add demo.analytics.old_table --campaign 1 --replacement demo.analytics.new_table
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)

            deprecation = deprecation_service.add_object_to_campaign(
                campaign_id=campaign,
                object_identifier=object_id,
                replacement_identifier=replacement,
                migration_notes=notes,
            )
            session.commit()

            result = {
                "deprecation_id": deprecation.id,
                "object": f"{deprecation.schema_name}.{deprecation.object_name}",
                "campaign_id": deprecation.campaign_id,
                "replacement": deprecation.replacement_name,
                "status": "added",
            }
            output_result(result, format)

    except CampaignNotFoundError as e:
        err_console.print(f"[red]Error:[/red] Campaign not found: {e.identifier}")
        raise typer.Exit(1) from None
    except ObjectNotFoundError:
        err_console.print(f"[red]Error:[/red] Object not found: {object_id!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_app.command("remove")
def deprecate_remove(
    deprecation_id: Annotated[int, typer.Argument(help="Deprecation ID.")],
) -> None:
    """Remove an object from a campaign.

    Examples:
        datacompass deprecate remove 1
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)
            deprecation_service.remove_object_from_campaign(deprecation_id)
            session.commit()
            console.print(f"[green]Removed deprecation:[/green] {deprecation_id}")

    except DeprecationNotFoundError:
        err_console.print(f"[red]Error:[/red] Deprecation not found: {deprecation_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_app.command("list")
def deprecate_list(
    campaign: Annotated[
        int | None, typer.Option("--campaign", "-c", help="Filter by campaign ID.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List deprecated objects.

    Examples:
        datacompass deprecate list
        datacompass deprecate list --campaign 1
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)
            deprecations = deprecation_service.list_deprecations(campaign_id=campaign)

            if format == OutputFormat.table:
                if not deprecations:
                    console.print("[dim]No deprecations found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Campaign ID", justify="right")
                table.add_column("Object")
                table.add_column("Type")
                table.add_column("Replacement")

                for dep in deprecations:
                    obj_name = f"{dep.schema_name}.{dep.object_name}"
                    table.add_row(
                        str(dep.id),
                        str(dep.campaign_id),
                        obj_name,
                        dep.object_type,
                        dep.replacement_name or "-",
                    )

                console.print(table)
            else:
                result = [d.model_dump() for d in deprecations]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@deprecate_app.command("check")
def deprecate_check(
    campaign_id: Annotated[int, typer.Argument(help="Campaign ID.")],
    depth: Annotated[
        int, typer.Option("--depth", "-d", help="Maximum traversal depth (1-10).")
    ] = 3,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Check downstream impact of a deprecation campaign.

    Uses lineage data to find all objects that depend on deprecated objects.

    Examples:
        datacompass deprecate check 1
        datacompass deprecate check 1 --depth 5 --format table
    """
    try:
        with get_session() as session:
            deprecation_service = DeprecationService(session)

            with console.status(f"Analyzing impact for campaign {campaign_id}..."):
                impact = deprecation_service.check_impact(campaign_id, depth=depth)

            if format == OutputFormat.table:
                console.print(f"\n[bold]Impact Analysis:[/bold] {impact.campaign_name}\n")
                console.print(f"Deprecated Objects: {impact.total_deprecated}")
                console.print(f"Total Impacted: {impact.total_impacted}\n")

                for dep_impact in impact.impacts:
                    console.print(f"[bold]{dep_impact.deprecated_object_name}[/bold] ({dep_impact.downstream_count} downstream)")

                    if dep_impact.impacted_objects:
                        table = Table(show_header=True, box=None)
                        table.add_column("Distance", justify="center")
                        table.add_column("Object")
                        table.add_column("Type")

                        for obj in dep_impact.impacted_objects:
                            table.add_row(
                                str(obj.distance),
                                obj.full_name,
                                obj.object_type,
                            )

                        console.print(table)
                    else:
                        console.print("[dim]  No downstream dependents.[/dim]")
                    console.print()
            else:
                output_result(impact.model_dump(), format)

    except CampaignNotFoundError:
        err_console.print(f"[red]Error:[/red] Campaign not found: {campaign_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Schedule commands
# =============================================================================


@schedule_app.command("list")
def schedule_list(
    job_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by job type (scan, dq_run, deprecation_check).")
    ] = None,
    enabled: Annotated[
        bool | None, typer.Option("--enabled", help="Filter by enabled status.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List scheduled jobs.

    Examples:
        datacompass schedule list
        datacompass schedule list --type scan
        datacompass schedule list --enabled --format table
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)
            schedules = service.list_schedules(
                job_type=job_type,
                enabled_only=enabled if enabled else False,
            )

            if format == OutputFormat.table:
                if not schedules:
                    console.print("[dim]No schedules found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Name")
                table.add_column("Type")
                table.add_column("Cron")
                table.add_column("Target")
                table.add_column("Enabled")
                table.add_column("Last Run")
                table.add_column("Status")

                for s in schedules:
                    enabled_str = "[green]Yes[/green]" if s.is_enabled else "[dim]No[/dim]"
                    last_run = str(s.last_run_at)[:16] if s.last_run_at else "-"
                    status = s.last_run_status or "-"
                    if status == "failed":
                        status = "[red]failed[/red]"
                    elif status == "success":
                        status = "[green]success[/green]"

                    table.add_row(
                        str(s.id),
                        s.name,
                        s.job_type,
                        s.cron_expression,
                        str(s.target_id) if s.target_id else "-",
                        enabled_str,
                        last_run,
                        status,
                    )

                console.print(table)
            else:
                result = [s.model_dump() for s in schedules]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("show")
def schedule_show(
    schedule_id: Annotated[int, typer.Argument(help="Schedule ID.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show schedule details.

    Examples:
        datacompass schedule show 1
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)
            schedule = service.get_schedule(schedule_id)

            if format == OutputFormat.table:
                console.print(f"\n[bold]Schedule #{schedule.id}:[/bold] {schedule.name}\n")

                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Job Type", schedule.job_type)
                table.add_row("Target ID", str(schedule.target_id) if schedule.target_id else "-")
                table.add_row("Cron", schedule.cron_expression)
                table.add_row("Timezone", schedule.timezone)
                table.add_row("Enabled", "Yes" if schedule.is_enabled else "No")
                table.add_row("Next Run", str(schedule.next_run_at) if schedule.next_run_at else "-")
                table.add_row("Last Run", str(schedule.last_run_at) if schedule.last_run_at else "-")
                table.add_row("Last Status", schedule.last_run_status or "-")
                table.add_row("Description", schedule.description or "-")
                console.print(table)

                if schedule.recent_runs:
                    console.print("\n[bold]Recent Runs:[/bold]\n")
                    runs_table = Table()
                    runs_table.add_column("ID", justify="right")
                    runs_table.add_column("Started")
                    runs_table.add_column("Completed")
                    runs_table.add_column("Status")

                    for run in schedule.recent_runs[:10]:
                        status = run.status
                        if status == "failed":
                            status = "[red]failed[/red]"
                        elif status == "success":
                            status = "[green]success[/green]"
                        elif status == "running":
                            status = "[yellow]running[/yellow]"

                        runs_table.add_row(
                            str(run.id),
                            str(run.started_at)[:19],
                            str(run.completed_at)[:19] if run.completed_at else "-",
                            status,
                        )

                    console.print(runs_table)
            else:
                output_result(schedule.model_dump(), format)

    except ScheduleNotFoundError:
        err_console.print(f"[red]Error:[/red] Schedule not found: {schedule_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("create")
def schedule_create(
    name: Annotated[str, typer.Argument(help="Schedule name.")],
    job_type: Annotated[
        str, typer.Option("--type", "-t", help="Job type (scan, dq_run, deprecation_check).")
    ],
    cron: Annotated[
        str, typer.Option("--cron", "-c", help="Cron expression (e.g., '0 6 * * *').")
    ],
    target: Annotated[
        int | None, typer.Option("--target", help="Target ID (source_id, config_id, or campaign_id).")
    ] = None,
    timezone: Annotated[
        str, typer.Option("--timezone", help="Timezone for cron.")
    ] = "UTC",
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a new scheduled job.

    Examples:
        datacompass schedule create "daily-scan" --type scan --cron "0 6 * * *" --target 1
        datacompass schedule create "dq-checks" --type dq_run --cron "0 7 * * *"
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)
            schedule = service.create_schedule(
                name=name,
                job_type=job_type,
                cron_expression=cron,
                target_id=target,
                timezone=timezone,
                description=description,
            )
            session.commit()

            result = {
                "id": schedule.id,
                "name": schedule.name,
                "job_type": schedule.job_type,
                "cron_expression": schedule.cron_expression,
                "status": "created",
            }
            output_result(result, format)

    except ScheduleExistsError as e:
        err_console.print(f"[red]Error:[/red] Schedule already exists: {e.name}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("update")
def schedule_update(
    schedule_id: Annotated[int, typer.Argument(help="Schedule ID.")],
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="New name.")
    ] = None,
    cron: Annotated[
        str | None, typer.Option("--cron", "-c", help="New cron expression.")
    ] = None,
    enabled: Annotated[
        bool | None, typer.Option("--enabled/--disabled", help="Enable or disable.")
    ] = None,
    timezone: Annotated[
        str | None, typer.Option("--timezone", help="New timezone.")
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Update a schedule.

    Examples:
        datacompass schedule update 1 --cron "0 8 * * *"
        datacompass schedule update 1 --disabled
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)
            schedule = service.update_schedule(
                schedule_id=schedule_id,
                name=name,
                cron_expression=cron,
                is_enabled=enabled,
                timezone=timezone,
                description=description,
            )
            session.commit()

            result = {
                "id": schedule.id,
                "name": schedule.name,
                "is_enabled": schedule.is_enabled,
                "status": "updated",
            }
            output_result(result, format)

    except ScheduleNotFoundError:
        err_console.print(f"[red]Error:[/red] Schedule not found: {schedule_id}")
        raise typer.Exit(1) from None
    except ScheduleExistsError as e:
        err_console.print(f"[red]Error:[/red] Schedule name already exists: {e.name}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("delete")
def schedule_delete(
    schedule_id: Annotated[int, typer.Argument(help="Schedule ID.")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation.")
    ] = False,
) -> None:
    """Delete a schedule.

    Examples:
        datacompass schedule delete 1 --force
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)

            # Get schedule first to show name
            schedule = service.get_schedule(schedule_id)

            if not force:
                confirm = typer.confirm(f"Delete schedule '{schedule.name}'?")
                if not confirm:
                    raise typer.Abort()

            service.delete_schedule(schedule_id)
            session.commit()
            console.print(f"[green]Deleted schedule:[/green] {schedule.name}")

    except typer.Abort:
        raise
    except ScheduleNotFoundError:
        err_console.print(f"[red]Error:[/red] Schedule not found: {schedule_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("run")
def schedule_run(
    schedule_id: Annotated[int, typer.Argument(help="Schedule ID.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Run a scheduled job immediately.

    Examples:
        datacompass schedule run 1
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)

            # Verify schedule exists
            schedule = service.get_schedule(schedule_id)

            console.print(f"Running job [bold]{schedule.name}[/bold]...")

        # Execute job (outside session context)
        from datacompass.core.scheduler.jobs import execute_job
        execute_job(schedule_id)

        result = {
            "schedule_id": schedule_id,
            "name": schedule.name,
            "status": "executed",
        }
        output_result(result, format)

    except ScheduleNotFoundError:
        err_console.print(f"[red]Error:[/red] Schedule not found: {schedule_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@schedule_app.command("apply")
def schedule_apply(
    config_file: Annotated[
        Path, typer.Argument(help="Path to schedules YAML file.")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Apply schedules from YAML configuration file.

    Examples:
        datacompass schedule apply schedules.yaml
    """
    try:
        with get_session() as session:
            service = SchedulingService(session)
            result = service.apply_from_yaml(config_file)
            session.commit()
            output_result(result, format)

    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] File not found: {config_file}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Scheduler daemon commands
# =============================================================================


@scheduler_app.command("start")
def scheduler_start(
    background: Annotated[
        bool, typer.Option("--background", "-b", help="Run in background.")
    ] = False,
) -> None:
    """Start the scheduler daemon.

    Examples:
        datacompass scheduler start
        datacompass scheduler start --background
    """
    try:
        from datacompass.core.scheduler import DataCompassScheduler

        console.print("[bold]Starting Data Compass scheduler...[/bold]")
        console.print("Press Ctrl+C to stop.\n")

        scheduler = DataCompassScheduler()
        scheduler.start(blocking=not background)

        if background:
            console.print("[green]Scheduler started in background.[/green]")

    except ImportError:
        err_console.print(
            "[red]Error:[/red] APScheduler not installed. "
            "Install with: pip install 'datacompass[scheduler]'"
        )
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped.[/yellow]")
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@scheduler_app.command("status")
def scheduler_status(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show scheduler status.

    Examples:
        datacompass scheduler status
    """
    try:
        from datacompass.core.scheduler.scheduler import get_scheduler

        scheduler = get_scheduler()
        status = scheduler.get_status()

        if format == OutputFormat.table:
            console.print(f"\n[bold]Scheduler Status[/bold]\n")
            console.print(f"Running: {'[green]Yes[/green]' if status['running'] else '[dim]No[/dim]'}")
            console.print(f"Jobs: {status['job_count']}")

            if status['jobs']:
                console.print("\n[bold]Active Jobs:[/bold]")
                for job in status['jobs']:
                    next_run = job['next_run_time'] or 'N/A'
                    console.print(f"  - {job['name']}: next run at {next_run}")
        else:
            output_result(status, format)

    except ImportError:
        err_console.print(
            "[red]Error:[/red] APScheduler not installed. "
            "Install with: pip install 'datacompass[scheduler]'"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Notification commands
# =============================================================================

# Create subcommands for channels and rules
notify_channel_app = typer.Typer(
    help="Manage notification channels.",
    no_args_is_help=True,
)
notify_rule_app = typer.Typer(
    help="Manage notification rules.",
    no_args_is_help=True,
)
notify_app.add_typer(notify_channel_app, name="channel")
notify_app.add_typer(notify_rule_app, name="rule")


@notify_channel_app.command("list")
def notify_channel_list(
    channel_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by type (email, slack, webhook).")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List notification channels.

    Examples:
        datacompass notify channel list
        datacompass notify channel list --type slack
    """
    try:
        with get_session() as session:
            service = NotificationService(session)
            channels = service.list_channels(channel_type=channel_type)

            if format == OutputFormat.table:
                if not channels:
                    console.print("[dim]No channels found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Name")
                table.add_column("Type")
                table.add_column("Enabled")

                for c in channels:
                    enabled = "[green]Yes[/green]" if c.is_enabled else "[dim]No[/dim]"
                    table.add_row(str(c.id), c.name, c.channel_type, enabled)

                console.print(table)
            else:
                result = [c.model_dump() for c in channels]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_channel_app.command("create")
def notify_channel_create(
    name: Annotated[str, typer.Argument(help="Channel name.")],
    channel_type: Annotated[
        str, typer.Option("--type", "-t", help="Channel type (email, slack, webhook).")
    ],
    config: Annotated[
        str, typer.Option("--config", "-c", help="Channel config as JSON string.")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a notification channel.

    Examples:
        datacompass notify channel create "slack-alerts" --type slack --config '{"webhook_url": "https://..."}'
    """
    try:
        config_dict = json.loads(config)

        with get_session() as session:
            service = NotificationService(session)
            channel = service.create_channel(
                name=name,
                channel_type=channel_type,
                config=config_dict,
            )
            session.commit()

            result = {
                "id": channel.id,
                "name": channel.name,
                "channel_type": channel.channel_type,
                "status": "created",
            }
            output_result(result, format)

    except json.JSONDecodeError:
        err_console.print("[red]Error:[/red] Invalid JSON config")
        raise typer.Exit(1) from None
    except ChannelExistsError as e:
        err_console.print(f"[red]Error:[/red] Channel already exists: {e.name}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_channel_app.command("test")
def notify_channel_test(
    channel_id: Annotated[int, typer.Argument(help="Channel ID.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Test a notification channel.

    Examples:
        datacompass notify channel test 1
    """
    try:
        with get_session() as session:
            service = NotificationService(session)
            result = service.test_channel(channel_id)

            output = {
                "channel_id": channel_id,
                "success": result.success,
                "error_message": result.error_message,
            }

            if format == OutputFormat.table:
                if result.success:
                    console.print(f"[green]Channel test successful[/green]")
                else:
                    console.print(f"[red]Channel test failed:[/red] {result.error_message}")
            else:
                output_result(output, format)

    except ChannelNotFoundError:
        err_console.print(f"[red]Error:[/red] Channel not found: {channel_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_channel_app.command("delete")
def notify_channel_delete(
    channel_id: Annotated[int, typer.Argument(help="Channel ID.")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation.")
    ] = False,
) -> None:
    """Delete a notification channel.

    Examples:
        datacompass notify channel delete 1 --force
    """
    try:
        with get_session() as session:
            service = NotificationService(session)

            # Get channel first to show name
            channel = service.get_channel(channel_id)

            if not force:
                confirm = typer.confirm(f"Delete channel '{channel.name}'?")
                if not confirm:
                    raise typer.Abort()

            service.delete_channel(channel_id)
            session.commit()
            console.print(f"[green]Deleted channel:[/green] {channel.name}")

    except typer.Abort:
        raise
    except ChannelNotFoundError:
        err_console.print(f"[red]Error:[/red] Channel not found: {channel_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_rule_app.command("list")
def notify_rule_list(
    event_type: Annotated[
        str | None, typer.Option("--event", "-e", help="Filter by event type.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List notification rules.

    Examples:
        datacompass notify rule list
        datacompass notify rule list --event dq_breach
    """
    try:
        with get_session() as session:
            service = NotificationService(session)
            rules = service.list_rules(event_type=event_type)

            if format == OutputFormat.table:
                if not rules:
                    console.print("[dim]No rules found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Name")
                table.add_column("Event")
                table.add_column("Channel")
                table.add_column("Enabled")

                for r in rules:
                    enabled = "[green]Yes[/green]" if r.is_enabled else "[dim]No[/dim]"
                    table.add_row(
                        str(r.id),
                        r.name,
                        r.event_type,
                        f"{r.channel_name} ({r.channel_type})",
                        enabled,
                    )

                console.print(table)
            else:
                result = [r.model_dump() for r in rules]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_rule_app.command("create")
def notify_rule_create(
    name: Annotated[str, typer.Argument(help="Rule name.")],
    event: Annotated[
        str, typer.Option("--event", "-e", help="Event type (dq_breach, scan_failed, scan_completed, deprecation_deadline).")
    ],
    channel: Annotated[
        int, typer.Option("--channel", "-c", help="Channel ID.")
    ],
    conditions: Annotated[
        str | None, typer.Option("--conditions", help="Conditions as JSON string.")
    ] = None,
    template: Annotated[
        str | None, typer.Option("--template", help="Custom message template.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a notification rule.

    Examples:
        datacompass notify rule create "breach-alerts" --event dq_breach --channel 1
        datacompass notify rule create "critical-only" --event dq_breach --channel 1 --conditions '{"priority": "critical"}'
    """
    try:
        conditions_dict = json.loads(conditions) if conditions else None

        with get_session() as session:
            service = NotificationService(session)
            rule = service.create_rule(
                name=name,
                event_type=event,
                channel_id=channel,
                conditions=conditions_dict,
                template_override=template,
            )
            session.commit()

            result = {
                "id": rule.id,
                "name": rule.name,
                "event_type": rule.event_type,
                "channel_id": rule.channel_id,
                "status": "created",
            }
            output_result(result, format)

    except json.JSONDecodeError:
        err_console.print("[red]Error:[/red] Invalid JSON conditions")
        raise typer.Exit(1) from None
    except ChannelNotFoundError:
        err_console.print(f"[red]Error:[/red] Channel not found: {channel}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_rule_app.command("delete")
def notify_rule_delete(
    rule_id: Annotated[int, typer.Argument(help="Rule ID.")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation.")
    ] = False,
) -> None:
    """Delete a notification rule.

    Examples:
        datacompass notify rule delete 1 --force
    """
    try:
        with get_session() as session:
            service = NotificationService(session)

            # Get rule first to show name
            rule = service.get_rule(rule_id)

            if not force:
                confirm = typer.confirm(f"Delete rule '{rule.name}'?")
                if not confirm:
                    raise typer.Abort()

            service.delete_rule(rule_id)
            session.commit()
            console.print(f"[green]Deleted rule:[/green] {rule.name}")

    except typer.Abort:
        raise
    except RuleNotFoundError:
        err_console.print(f"[red]Error:[/red] Rule not found: {rule_id}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_app.command("log")
def notify_log(
    event_type: Annotated[
        str | None, typer.Option("--event", "-e", help="Filter by event type.")
    ] = None,
    status: Annotated[
        str | None, typer.Option("--status", "-s", help="Filter by status (sent, failed).")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum results.")
    ] = 50,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """View notification log.

    Examples:
        datacompass notify log
        datacompass notify log --status failed
    """
    try:
        with get_session() as session:
            service = NotificationService(session)
            logs = service.get_notification_log(
                event_type=event_type,
                status=status,
                limit=limit,
            )

            if format == OutputFormat.table:
                if not logs:
                    console.print("[dim]No notifications found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Event")
                table.add_column("Status")
                table.add_column("Sent At")
                table.add_column("Error")

                for log in logs:
                    status_str = log.status
                    if status_str == "failed":
                        status_str = "[red]failed[/red]"
                    elif status_str == "sent":
                        status_str = "[green]sent[/green]"

                    error = log.error_message[:30] + "..." if log.error_message and len(log.error_message) > 30 else (log.error_message or "-")

                    table.add_row(
                        str(log.id),
                        log.event_type,
                        status_str,
                        str(log.sent_at)[:19],
                        error,
                    )

                console.print(table)
            else:
                result = [log.model_dump() for log in logs]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@notify_app.command("apply")
def notify_apply(
    config_file: Annotated[
        Path, typer.Argument(help="Path to notifications YAML file.")
    ],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Apply notification configuration from YAML file.

    Examples:
        datacompass notify apply notifications.yaml
    """
    try:
        with get_session() as session:
            service = NotificationService(session)
            result = service.apply_from_yaml(config_file)
            session.commit()
            output_result(result, format)

    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] File not found: {config_file}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Auth commands
# =============================================================================


def _get_credentials_path() -> Path:
    """Get path to credentials file."""
    from datacompass.config.settings import get_settings

    settings = get_settings()
    return settings.data_dir / ".credentials"


def _store_credentials(access_token: str, refresh_token: str) -> None:
    """Store credentials to file with secure permissions."""
    creds_path = _get_credentials_path()
    creds_path.parent.mkdir(parents=True, exist_ok=True)

    creds_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    creds_path.write_text(json.dumps(creds_data))
    creds_path.chmod(0o600)


def _get_stored_credentials() -> dict | None:
    """Get stored credentials if they exist."""
    creds_path = _get_credentials_path()
    if not creds_path.exists():
        return None

    try:
        return json.loads(creds_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _clear_credentials() -> None:
    """Clear stored credentials."""
    creds_path = _get_credentials_path()
    if creds_path.exists():
        creds_path.unlink()


def _get_current_user(session):
    """Get current user from stored token or environment.

    Returns (user, auth_service) tuple or (None, auth_service) if not authenticated.
    """
    import os

    auth_service = AuthService(session)

    # Check environment for API key
    api_key = os.environ.get("DATACOMPASS_API_KEY")
    if api_key:
        try:
            user = auth_service.authenticate_api_key(api_key)
            return user, auth_service
        except AuthServiceError:
            pass

    # Check environment for access token
    access_token = os.environ.get("DATACOMPASS_ACCESS_TOKEN")
    if access_token:
        try:
            user = auth_service.validate_access_token(access_token)
            return user, auth_service
        except AuthServiceError:
            pass

    # Check stored credentials
    creds = _get_stored_credentials()
    if creds:
        try:
            user = auth_service.validate_access_token(creds.get("access_token", ""))
            return user, auth_service
        except TokenExpiredError:
            # Try to refresh
            try:
                response = auth_service.refresh_tokens(creds.get("refresh_token", ""))
                _store_credentials(response.access_token, response.refresh_token)
                user = auth_service.validate_access_token(response.access_token)
                return user, auth_service
            except AuthServiceError:
                _clear_credentials()
        except AuthServiceError:
            pass

    return None, auth_service


@auth_app.command("login")
def auth_login(
    email: Annotated[
        str | None, typer.Option("--email", "-e", help="Email address.")
    ] = None,
    password: Annotated[
        str | None, typer.Option("--password", "-p", help="Password (will prompt if not provided).")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Login and store credentials.

    Examples:
        datacompass auth login --email user@example.com
        datacompass auth login -e user@example.com -p secret
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)

            # Prompt for email if not provided
            if not email:
                email = typer.prompt("Email")

            # Prompt for password if not provided
            if not password:
                password = typer.prompt("Password", hide_input=True)

            response = auth_service.authenticate(email, password)
            session.commit()

            # Store credentials
            _store_credentials(response.access_token, response.refresh_token)

            if format == OutputFormat.table:
                console.print("[green]Login successful![/green]")
                console.print(f"[dim]Credentials stored at {_get_credentials_path()}[/dim]")
            else:
                output_result({
                    "success": True,
                    "message": "Login successful",
                    "expires_in": response.expires_in,
                }, format)

    except AuthDisabledError:
        err_console.print("[yellow]Authentication is disabled.[/yellow]")
        err_console.print("[dim]Set DATACOMPASS_AUTH_MODE=local to enable.[/dim]")
        raise typer.Exit(1) from None
    except InvalidCredentialsError as e:
        err_console.print(f"[red]Error:[/red] {e.message}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_app.command("logout")
def auth_logout(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Logout and clear stored credentials.

    Examples:
        datacompass auth logout
    """
    _clear_credentials()

    if format == OutputFormat.table:
        console.print("[green]Logged out successfully.[/green]")
    else:
        output_result({"success": True, "message": "Logged out"}, format)


@auth_app.command("whoami")
def auth_whoami(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show current authenticated user.

    Examples:
        datacompass auth whoami
    """
    try:
        with get_session() as session:
            user, auth_service = _get_current_user(session)

            status = auth_service.get_auth_status()

            if status["auth_mode"] == "disabled":
                if format == OutputFormat.table:
                    console.print("[yellow]Authentication is disabled.[/yellow]")
                else:
                    output_result({
                        "auth_mode": "disabled",
                        "is_authenticated": False,
                    }, format)
                return

            if user is None:
                if format == OutputFormat.table:
                    console.print("[dim]Not authenticated.[/dim]")
                    console.print("[dim]Use 'datacompass auth login' to authenticate.[/dim]")
                else:
                    output_result({
                        "auth_mode": status["auth_mode"],
                        "is_authenticated": False,
                    }, format)
                raise typer.Exit(1)

            if format == OutputFormat.table:
                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Email", user.email)
                table.add_row("Display Name", user.display_name or "-")
                table.add_row("Superuser", "Yes" if user.is_superuser else "No")
                table.add_row("Last Login", str(user.last_login_at)[:19] if user.last_login_at else "-")
                console.print(table)
            else:
                from datacompass.core.models.auth import UserResponse
                output_result({
                    "auth_mode": status["auth_mode"],
                    "is_authenticated": True,
                    "user": UserResponse.model_validate(user).model_dump(),
                }, format)

    except AuthDisabledError:
        if format == OutputFormat.table:
            console.print("[yellow]Authentication is disabled.[/yellow]")
        else:
            output_result({"auth_mode": "disabled", "is_authenticated": False}, format)
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_app.command("status")
def auth_status(
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show authentication mode and configuration.

    Examples:
        datacompass auth status
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            status = auth_service.get_auth_status()

            if format == OutputFormat.table:
                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Auth Mode", status["auth_mode"])
                table.add_row("Auth Enabled", "Yes" if status["auth_enabled"] else "No")
                if status["auth_enabled"]:
                    table.add_row("Supports Local Auth", "Yes" if status["supports_local_auth"] else "No")
                    table.add_row("Access Token Expiry", f"{status['access_token_expire_minutes']} minutes")
                    table.add_row("Refresh Token Expiry", f"{status['refresh_token_expire_days']} days")
                console.print(table)
            else:
                output_result(status, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Auth API Key commands
# =============================================================================


@auth_apikey_app.command("create")
def auth_apikey_create(
    name: Annotated[str, typer.Argument(help="Name for the API key.")],
    scopes: Annotated[
        str | None, typer.Option("--scopes", "-s", help="Comma-separated list of scopes.")
    ] = None,
    expires_days: Annotated[
        int | None, typer.Option("--expires-days", "-d", help="Expiration in days.")
    ] = None,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a new API key.

    Examples:
        datacompass auth apikey create "CI/CD Key" --scopes read,write
        datacompass auth apikey create "Temp Key" --expires-days 30
    """
    try:
        with get_session() as session:
            user, auth_service = _get_current_user(session)

            if user is None:
                err_console.print("[red]Error:[/red] Not authenticated.")
                err_console.print("[dim]Use 'datacompass auth login' first.[/dim]")
                raise typer.Exit(1)

            scope_list = None
            if scopes:
                scope_list = [s.strip() for s in scopes.split(",")]

            api_key = auth_service.create_api_key(
                user=user,
                name=name,
                scopes=scope_list,
                expires_days=expires_days,
            )
            session.commit()

            if format == OutputFormat.table:
                console.print("\n[bold green]API key created![/bold green]\n")
                console.print("[bold yellow]Important:[/bold yellow] Copy the key now. It won't be shown again.\n")

                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("Key", api_key.key)
                table.add_row("ID", str(api_key.id))
                table.add_row("Name", api_key.name)
                table.add_row("Prefix", api_key.key_prefix)
                table.add_row("Scopes", ", ".join(api_key.scopes) if api_key.scopes else "-")
                table.add_row("Expires", str(api_key.expires_at)[:19] if api_key.expires_at else "Never")
                console.print(table)
            else:
                output_result(api_key.model_dump(), format)

    except AuthDisabledError:
        err_console.print("[yellow]Authentication is disabled.[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_apikey_app.command("list")
def auth_apikey_list(
    include_inactive: Annotated[
        bool, typer.Option("--include-inactive", help="Include revoked keys.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List API keys.

    Examples:
        datacompass auth apikey list
        datacompass auth apikey list --include-inactive
    """
    try:
        with get_session() as session:
            user, auth_service = _get_current_user(session)

            if user is None:
                err_console.print("[red]Error:[/red] Not authenticated.")
                err_console.print("[dim]Use 'datacompass auth login' first.[/dim]")
                raise typer.Exit(1)

            keys = auth_service.list_api_keys(user, include_inactive=include_inactive)

            if format == OutputFormat.table:
                if not keys:
                    console.print("[dim]No API keys found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Name")
                table.add_column("Prefix")
                table.add_column("Scopes")
                table.add_column("Expires")
                table.add_column("Last Used")
                table.add_column("Active")

                for key in keys:
                    active = "[green]Yes[/green]" if key.is_active else "[red]No[/red]"
                    scopes = ", ".join(key.scopes) if key.scopes else "-"
                    expires = str(key.expires_at)[:10] if key.expires_at else "Never"
                    last_used = str(key.last_used_at)[:19] if key.last_used_at else "-"

                    table.add_row(
                        str(key.id),
                        key.name,
                        key.key_prefix,
                        scopes,
                        expires,
                        last_used,
                        active,
                    )

                console.print(table)
            else:
                from datacompass.core.models.auth import APIKeyResponse
                result = [APIKeyResponse.model_validate(k).model_dump() for k in keys]
                output_result(result, format)

    except AuthDisabledError:
        err_console.print("[yellow]Authentication is disabled.[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_apikey_app.command("revoke")
def auth_apikey_revoke(
    key_id: Annotated[int, typer.Argument(help="API key ID to revoke.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Revoke an API key.

    Examples:
        datacompass auth apikey revoke 1
    """
    try:
        with get_session() as session:
            user, auth_service = _get_current_user(session)

            if user is None:
                err_console.print("[red]Error:[/red] Not authenticated.")
                err_console.print("[dim]Use 'datacompass auth login' first.[/dim]")
                raise typer.Exit(1)

            api_key = auth_service.revoke_api_key(key_id, user)
            session.commit()

            if format == OutputFormat.table:
                console.print(f"[green]API key {key_id} ({api_key.name}) revoked.[/green]")
            else:
                output_result({"success": True, "key_id": key_id, "message": "API key revoked"}, format)

    except APIKeyNotFoundError:
        err_console.print(f"[red]Error:[/red] API key not found: {key_id}")
        raise typer.Exit(1) from None
    except AuthDisabledError:
        err_console.print("[yellow]Authentication is disabled.[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


# =============================================================================
# Auth User commands (admin)
# =============================================================================


@auth_user_app.command("create")
def auth_user_create(
    email: Annotated[str, typer.Argument(help="User email address.")],
    password: Annotated[
        bool, typer.Option("--password", "-p", help="Prompt for password.")
    ] = False,
    display_name: Annotated[
        str | None, typer.Option("--display-name", "-n", help="Display name.")
    ] = None,
    superuser: Annotated[
        bool, typer.Option("--superuser", help="Grant superuser privileges.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Create a new user.

    Examples:
        datacompass auth user create admin@example.com --password --superuser
        datacompass auth user create user@example.com --display-name "John Doe"
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)

            # Prompt for password if flag is set
            user_password = None
            if password:
                user_password = typer.prompt("Password", hide_input=True)
                password_confirm = typer.prompt("Confirm Password", hide_input=True)
                if user_password != password_confirm:
                    err_console.print("[red]Error:[/red] Passwords do not match.")
                    raise typer.Exit(1)

            user_data = UserCreate(
                email=email,
                password=user_password,
                display_name=display_name,
                is_superuser=superuser,
            )

            user = auth_service.create_local_user(user_data)
            session.commit()

            if format == OutputFormat.table:
                console.print(f"[green]User created:[/green] {user.email}")
                if superuser:
                    console.print("[dim]Superuser privileges granted.[/dim]")
            else:
                from datacompass.core.models.auth import UserResponse
                output_result(UserResponse.model_validate(user).model_dump(), format)

    except UserExistsError as e:
        err_console.print(f"[red]Error:[/red] User already exists: {e.email}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_user_app.command("list")
def auth_user_list(
    include_inactive: Annotated[
        bool, typer.Option("--include-inactive", help="Include disabled users.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """List all users.

    Examples:
        datacompass auth user list
        datacompass auth user list --include-inactive
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            users = auth_service.list_users(include_inactive=include_inactive)

            if format == OutputFormat.table:
                if not users:
                    console.print("[dim]No users found.[/dim]")
                    return

                table = Table()
                table.add_column("ID", justify="right")
                table.add_column("Email")
                table.add_column("Display Name")
                table.add_column("Superuser")
                table.add_column("Active")
                table.add_column("Last Login")

                for user in users:
                    active = "[green]Yes[/green]" if user.is_active else "[red]No[/red]"
                    superuser = "[cyan]Yes[/cyan]" if user.is_superuser else "No"
                    last_login = str(user.last_login_at)[:19] if user.last_login_at else "-"

                    table.add_row(
                        str(user.id),
                        user.email,
                        user.display_name or "-",
                        superuser,
                        active,
                        last_login,
                    )

                console.print(table)
            else:
                from datacompass.core.models.auth import UserResponse
                result = [UserResponse.model_validate(u).model_dump() for u in users]
                output_result(result, format)

    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_user_app.command("show")
def auth_user_show(
    email: Annotated[str, typer.Argument(help="User email address.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Show user details.

    Examples:
        datacompass auth user show admin@example.com
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            user = auth_service.get_user_by_email(email)

            if format == OutputFormat.table:
                table = Table(show_header=False)
                table.add_column("Key", style="bold")
                table.add_column("Value")
                table.add_row("ID", str(user.id))
                table.add_row("Email", user.email)
                table.add_row("Username", user.username or "-")
                table.add_row("Display Name", user.display_name or "-")
                table.add_row("External Provider", user.external_provider or "-")
                table.add_row("Superuser", "Yes" if user.is_superuser else "No")
                table.add_row("Active", "Yes" if user.is_active else "No")
                table.add_row("Last Login", str(user.last_login_at)[:19] if user.last_login_at else "-")
                table.add_row("Created", str(user.created_at)[:19])
                console.print(table)
            else:
                from datacompass.core.models.auth import UserResponse
                output_result(UserResponse.model_validate(user).model_dump(), format)

    except UserNotFoundError:
        err_console.print(f"[red]Error:[/red] User not found: {email!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_user_app.command("disable")
def auth_user_disable(
    email: Annotated[str, typer.Argument(help="User email address.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Disable a user account.

    Examples:
        datacompass auth user disable user@example.com
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            user = auth_service.disable_user(email)
            session.commit()

            if format == OutputFormat.table:
                console.print(f"[green]User disabled:[/green] {email}")
                console.print("[dim]All sessions and tokens have been invalidated.[/dim]")
            else:
                output_result({"success": True, "email": email, "message": "User disabled"}, format)

    except UserNotFoundError:
        err_console.print(f"[red]Error:[/red] User not found: {email!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_user_app.command("enable")
def auth_user_enable(
    email: Annotated[str, typer.Argument(help="User email address.")],
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Enable a user account.

    Examples:
        datacompass auth user enable user@example.com
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            user = auth_service.enable_user(email)
            session.commit()

            if format == OutputFormat.table:
                console.print(f"[green]User enabled:[/green] {email}")
            else:
                output_result({"success": True, "email": email, "message": "User enabled"}, format)

    except UserNotFoundError:
        err_console.print(f"[red]Error:[/red] User not found: {email!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


@auth_user_app.command("set-superuser")
def auth_user_set_superuser(
    email: Annotated[str, typer.Argument(help="User email address.")],
    remove: Annotated[
        bool, typer.Option("--remove", help="Remove superuser privileges.")
    ] = False,
    format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.json,
) -> None:
    """Grant or revoke superuser privileges.

    Examples:
        datacompass auth user set-superuser admin@example.com
        datacompass auth user set-superuser admin@example.com --remove
    """
    try:
        with get_session() as session:
            auth_service = AuthService(session)
            is_superuser = not remove
            user = auth_service.set_superuser(email, is_superuser)
            session.commit()

            if format == OutputFormat.table:
                if is_superuser:
                    console.print(f"[green]Superuser privileges granted to:[/green] {email}")
                else:
                    console.print(f"[green]Superuser privileges removed from:[/green] {email}")
            else:
                action = "granted" if is_superuser else "removed"
                output_result({
                    "success": True,
                    "email": email,
                    "is_superuser": is_superuser,
                    "message": f"Superuser privileges {action}",
                }, format)

    except UserNotFoundError:
        err_console.print(f"[red]Error:[/red] User not found: {email!r}")
        raise typer.Exit(1) from None
    except Exception as e:
        code = handle_error(e)
        raise typer.Exit(code) from None


if __name__ == "__main__":
    app()
