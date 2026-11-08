import { useEffect, useState } from 'react'

type AsyncState<T> = {
  data: T | null
  error: string | null
  loading: boolean
}

export function useAccountData<T>(
  loader: () => Promise<T>,
  dependencies: readonly unknown[] = [],
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
  })

  // The caller supplies the dependency list because loaders are account/query-specific.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    let active = true
    // Loading is reset whenever the caller's account/query dependencies change.
    // eslint-disable-next-line react/set-state-in-effect
    setState({ data: null, error: null, loading: true })
    loader()
      .then((data) => {
        if (active) setState({ data, error: null, loading: false })
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            data: null,
            error: error instanceof Error ? error.message : 'Unable to load account data',
            loading: false,
          })
        }
      })
    return () => {
      active = false
    }
  // The dependency list is intentionally supplied by the hook caller.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)

  return state
}
