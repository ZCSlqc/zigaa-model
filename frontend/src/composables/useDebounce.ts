/**
 * Create a debounced search handler that calls fetchFn after delay ms.
 * Returns a function to bind to @input on el-input.
 */
export function useDebounceSearch(fetchFn: () => void, delay = 300): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null

  return () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(fetchFn, delay)
  }
}
