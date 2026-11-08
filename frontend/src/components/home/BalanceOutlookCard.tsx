import { getDashboard } from '../../api/client'
import type { DashboardResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'
import { ACCOUNT_ID } from '../../config'

const currency = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', maximumFractionDigits: 0 })
const shortDate = new Intl.DateTimeFormat('en-CA', { month: 'short', day: 'numeric', timeZone: 'UTC' })
const fmt = (iso: string) => shortDate.format(new Date(`${iso}T00:00:00Z`))

function nextPeriod(asOf: string): [string, string] {
  const start = new Date(`${asOf}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() + 1)
  const end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0))
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)]
}

/** Uses Heena's /api/accounts/{id}/dashboard: projected balance plus low-balance alerts for the next month. */
export function BalanceOutlookCard({ asOf }: { asOf: string | null }) {
  const { data, error } = useAccountData<DashboardResponse | null>(
    () => (asOf ? getDashboard(ACCOUNT_ID, ...nextPeriod(asOf)) : Promise.resolve(null)),
    [asOf],
  )
  const projection = data?.projected_balance
  const alerts = data?.balance_alerts
  const warning = alerts?.status === 'warning'
  const start = projection?.starting_balance ?? 0
  const points = projection ? [{ date: data!.period.start_date, balance: start }, ...projection.timeline.map((e) => ({ date: e.date, balance: e.projected_balance }))] : []
  const max = Math.max(...points.map((p) => p.balance), 1)

  return (
    <article className="card balance-outlook-card">
      <div className="card-heading">
        <div>
          <p className="eyebrow">Next month · bills already known</p>
          <h2>Balance outlook</h2>
        </div>
        {alerts && alerts.status !== 'unavailable' && (
          <span className={`status-badge ${warning ? 'watch' : ''}`}>{warning ? 'Low balance ahead' : 'Stays above buffer'}</span>
        )}
      </div>
      {error && <p className="data-status data-error">Balance outlook unavailable. {error}</p>}
      {!data && !error && <p className="muted-copy">Projecting your balance…</p>}
      {data && !projection && <p className="muted-copy">Not enough recurring activity to project this account yet.</p>}
      {projection && (
        <>
          <div className="outlook-figures">
            <div><span>Starts at</span><strong>{currency.format(projection.starting_balance)}</strong></div>
            <div><span>Lowest point</span><strong className={warning ? 'negative-value' : ''}>{currency.format(projection.lowest_projected_balance)}</strong></div>
            <div><span>Ends at</span><strong>{currency.format(projection.projected_ending_balance)}</strong></div>
          </div>
          <div className="outlook-bars" aria-label="Projected balance after each bill">
            {points.map((point, index) => (
              <div className="outlook-bar" key={`${point.date}-${index}`} title={`${fmt(point.date)}: ${currency.format(point.balance)}`}>
                <i style={{ height: `${Math.max((point.balance / max) * 100, 2)}%` }} className={point.balance < (alerts?.safety_buffer ?? 0) ? 'is-low' : ''} />
                <small>{fmt(point.date)}</small>
              </div>
            ))}
          </div>
          <div className="insight-box">
            <span className="astro-icon" aria-hidden="true">✦</span>
            <p>
              {warning
                ? <>Your balance dips below your {currency.format(alerts!.safety_buffer)} safety buffer on <strong>{alerts!.alerts[0].date ? fmt(alerts!.alerts[0].date) : 'day one'}</strong>, about <strong>{currency.format(alerts!.alerts[0].shortfall)}</strong> short. Move money in before then.</>
                : <>After {projection.timeline.length} known bills ({currency.format(data!.cashflow.predicted_recurring_expenses)}), you stay above your {currency.format(alerts?.safety_buffer ?? 500)} safety buffer all month.</>}
            </p>
          </div>
        </>
      )}
    </article>
  )
}
