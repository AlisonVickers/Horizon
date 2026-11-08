import { useState } from 'react'
import type { FormEvent } from 'react'
import { askAssistant } from '../../api/client'
import { ACCOUNT_ID } from '../../config'
import { NextPaydayCard } from './NextPaydayCard'
import { BalanceOutlookCard } from './BalanceOutlookCard'
import { getHome } from '../../api/client'
import type { HomeResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'

const currency = new Intl.NumberFormat('en-CA', {
  currency: 'CAD',
  style: 'currency',
  maximumFractionDigits: 0,
})

const dateFormatter = new Intl.DateTimeFormat('en-CA', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})

function formatDate(value: string) {
  return dateFormatter.format(new Date(`${value}T00:00:00Z`))
}

export function Home() {
  const { data, error, loading } = useAccountData<HomeResponse>(() => getHome(ACCOUNT_ID))
  const calendarDays = data
    ? (() => {
        const start = new Date(`${data.last_payday}T00:00:00Z`)
        const end = new Date(`${data.next_payday}T00:00:00Z`)
        const currentDate = data.current_date
          ? new Date(`${data.current_date}T00:00:00Z`).toISOString().slice(0, 10)
          : null
        const dayDetails = new Map(data.pay_period_days.map((day) => [day.date, day]))
        const days: Array<{ date: string; label: string; amount: number }> = []

        for (const date = new Date(start); date <= end; date.setUTCDate(date.getUTCDate() + 1)) {
          const dateString = date.toISOString().slice(0, 10)
          const existingDay = dayDetails.get(dateString)
          let label = existingDay?.label ?? ''
          if (dateString === currentDate) label = 'Today'
          if (dateString === data.next_payday) label = 'Payday'
          days.push({ date: dateString, label, amount: existingDay?.amount ?? 0 })
        }

        const paddingDays = (start.getUTCDay() + 6) % 7
        return [...Array.from({ length: paddingDays }, () => null), ...days]
      })()
    : []
  const displayedExpenses = (data?.upcoming_expenses ?? []).slice(0, 3)
  const income = data?.expected_deposit ?? 0
  const spending = data?.spent_since_payday ?? 0
  const remaining = data?.flexible_spending_remaining ?? 0
  const overspent = data?.overspent_since_payday ?? 0
  const formattedCurrentDate = data?.current_date
    ? new Intl.DateTimeFormat('en-CA', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(new Date(`${data.current_date}T00:00:00Z`))
    : 'your latest banking date'
  const [prompt, setPrompt] = useState('')
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null)
  const [assistantDetails, setAssistantDetails] = useState<Record<string, unknown> | null>(null)
  const [assistantError, setAssistantError] = useState<string | null>(null)
  const [assistantLoading, setAssistantLoading] = useState(false)

  async function submitPrompt(event: FormEvent) {
    event.preventDefault()
    const trimmedPrompt = prompt.trim()
    if (!trimmedPrompt || assistantLoading) return
    setAssistantLoading(true)
    setAssistantError(null)
    try {
      const response = await askAssistant(ACCOUNT_ID, trimmedPrompt)
      setAssistantMessage(response.message)
      setAssistantDetails(response.data)
      setPrompt('')
    } catch (error) {
      setAssistantError(error instanceof Error ? error.message : 'Astro is unavailable right now')
    } finally {
      setAssistantLoading(false)
    }
  }

  return (
    <main className="dashboard-main">
      <section className="welcome-row">
        <div>
          <h1>Hello! Today is {formattedCurrentDate}</h1>
          <p className="welcome-copy">
            Everything here is detected from your bank activity. There is nothing to enter.
          </p>
        </div>
        <form className="chat-input" onSubmit={submitPrompt}>
          <span className="astro-icon" aria-hidden="true">✦</span>
          <input
            aria-label="Ask Astro anything"
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask Astro anything... e.g. Can I afford a $400 trip in December?"
            value={prompt}
          />
          <button className="send-arrow" disabled={assistantLoading} type="submit" aria-label="Send question">↗</button>
        </form>
        {assistantLoading && <p className="data-status">Astro is checking your detected activity…</p>}
        {assistantMessage && <p className="assistant-reply"><span className="astro-icon" aria-hidden="true">✦</span>{assistantMessage}</p>}
        {assistantDetails && (
          <p className="assistant-disclaimer">
            Based on {assistantDetails.projection_scope === 'detected_recurring_events_plus_requested_purchase'
              ? 'detected recurring activity plus your requested purchase'
              : 'detected recurring activity'}; future balances are estimates, not live balances.
          </p>
        )}
        {assistantError && <p className="data-status data-error">Astro could not answer right now. {assistantError}</p>}
        {loading && <p className="data-status">Syncing detected account activity…</p>}
        {error && <p className="data-status data-error">Showing the latest saved view. {error}</p>}
      </section>

      <div className="dashboard-grid">
        <NextPaydayCard
          expectedDeposit={income}
          spent={spending}
          remaining={remaining}
          overspent={overspent}
          balance={data?.balance ?? 0}
          daysAway={data?.days_until_payday ?? 0}
          lastPayday={data ? formatDate(data.last_payday) : '—'}
          paydayDate={data ? formatDate(data.next_payday) : '—'}
          flexibleSpending={remaining}
          dailyBudget={Math.round(remaining / Math.max(data?.days_until_payday ?? 1, 1))}
        />

        <article className="card expenses-card">
          <div className="card-heading">
            <div>
              <p className="eyebrow">Coming up</p>
              <h2>Upcoming expenses</h2>
            </div>
            <button className="text-button" type="button">View all <span>→</span></button>
          </div>
          <div className="expense-list">
            {displayedExpenses.length === 0 && <p className="muted-copy">No standing orders detected for this account.</p>}
            {displayedExpenses.map((expense) => (
              <div className="expense-row" key={expense.key}>
                <span className="expense-icon" aria-hidden="true">⌂</span>
                <span className="expense-name"><strong>{expense.name}</strong><small>{expense.due_date ? `Due ${formatDate(expense.due_date)} · monthly` : 'Monthly standing order'}</small></span>
                <strong className="expense-amount">{currency.format(expense.amount)}</strong>
              </div>
            ))}
          </div>
          <div className="insight-box expense-insight">
            <span className="astro-icon" aria-hidden="true">✦</span>
            <p><strong>{currency.format(data?.due_before_payday ?? 0)}</strong> due before payday</p>
            <span className={`status-badge ${(data?.balance ?? 0) >= (data?.due_before_payday ?? 0) ? '' : 'watch'}`}>
              {(data?.balance ?? 0) >= (data?.due_before_payday ?? 0) ? 'Covered' : 'At risk'}
            </span>
          </div>
        </article>

        <BalanceOutlookCard asOf={data?.current_date ?? null} />

        <article className="card glance-card">
          <div className="card-heading">
            <div>
              <p className="eyebrow">{data?.pay_period_frequency ?? 'Pay period'}</p>
              <h2>Pay period at a glance</h2>
            </div>
            <button className="icon-button" type="button" aria-label="Open calendar">↗</button>
          </div>
          <div className="mini-calendar">
            {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, index) => <span className="weekday" key={`${day}-${index}`}>{day}</span>)}
            {calendarDays.map((day, index) => day === null ? (
              <span aria-hidden="true" key={`padding-${index}`} />
            ) : (
              <span className={`calendar-day ${day.label.toLowerCase()}`} key={day.date}>
                <b>{new Date(`${day.date}T00:00:00Z`).getUTCDate()}</b>
                {day.label && <small>{day.label}</small>}
                {day.amount < 0 && <small>{currency.format(Math.abs(day.amount))}</small>}
              </span>
            ))}
          </div>
        </article>

        <article className="card goal-card">
          <div className="card-heading">
            <div><p className="eyebrow">Your goals</p><h2>{data?.savings_goal?.name ?? 'No goals yet'}</h2></div>
          </div>
          {data?.savings_goal ? (
            <>
              <div className="budget-amounts">
                <strong>{currency.format(data.savings_goal.current)}</strong>
                <span>of {currency.format(data.savings_goal.target)}</span>
              </div>
              <div className="goal-progress"><i style={{ width: `${data.savings_goal.progress_pct}%` }} /></div>
              <p className="muted-copy">{Math.round(data.savings_goal.progress_pct)}% there · suggested by Astro</p>
              <div className="insight-box">
                <span className="astro-icon" aria-hidden="true">✦</span>
                <p>{data.savings_goal.rationale}</p>
              </div>
            </>
          ) : (
            <div className="insight-box">
              <span className="astro-icon" aria-hidden="true">✦</span>
              <p>Ask Astro to help you create a goal from your banking activity.</p>
            </div>
          )}
        </article>

        <article className="card peer-card">
          <div className="card-heading">
            <div><p className="eyebrow">Benchmarks</p><h2>People like you</h2></div>
            <span className="info-mark">i</span>
          </div>
          <div className="peer-list">
            {(data?.benchmarks ?? []).map((row) => (
              <div className="benchmark-row" key={row.label}>
                <span><strong>{row.label}</strong><small>You {currency.format(row.you)} · typical {currency.format(row.peer_median)}</small></span>
                <strong className={row.is_good ? 'benchmark-good' : 'benchmark-bad'}>
                  {row.difference_pct >= 0 ? '+' : ''}{Math.round(row.difference_pct)}%
                </strong>
              </div>
            ))}
            {!data?.benchmarks?.length && <p className="muted-copy">Loading comparisons with all other customers…</p>}
          </div>
        </article>
      </div>
    </main>
  )
}
