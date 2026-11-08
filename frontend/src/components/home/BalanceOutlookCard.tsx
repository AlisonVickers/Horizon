import { getDashboard } from '../../api/client'
import type { DashboardResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'
import { ACCOUNT_ID } from '../../config'

const currency = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', notation: 'compact', maximumFractionDigits: 1 })
const monthLabel = new Intl.DateTimeFormat('en-CA', { month: 'short', timeZone: 'UTC' })
const dayLabel = new Intl.DateTimeFormat('en-CA', { month: 'short', day: 'numeric', timeZone: 'UTC' })

type HistoryPoint = { month: string; balance: number }

function nextPeriod(asOf: string): [string, string] {
  const start = new Date(`${asOf}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() + 1)
  const end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0))
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)]
}

const W = 640
const H = 240
const PAD = { top: 20, right: 24, bottom: 34, left: 56 }

export function BalanceOutlookCard({ asOf, history }: { asOf: string | null; history: HistoryPoint[] }) {
  const { data } = useAccountData<DashboardResponse | null>(
    () => (asOf ? getDashboard(ACCOUNT_ID, ...nextPeriod(asOf)) : Promise.resolve(null)),
    [asOf],
  )
  const projection = data?.projected_balance ?? null
  const buffer = data?.balance_alerts.safety_buffer ?? 500
  const warning = data?.balance_alerts.status === 'warning'

  const points = history.map((row) => ({ label: monthLabel.format(new Date(`${row.month}-01T00:00:00Z`)), value: row.balance }))
  const projected = projection ? { label: dayLabel.format(new Date(`${data!.period.end_date}T00:00:00Z`)), value: projection.projected_ending_balance } : null
  const all = [...points, ...(projected ? [projected] : [])]

  if (points.length < 2) {
    return (
      <article className="card balance-outlook-card">
        <p className="eyebrow">Last 12 months</p>
        <h2>Balance trend</h2>
        <p className="muted-copy">Not enough history to chart this account yet.</p>
      </article>
    )
  }

  const values = [...all.map((p) => p.value), buffer]
  const max = Math.max(...values)
  const min = Math.min(0, ...values)
  const span = max - min || 1
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (i / Math.max(all.length - 1, 1)) * innerW
  const y = (v: number) => PAD.top + (1 - (v - min) / span) * innerH

  const historyPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')
  const areaPath = `${historyPath} L${x(points.length - 1).toFixed(1)},${y(min).toFixed(1)} L${x(0).toFixed(1)},${y(min).toFixed(1)} Z`
  const last = points[points.length - 1]
  const first = points[0]
  const change = last.value - first.value
  const ticks = [max, (max + min) / 2, min]

  return (
    <article className="card balance-outlook-card">
      <div className="card-heading">
        <div>
          <p className="eyebrow">Last 12 months</p>
          <h2>Balance trend</h2>
        </div>
        {data && (
          <span className={`status-badge ${warning ? 'watch' : ''}`}>{warning ? 'Low balance ahead' : 'On track'}</span>
        )}
      </div>

      <div className="outlook-figures">
        <div><span>Balance now</span><strong>{currency.format(last.value)}</strong></div>
        <div>
          <span>12-month change</span>
          <strong className={change >= 0 ? 'positive-value' : 'negative-value'}>{change >= 0 ? '+' : '−'}{currency.format(Math.abs(change))}</strong>
        </div>
        <div><span>Projected {projected?.label ?? 'next month'}</span><strong>{projected ? currency.format(projected.value) : '—'}</strong></div>
      </div>

      <svg className="balance-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Month-end balance over the last 12 months with next month's projection">
        <defs>
          <linearGradient id="balanceFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2b50d6" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#2b50d6" stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} stroke="#e6eaf2" />
            <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end" className="chart-axis">{compact.format(tick)}</text>
          </g>
        ))}

        <line x1={PAD.left} x2={W - PAD.right} y1={y(buffer)} y2={y(buffer)} stroke="#f28c28" strokeDasharray="4 4" />
        <text x={W - PAD.right} y={y(buffer) - 6} textAnchor="end" className="chart-axis chart-buffer">Safety buffer {currency.format(buffer)}</text>

        <path d={areaPath} fill="url(#balanceFill)" />
        <path d={historyPath} fill="none" stroke="#2b50d6" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />

        {projected && (
          <>
            <line x1={x(points.length - 1)} y1={y(last.value)} x2={x(all.length - 1)} y2={y(projected.value)} stroke="#2b50d6" strokeWidth="3" strokeDasharray="6 6" strokeLinecap="round" />
            <circle cx={x(all.length - 1)} cy={y(projected.value)} r="5" fill="#fff" stroke="#2b50d6" strokeWidth="2.5">
              <title>{`Projected ${projected.label}: ${currency.format(projected.value)}`}</title>
            </circle>
          </>
        )}

        {points.map((p, i) => (
          <circle key={`${p.label}-${i}`} cx={x(i)} cy={y(p.value)} r={i === points.length - 1 ? 5 : 3} fill="#2b50d6">
            <title>{`${p.label}: ${currency.format(p.value)}`}</title>
          </circle>
        ))}

        {all.map((p, i) => (i % 2 === 0 || i === all.length - 1) && (
          <text key={`label-${i}`} x={x(i)} y={H - 10} textAnchor="middle" className="chart-axis">{p.label}</text>
        ))}
      </svg>

      <p className="chart-legend">
        <span><i className="legend-line" /> Month-end balance</span>
        {projected && <span><i className="legend-line dashed" /> Projection after known bills</span>}
      </p>
    </article>
  )
}
