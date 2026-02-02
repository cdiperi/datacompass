/**
 * URL utilities for building semantic URLs in the catalog.
 */

/**
 * Build semantic URL from object data.
 */
export function getObjectUrl(obj: {
  source_name: string
  schema_name: string
  object_name: string
}): string {
  return `/catalog/${encodeURIComponent(obj.source_name)}/${encodeURIComponent(obj.schema_name)}/${encodeURIComponent(obj.object_name)}`
}

/**
 * Build FQN from URL params (for API calls).
 */
export function paramsToFqn(source: string, schema: string, object: string): string {
  return `${decodeURIComponent(source)}.${decodeURIComponent(schema)}.${decodeURIComponent(object)}`
}

/**
 * Build source page URL.
 */
export function getSourceUrl(sourceName: string): string {
  return `/catalog/${encodeURIComponent(sourceName)}`
}

/**
 * Build schema page URL.
 */
export function getSchemaUrl(sourceName: string, schemaName: string): string {
  return `/catalog/${encodeURIComponent(sourceName)}/${encodeURIComponent(schemaName)}`
}
