import { ref } from 'vue'

/**
 * Shared loading state with 500ms delay to prevent flash on fast requests.
 * Multiple independent keys can be tracked simultaneously (Set-based).
 */
export function useDelayedLoading() {
  const loadingActions = ref<Set<string>>(new Set())
  let loadingTimer: ReturnType<typeof setTimeout> | null = null
  let pendingKey: string | null = null

  function startLoading(key: string) {
    stopLoading()
    pendingKey = key
    loadingTimer = setTimeout(() => {
      if (pendingKey) loadingActions.value = new Set([pendingKey])
      pendingKey = null
    }, 500)
  }

  function stopLoading() {
    if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
    pendingKey = null
    loadingActions.value = new Set()
  }

  function isLoading(key: string): boolean {
    return loadingActions.value.has(key)
  }

  function hasLoading(): boolean {
    return loadingActions.value.size > 0
  }

  return { loadingActions, startLoading, stopLoading, isLoading, hasLoading }
}

/**
 * Single-key variant for pages that only have one loading action at a time.
 */
export function useSingleLoading() {
  const loadingAction = ref<string>('')
  let loadingTimer: ReturnType<typeof setTimeout> | null = null

  function startLoading(key: string) {
    stopLoading()
    loadingTimer = setTimeout(() => loadingAction.value = key, 500)
  }

  function stopLoading() {
    if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
    loadingAction.value = ''
  }

  function isLoading(key: string): boolean {
    return loadingAction.value === key
  }

  return { loadingAction, startLoading, stopLoading, isLoading }
}
