import { getPlans } from '../../api/client'
import type { PlansResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'
import { ACCOUNT_ID } from '../../config'

const currency = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', maximumFractionDigits: 0 })
const months = (value: number) => (value >= 120 ? '120+ months' : `${value.toFixed(1)} months`)

export function Plans() {
  const { data, error, loading } = useAccountData<PlansResponse>(() => getPlans(ACCOUNT_ID))
  const goal = data?.goal_plan
  const backup = data?.backup_plan

  return (
    <main className="dashboard-main">
      <section className="page-heading with-mascot">
        <div>
          <p className="eyebrow">Your plans</p>
          <h1>A goal, and a backup</h1>
          <p className="welcome-copy">A savings goal, and a plan in case your income drops.</p>
          {loading && <p className="data-status">Loading…</p>}
          {error && <p className="data-status data-error">Could not load plans. {error}</p>}
        </div>
        <img src="/assets/astro-celebrate.svg" alt="" aria-hidden="true" />
      </section>

      {goal && backup && (
        <div className="plans-grid">
          <article className="card">
            <p className="eyebrow">Goal plan</p>
            <h2>{goal.name}</h2>
            <div className="budget-amounts">
              <strong>{currency.format(goal.current)}</strong>
              <span>of {currency.format(goal.target)}</span>
            </div>
            <div className="goal-progress"><i style={{ width: `${goal.progress_pct}%` }} /></div>
            <p className="muted-copy">
              {Math.round(goal.progress_pct)}% there.{' '}
              {goal.progress_pct >= 100
                ? 'Goal reached. Keep it topped up.'
                : goal.months_to_goal !== null
                  ? `Saving ${currency.format(goal.monthly_saving)}/month gets you there in about ${Math.ceil(goal.months_to_goal)} months.`
                  : ''}
            </p>
            <ol className="plan-steps">
              {goal.steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
          </article>

          <article className="card backup-card">
            <p className="eyebrow">Backup plan</p>
            <h2>If you lose your job</h2>
            <p className="muted-copy">{backup.trigger}.</p>
            <div className="backup-compare">
              <div><span>Without changes</span><strong>{months(backup.runway_without_actions)}</strong></div>
              <span aria-hidden="true">→</span>
              <div><span>With the top 2 actions</span><strong className="positive-value">{months(backup.runway_with_top_actions)}</strong></div>
            </div>
            <ol className="plan-steps">
              {backup.actions.map((action) => (
                <li key={action.title}>
                  <strong>{action.title}</strong> <span className="positive-value">+{action.months_gained.toFixed(1)} months</span>
                  <small>{action.detail}</small>
                </li>
              ))}
            </ol>
          </article>
        </div>
      )}
    </main>
  )
}
