export function Budget() {
  const [refresh, setRefresh] = useState(0)
  const [prompt, setPrompt] = useState('')
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null)
  const [assistantError, setAssistantError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const { data, error, loading } = useAccountData<BudgetResponse>(
    () => getBudgets(ACCOUNT_ID),
    [refresh],
  )
  const cards = data
    ? data.goals.map((goal) => ({
        title: goal.name,
        status: 'Created' as const,
        spent: currency.format(goal.monthly_savings),
        limit: currency.format(goal.monthly_limit),
        progress: Math.min((goal.monthly_savings / goal.monthly_limit) * 100, 100),
        insight: goal.rationale,
        icon: '✦',
      }))
    : []

  async function createBudget(event: FormEvent) {
    event.preventDefault()
    if (!prompt.trim() || creating) return
    setCreating(true)
    setAssistantError(null)
    try {
      const response = await askAssistant(ACCOUNT_ID, prompt.trim())
      setAssistantMessage(response.message)
      setPrompt('')
      setRefresh((value) => value + 1)
    } catch (error) {
      setAssistantError(error instanceof Error ? error.message : 'Astro could not create a budget')
    } finally {
      setCreating(false)
    }
  }

  return (
    <main className="dashboard-main budget-main">
      <section className="page-heading budget-heading">
        <div>
          <p className="eyebrow">Detected from your activity</p>
          <h1>Budget</h1>
          <p className="welcome-copy">
            Budgets are created only when you ask Astro. Astro reads your banking activity and calculates an affordable plan.
          </p>
          <form className="chat-input" onSubmit={createBudget}>
            <span className="astro-icon" aria-hidden="true">✦</span>
            <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask Astro to create a budget..." />
            <button className="send-arrow" disabled={creating} type="submit" aria-label="Create budget">↗</button>
          </form>
          {assistantMessage && <p className="assistant-reply"><span className="astro-icon" aria-hidden="true">✦</span>{assistantMessage}</p>}
          {assistantError && <p className="data-status data-error">{assistantError}</p>}
          {loading && <p className="data-status">Syncing detected budgets…</p>}
          {error && <p className="data-status data-error">Showing the saved budget view. {error}</p>}
        </div>
        <div className="period-progress">
          <span>Current pay period</span>
          <strong>Day {data?.pay_period_day ?? '—'} <small>of {data?.pay_period_length ?? '—'}</small></strong>
          <div><i style={{ width: `${data ? (data.pay_period_day / data.pay_period_length) * 100 : 0}%` }} /></div>
        </div>
      </section>

      <section className="budget-grid" aria-label="User-created budgets">
        {cards.length > 0 ? cards.map((card) => <BudgetCard {...card} key={card.title} />) : (
          <div className="card budget-empty">
            <span className="astro-icon" aria-hidden="true">✦</span>
            <h2>No budgets yet</h2>
            <p className="muted-copy">Tell Astro what you want to accomplish, such as “create a budget to help me save more money.”</p>
          </div>
        )}
      </section>

      <section className="budget-footer insight-box">
        <span className="astro-icon" aria-hidden="true">✦</span>
        <p>Astro watches your pace automatically. If your activity changes, these budgets adjust with it—there is nothing to update.</p>
      </section>
    </main>
  )
}

function BudgetCard({ title, status, spent, limit, progress, insight, icon }: {
  title: string
  status: 'Created'
  spent: string
  limit: string
  progress: number
  insight: string
  icon: string
}) {
  const statusClass = status.toLowerCase().replace(' ', '-')

  return (
    <article className="card budget-card">
      <div className="budget-card-heading">
        <span className={`budget-icon ${statusClass}`} aria-hidden="true">{icon}</span>
        <span className={`status-badge ${statusClass === 'watch' ? 'watch' : ''}`}>{status}</span>
      </div>
      <h2>{title}</h2>
      <div className="budget-amounts">
        <strong>{spent}</strong>
        <span>of {limit}</span>
      </div>
      <div className="budget-progress" aria-label={`${progress}% of budget used`}>
        <i className={statusClass} style={{ width: `${progress}%` }} />
      </div>
      <div className="budget-progress-labels">
        <span>{progress}% used</span>
        <span>Monthly plan</span>
      </div>
      <div className="budget-insight">
        <span className="astro-icon" aria-hidden="true">✦</span>
        <p>{insight}</p>
      </div>
    </article>
  )
}
import { useState } from 'react'
import type { FormEvent } from 'react'
import { askAssistant, getBudgets } from '../../api/client'
import type { BudgetResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'
import { ACCOUNT_ID } from '../../config'

const currency = new Intl.NumberFormat('en-CA', {
  currency: 'CAD',
  style: 'currency',
  maximumFractionDigits: 0,
})
