const DEFAULT_ACCOUNT_ID = 20111

function readAccountId(): number {
  const fromUrl = Number(new URLSearchParams(window.location.search).get('account'))
  if (Number.isInteger(fromUrl) && fromUrl > 0) return fromUrl
  const fromEnv = Number(import.meta.env.VITE_ACCOUNT_ID)
  if (Number.isInteger(fromEnv) && fromEnv > 0) return fromEnv
  return DEFAULT_ACCOUNT_ID
}

export const ACCOUNT_ID = readAccountId()

export function switchAccount(accountId: number) {
  const url = new URL(window.location.href)
  url.searchParams.set('account', String(accountId))
  window.location.assign(url.toString())
}
