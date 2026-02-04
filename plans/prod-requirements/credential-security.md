# Credential Security Plan

## Current State

When a data source is onboarded via `datacompass source add`, the YAML config is read, environment variables are resolved, and the **plaintext credentials** are stored in the `connection_info` JSON column of the `data_sources` table.

```
~/.datacompass/datacompass.db
  └── data_sources.connection_info  ← contains resolved passwords, tokens, etc.
```

This is acceptable for:
- Local development
- Single-user deployments
- Trusted environments where database file access is controlled

This is problematic for:
- Multi-user production deployments
- Environments with compliance requirements (SOC2, HIPAA, etc.)
- Situations where DB backups or logs might expose credentials

## Security Concerns

1. **Plaintext at rest** - Anyone with read access to the SQLite file can extract all source credentials
2. **Backup exposure** - Database backups contain credentials
3. **Log exposure** - Debug logging or error messages could leak connection info
4. **No credential rotation** - Credentials are static; rotating requires re-adding the source

## Options to Consider

### Option 1: File-Based Encryption at Rest

Encrypt sensitive fields before storing in the database using a local key.

**Approach:**
- Generate or accept an encryption key (stored in `~/.datacompass/key` or via env var)
- Encrypt `connection_info` before write, decrypt on read
- Use Fernet (symmetric) or similar

**Pros:**
- Simple to implement
- No external dependencies
- Works offline

**Cons:**
- Key management is user's responsibility
- Key on same machine as DB provides limited protection
- No audit trail

**Effort:** Low

---

### Option 2: External Secrets Manager Integration

Store credentials in a secrets backend; database only stores references.

**Approach:**
- `connection_info` stores `{"secret_ref": "vault://datacompass/sources/prod"}`
- At connection time, resolve the reference from the secrets manager
- Support multiple backends: HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager

**Pros:**
- Industry standard for production
- Centralized credential management
- Audit trails, rotation, access policies
- Credentials never touch local disk

**Cons:**
- External dependency
- More complex setup
- Requires network access to secrets manager

**Effort:** Medium-High

---

### Option 3: Environment Variable References (Deferred Resolution)

Don't resolve `${VAR}` at add time; resolve at connection time.

**Approach:**
- Store `connection_info` with `${VAR}` placeholders intact
- Resolve environment variables when connecting, not when onboarding
- Admin sets env vars in the deployment environment (systemd, Docker, k8s secrets)

**Pros:**
- No credentials in database at all
- Integrates with container/orchestration secrets
- Simple conceptually

**Cons:**
- Requires env vars to be set at runtime (not just onboarding time)
- Harder to debug connection issues
- All users/processes need access to same env vars

**Effort:** Low (mostly refactoring existing code)

---

### Option 4: Database-Level Encryption (SQLCipher)

Use SQLCipher instead of SQLite for encrypted database files.

**Approach:**
- Replace SQLite with SQLCipher
- Entire database is encrypted at rest
- Key provided at startup

**Pros:**
- Protects entire database, not just credentials
- Transparent to application code
- Well-established solution

**Cons:**
- Different SQLite driver dependency
- Key management still required
- Performance overhead

**Effort:** Medium

---

## Recommendation

For a phased approach:

| Phase | Option | When |
|-------|--------|------|
| Near-term | Option 3 (Deferred Resolution) | Low effort, eliminates credentials from DB |
| Medium-term | Option 1 (Encryption at Rest) | Defense in depth for any residual sensitive data |
| Production | Option 2 (Secrets Manager) | For enterprise/compliance deployments |

### Suggested Default Behavior

1. **Default:** Resolve env vars at connection time (Option 3)
2. **Flag:** `--resolve-now` for current behavior (store resolved values)
3. **Config:** `secrets_backend: vault` in global config for Option 2

This maintains backwards compatibility while making the secure path the default.

## Open Questions

- Should we support mixed mode (some sources use secrets manager, others use env vars)?
- How do we handle migration for existing sources with stored credentials?
- What's the minimum viable secrets manager integration (just Vault? AWS SM?)
- Do we need encryption for other tables (API keys, user passwords)?

## Related

- Phase 9 (Production Hardening) in project roadmap
- Authentication system already stores hashed passwords (not plaintext)
- API keys are stored as hashed values
