/** Extract relative path after `/original/` in a tree node path.
 *  Tree paths look like: `/uploads/{modelId}/{type}/original/{relPath}`
 *  Returns: `{relPath}` (e.g. `20260624_180406/子文件夹`)
 */
export function extractRelPath(fullPath: string): string {
  const idx = fullPath.indexOf('/original/')
  if (idx !== -1) return fullPath.slice(idx + 10)
  const parts = fullPath.split('/')
  const oi = parts.indexOf('original')
  if (oi >= 0) return parts.slice(oi + 1).join('/')
  return fullPath
}
