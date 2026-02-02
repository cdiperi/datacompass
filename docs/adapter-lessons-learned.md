# Adapter Implementation: Lessons Learned

Real-world issues encountered while implementing the PostgreSQL adapter and onboarding a test database.

---

## 1. SecretStr Serialization Bug

**Problem:** Passwords stored as `**********` in the database, causing authentication failures.

**Root Cause:** `SourceService.add_source()` used `model_dump(mode="json")` to serialize the config before storing. Pydantic's JSON mode masks `SecretStr` fields by design.

**Fix:** Created a custom serialization function that exposes secrets:

```python
def _serialize_config_with_secrets(model: BaseModel) -> dict[str, Any]:
    """Serialize a Pydantic model, exposing SecretStr values."""
    result: dict[str, Any] = {}
    for field_name, field_value in model:
        if isinstance(field_value, SecretStr):
            result[field_name] = field_value.get_secret_value()
        elif isinstance(field_value, Enum):
            result[field_name] = field_value.value
        elif isinstance(field_value, BaseModel):
            result[field_name] = _serialize_config_with_secrets(field_value)
        else:
            result[field_name] = field_value
    return result
```

**Lesson:** Always test the full add→store→retrieve→connect flow, not just individual components.

---

## 2. information_schema vs pg_catalog Permissions

**Problem:** Foreign key and view dependency queries returned empty results despite data existing.

**Root Cause:** PostgreSQL's `information_schema` views apply stricter permission filtering - they only show objects the current user owns or has explicit privileges on. The `datacompass` user had SELECT but not ownership.

**Fix:** Use `pg_catalog` system tables instead, which have less restrictive access:

```python
# Instead of information_schema.table_constraints (returned 0 rows)
# Use pg_constraint directly:
query = """
    SELECT
        tc.conname AS constraint_name,
        src_ns.nspname AS source_schema,
        src_tbl.relname AS source_table,
        ...
    FROM pg_constraint tc
    JOIN pg_class src_tbl ON tc.conrelid = src_tbl.oid
    JOIN pg_namespace src_ns ON src_tbl.relnamespace = src_ns.oid
    ...
    WHERE tc.contype = 'f'
"""

# Instead of information_schema.view_table_usage (returned 0 rows)
# Use pg_depend:
query = """
    SELECT DISTINCT
        dependent_ns.nspname AS view_schema,
        dependent_view.relname AS view_name,
        source_ns.nspname AS source_schema,
        source_table.relname AS source_table
    FROM pg_depend
    JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
    JOIN pg_class AS dependent_view ON pg_rewrite.ev_class = dependent_view.oid
    ...
"""
```

**Lesson:** Test with a non-superuser account that mirrors production permissions.

---

## 3. Lineage Methods Not Called During Scan

**Problem:** Adapter had `get_foreign_keys()` and `get_view_dependencies()` methods, but lineage was empty after scan.

**Root Cause:** These methods were defined but never called - the `CatalogService.scan_source()` only called `get_objects()` and `get_columns()`.

**Fix:** Added lineage extraction to the scan process:

```python
async def _extract_lineage(self, adapter: Any, source_id: int) -> None:
    """Extract lineage from adapter if supported."""
    dependencies: list[dict[str, Any]] = []

    # Check if adapter supports FK extraction
    try:
        if hasattr(adapter, "get_foreign_keys") and callable(adapter.get_foreign_keys):
            fks = await adapter.get_foreign_keys()
            if isinstance(fks, list):
                for fk in fks:
                    # Resolve to object IDs and add to dependencies
                    ...
    except (TypeError, AttributeError):
        pass  # Adapter doesn't support this

    # Similar for view dependencies...
```

**Lesson:** New adapter capabilities need integration points in the service layer, not just the adapter itself.

---

## 4. Network Configuration (pg_hba.conf)

**Problem:** Connection refused with "no pg_hba.conf entry for host" error.

**Root Cause:** PostgreSQL's host-based authentication requires explicit rules for each client IP/subnet.

**Fix:** Added rule for the client's subnet:
```
# /etc/postgresql/*/main/pg_hba.conf
host    all    all    192.168.100.0/24    scram-sha-256
```

**Lesson:** Document network requirements. Test connectivity with `nc -zv <host> <port>` before debugging application code.

---

## 5. Config File Location and Secrets

**Problem:** Created config file with plaintext password in project root.

**Better Approach:**
1. Store configs in `~/.datacompass/configs/sources/`
2. Use environment variables for secrets: `password: ${PG_PASSWORD}`
3. Config files are inputs for `source add`, not persistent state

```yaml
# ~/.datacompass/configs/sources/my-source.yaml
host: ${DB_HOST:-localhost}
port: ${DB_PORT:-5432}
database: ${DB_NAME}
username: ${DB_USER}
password: ${DB_PASSWORD}  # Required env var
```

```bash
# Usage
export DB_PASSWORD='secret'
datacompass source add my-source --type postgresql \
  --config ~/.datacompass/configs/sources/my-source.yaml
```

**Lesson:** Design for secrets management from the start. The config loader already supports `${VAR}` and `${VAR:-default}` syntax.

---

## 6. Async Method Mocking in Tests

**Problem:** Tests failed with "object MagicMock can't be used in 'await' expression".

**Root Cause:** Added new async methods (`get_foreign_keys`, `get_view_dependencies`) but MagicMock returns sync mocks by default. When the code checked `hasattr()`, it found the mock attribute, then failed on `await`.

**Fix:** Made the lineage extraction defensive:

```python
try:
    if hasattr(adapter, "get_foreign_keys") and callable(adapter.get_foreign_keys):
        fks = await adapter.get_foreign_keys()
        if isinstance(fks, list):  # Verify we got actual data
            ...
except (TypeError, AttributeError):
    pass  # Silently skip if not supported
```

**Lesson:** When adding optional adapter methods, handle missing/incompatible implementations gracefully.

---

## 7. Materialized View Column Metadata

**Problem:** Materialized views showed 0 columns.

**Root Cause:** `information_schema.columns` only includes regular tables and views, not materialized views.

**Note:** This is a known limitation. To get materialized view columns, need to query `pg_attribute`:

```sql
SELECT
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    a.attnum AS position
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE c.relkind = 'm'  -- materialized view
  AND a.attnum > 0
  AND NOT a.attisdropped
```

**Status:** Not yet implemented - materialized views scan but columns are not extracted.

---

## Checklist for New Adapters

Before considering an adapter complete:

- [ ] Test with non-superuser credentials
- [ ] Verify secrets aren't logged or stored in plaintext
- [ ] Test full flow: add source → test → scan → query objects
- [ ] Verify lineage extraction works (if supported)
- [ ] Test with schema filtering enabled
- [ ] Document any database-specific permissions required
- [ ] Add integration test with real database (can be in CI or manual)
- [ ] Update `__init__.py` exports
- [ ] Update `pyproject.toml` optional dependencies
