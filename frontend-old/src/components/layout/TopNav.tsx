import { useState } from 'react'
import type { FormEvent } from 'react'
import { ACCOUNT_ID, switchAccount } from '../../config'

type Tab = 'Home' | 'Calendar' | 'Budget' | 'Scenarios'

type TopNavProps = {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}

const tabs: Tab[] = ['Home', 'Calendar', 'Budget', 'Scenarios']

export function TopNav({ activeTab, onTabChange }: TopNavProps) {
  const [accountInput, setAccountInput] = useState(String(ACCOUNT_ID))

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = Number(accountInput.trim())
    if (Number.isInteger(next) && next > 0 && next !== ACCOUNT_ID) switchAccount(next)
  }

  return (
    <header className="top-nav">
      <a className="brand" href="/" onClick={(event) => event.preventDefault()}>
        Horizon<span style={{ color: '#ff9a4a' }}>.</span>
      </a>
      <nav aria-label="Primary navigation">
        {tabs.map((tab) => (
          <button
            className={`nav-link ${activeTab === tab ? 'is-active' : ''}`}
            key={tab}
            onClick={() => onTabChange(tab)}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>
      <form className="account-status" onSubmit={submit} title="Type any account_id and press Enter">
        <span className="sync-dot" aria-hidden="true" />
        <span>
          <small>Account</small>
          <input
            aria-label="Account ID"
            className="account-input"
            inputMode="numeric"
            onChange={(event) => setAccountInput(event.target.value.replace(/\D/g, ''))}
            value={accountInput}
          />
        </span>
      </form>
    </header>
  )
}
