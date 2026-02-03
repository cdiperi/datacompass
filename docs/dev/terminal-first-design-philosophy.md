# Terminal-First Design Philosophy: Data Catalog & Governance Platform

## Guiding Principle

Build the engine before the cockpit. Every capability this platform offers should work without a browser. The web app is a window into the system, not the system itself.

---

## Phase Mindset

### Phase 1: CLI Core — Make it work in the terminal

Everything starts as a command. If a user can't accomplish a task by typing a command and reading output, the feature isn't ready. This forces clean separation between logic and presentation from day one.

The CLI is not a throwaway prototype. It is a first-class product surface that data engineers will use directly in scripts, pipelines, and automation workflows. Design it with the same care you'd give an API.

### Phase 2: API Layer — Expose the core over HTTP

The API should feel like a thin translation layer between the CLI internals and the outside world. If adding an endpoint requires significant new logic that doesn't exist in the CLI path, that's a sign the core is incomplete. Go back and add the capability to the core first, then expose it.

### Phase 3: Web Interface — Visualize, browse, collaborate

The web layer exists for things terminals are bad at: interactive graph exploration, search with faceted filtering, collaborative annotation, and at-a-glance dashboards. The frontend calls the same API the CLI could call. No special backend routes that only the web app knows about.

---

## Architectural Boundaries

### The Core Library is the product

There should be a core library (package, module, whatever the language provides) that contains all business logic: scanning, metadata extraction, quality rule evaluation, lineage parsing, documentation generation. Both the CLI and the API import this library. Neither contains business logic of their own.

If you find yourself writing an `if` statement that decides how data governance works inside a CLI command handler or an API route, stop. That logic belongs in the core.

### CLI commands map to capabilities, not screens

Don't design CLI commands by thinking "what pages will the web app have." Design them by thinking "what actions does a user need to perform against their data ecosystem." Examples:

- Scan a source and ingest metadata
- Run quality checks against a dataset
- Trace lineage for a specific table or column
- Generate or update documentation
- Search the catalog
- Export a report

Each of these is a self-contained capability. Each one should be invocable, scriptable, and composable.

### Output is data, not decoration

CLI output should default to structured formats (JSON, YAML) that are parseable by other tools. Human-friendly tables and summaries are a display mode, not the primary output. This makes the CLI immediately useful in pipelines and makes the API layer trivial — you're already producing the response shape.

---

## Design Decisions to Make Early

### Configuration over conversation

The platform should be driven by configuration files (catalog sources, quality rules, scan schedules, documentation templates). A user should be able to define their entire governance setup in version-controlled config files and apply it with a single command. The web app can generate and edit these configs, but the configs are the source of truth.

### Plugin architecture for sources

Every data source connector (Oracle, Postgres, Snowflake, S3, dbt, Spark, etc.) should be a plugin with a standard interface. The core doesn't know how to talk to Oracle. It knows how to talk to a "source plugin" that happens to understand Oracle. This is critical for extensibility and keeps the core lean.

### Idempotent operations

Every scan, quality check, and documentation generation should be safely re-runnable. Running the same command twice produces the same result without duplicating data or corrupting state. This is non-negotiable for automation and pipeline integration.

### Local-first storage to start

Begin with local storage (SQLite, file-based) for the metadata catalog. Don't start with a Postgres dependency. A user should be able to `pip install` the tool and run `catalog scan` against a database within minutes. The web platform can introduce a proper database later, but the CLI should work with zero infrastructure.

---

## What the Web Layer Should Own

The web app earns its existence by providing things the terminal cannot:

- **Interactive lineage visualization** — Graph exploration with zoom, filter, and click-to-trace that would be meaningless as text output
- **Search and discovery** — Faceted, full-text search with previews that makes browsing a large catalog fast and intuitive
- **Collaborative features** — Comments, annotations, ownership assignments, review workflows where multiple humans interact
- **Dashboards and monitoring** — At-a-glance health of data quality, scan coverage, documentation completeness
- **Configuration UI** — A guided way to set up sources, define rules, and manage the platform for users who aren't comfortable editing YAML

If a web feature doesn't fall into one of these categories, seriously question whether it should exist as a web page at all or whether it's better served by the CLI.

---

## Testing Philosophy

If the core works, the CLI works. If the CLI works, the API works. If the API works, the web app works. Test from the inside out. The deepest and most rigorous tests should be on the core library. Integration tests should exercise the CLI. API tests confirm the translation layer. Frontend tests confirm rendering and interaction.

Never test business logic through the web layer. If your only test for "quality rule X catches null values" involves spinning up a browser, the architecture has gone wrong.

---

## Summary of Non-Negotiable Principles

1. **The core library is the product.** Everything else is an interface to it.
2. **Every feature works headlessly first.** No capability should require a browser to function.
3. **Output is structured data by default.** Human formatting is a presentation choice, not the native format.
4. **Configuration is code.** The governance setup lives in version-controlled files, not trapped in a database.
5. **Connectors are plugins.** The core is source-agnostic.
6. **Operations are idempotent.** Safe to re-run, safe to automate.
7. **The web layer visualizes and collaborates.** It doesn't contain logic the CLI can't access.
