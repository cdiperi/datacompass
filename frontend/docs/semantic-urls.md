# Semantic URLs Design

This document explains the design decisions behind Data Compass's semantic URL structure for the web application.

## Problem Statement

The original URL scheme used opaque numeric IDs for object detail pages:

```
/objects/4
/objects/127
```

This approach has several drawbacks:

1. **Not human-readable** - Users can't tell what object they're viewing from the URL
2. **Not shareable** - URLs don't convey meaning when shared in documentation or chat
3. **Not bookmarkable** - Saved bookmarks become meaningless over time
4. **Database-coupled** - URLs depend on internal database IDs that may change across environments
5. **No hierarchy** - Flat structure doesn't reflect the natural source > schema > object hierarchy

## Design Goals

1. **Human-readable URLs** that describe the resource being viewed
2. **Hierarchical structure** matching the data model (source > schema > object)
3. **Future-proof** for source-level and schema-level pages
4. **Backward compatible** with existing bookmarks and links
5. **Safe for special characters** in names (spaces, dots, unicode)

## URL Structure

### Final Design

```
/catalog                                    # Catalog overview
/catalog/{source}                           # Source detail (filterable browse)
/catalog/{source}/{schema}                  # Schema page (filterable browse)
/catalog/{source}/{schema}/{object}         # Object detail
```

### Examples

| Description | URL |
|-------------|-----|
| Catalog root | `/catalog` |
| Demo source | `/catalog/demo` |
| Core schema in demo | `/catalog/demo/core` |
| Customers table | `/catalog/demo/core/customers` |
| Table with spaces | `/catalog/demo/my%20schema/user%20accounts` |

### Why `/catalog/` Prefix?

We considered several alternatives:

| Option | Example | Rejected Because |
|--------|---------|------------------|
| No prefix | `/demo/core/customers` | Conflicts with existing routes (`/dq`, `/search`) and future routes |
| `/browse/` | `/browse/demo/core/customers` | "Browse" implies list view, not detail view |
| `/objects/` | `/objects/demo/core/customers` | Ambiguous - could mean the old ID-based route |
| `/data/` | `/data/demo/core/customers` | Too generic |

The `/catalog/` prefix:
- Clearly namespaces all data browsing functionality
- Avoids collision with feature hubs (`/dq`, `/search`, `/scheduler`, `/deprecation`)
- Leaves room for future top-level sections (`/admin`, `/settings`)
- Semantically accurate - users are browsing the catalog

### Object Type Handling

Object types (TABLE, VIEW, MATERIALIZED_VIEW, FUNCTION) are **omitted from URLs** because:

1. Name collisions between types are rare in practice
2. Including type would make URLs longer and less readable
3. The type is visible in the UI once you navigate to the page

For the rare case of disambiguation, we support an optional query parameter:

```
/catalog/demo/core/users?type=VIEW
```

This is not currently implemented in the UI but the URL structure supports it.

## Implementation Details

### URL Encoding

All path segments use `encodeURIComponent()` / `decodeURIComponent()` to safely handle:

- Spaces: `my table` → `my%20table`
- Dots: `v1.0` → `v1%2E0` (though dots in names work fine within a single segment)
- Unicode: `表` → `%E8%A1%A8`
- Special chars: `user@domain` → `user%40domain`

### Utility Functions

URL construction is centralized in `frontend/src/utils/urls.ts`:

```typescript
// Build object detail URL
getObjectUrl({ source_name, schema_name, object_name })
// → /catalog/demo/core/customers

// Build source page URL
getSourceUrl(sourceName)
// → /catalog/demo

// Build schema page URL
getSchemaUrl(sourceName, schemaName)
// → /catalog/demo/core

// Convert URL params to FQN for API calls
paramsToFqn(source, schema, object)
// → demo.core.customers
```

### Route Configuration

Routes are defined in `App.tsx`:

```tsx
<Route path="catalog" element={<BrowsePage />} />
<Route path="catalog/:source" element={<BrowsePage />} />
<Route path="catalog/:source/:schema" element={<BrowsePage />} />
<Route path="catalog/:source/:schema/:object" element={<ObjectDetailPage />} />
```

The first three routes all render `BrowsePage`, which extracts filters from URL params.

### Backward Compatibility

Legacy URLs are supported through redirects:

```tsx
{/* Redirects old ID-based URLs to semantic URLs */}
<Route path="objects/:id" element={<ObjectRedirect />} />

{/* Redirects old browse path */}
<Route path="browse" element={<Navigate to="/catalog" replace />} />
```

The `ObjectRedirect` component:
1. Fetches the object by numeric ID
2. Extracts `source_name`, `schema_name`, `object_name`
3. Redirects to the semantic URL using `<Navigate replace />`

This ensures:
- Old bookmarks continue to work
- External links in documentation remain valid
- Users are transparently upgraded to the new URL scheme

### API Compatibility

The backend API already supports FQN-based lookups:

```
GET /api/v1/objects/demo.core.customers
```

This was implemented during Phase 2 specifically to enable semantic URLs. The `ObjectDetailPage` constructs the FQN from URL params using `paramsToFqn()`.

## Navigation Updates

All navigation calls throughout the app were updated to use semantic URLs:

| Component | Change |
|-----------|--------|
| `ObjectTable` | Row click navigates to `getObjectUrl(record)` |
| `SearchResultsPage` | Result click navigates to `getObjectUrl(result)` |
| `BreachTable` | Object link uses `getObjectUrl(record)` |
| `LineageList` | Node links use `getObjectUrl(node)` |
| `BrowsePage` | Source/schema dropdowns navigate to path-based URLs |
| `ObjectDetailPage` | Breadcrumbs link to source and schema pages |
| `Layout` | Sidebar "Catalog" link goes to `/catalog` |

### Breadcrumb Navigation

Object detail pages show clickable breadcrumbs:

```
Home > Catalog > demo > core > customers
       ↓         ↓      ↓
    /catalog  /catalog/demo  /catalog/demo/core
```

This provides quick navigation up the hierarchy.

## Future Considerations

### Source Detail Pages

Currently `/catalog/{source}` renders the browse page filtered by source. In the future, this could be a dedicated source detail page showing:

- Source metadata and connection info
- Scan history and statistics
- Schema list with object counts
- Health metrics

### Schema Governance Pages

Similarly, `/catalog/{source}/{schema}` could become a schema governance page with:

- Schema-level documentation
- Data steward assignments
- Access policies
- Quality score rollup

### Deep Linking to Tabs

We may want to support linking directly to object tabs:

```
/catalog/demo/core/customers#lineage
/catalog/demo/core/customers#quality
```

This is straightforward to add when needed.

### Search Integration

Search results could update the URL to enable sharing:

```
/search?q=customer&source=demo
```

Currently search state is in the URL via query params, which works well with the semantic structure.

## Testing Checklist

When verifying the implementation:

1. Navigate to `/catalog/demo/core/customers` - should load object detail
2. Navigate to `/objects/4` - should redirect to semantic URL
3. Click object in browse table - URL should be semantic
4. Click search result - URL should be semantic
5. Breadcrumb links should navigate correctly
6. Browser back/forward should work
7. Refresh on semantic URL should load correctly
8. Sidebar "Catalog" should be highlighted on all `/catalog/*` routes
9. Special characters in names should encode/decode properly
