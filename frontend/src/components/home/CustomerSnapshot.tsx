import type { Profile } from '../../api/client'

const currency = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', maximumFractionDigits: 0 })

export function CustomerSnapshot({ profile, runway }: { profile: Profile; runway: number }) {
  const runwayText = runway >= 120 ? 'No shortfall' : `${runway.toFixed(1)} months`
  const items = [
    { label: 'Monthly income', value: currency.format(profile.income), formula: 'I = median money_in' },
    { label: 'Fixed costs', value: currency.format(profile.fixed_costs), formula: 'F = median(bills + insurance + loan)' },
    { label: 'Savings buffer', value: currency.format(profile.buffer), formula: 'B = mean avg_daily_balance, last 6 months' },
    { label: 'Runway today', value: runwayText, formula: 'runway = B ÷ (S − I), capped at 120' },
  ]
  return (
    <section className="card snapshot-card">
      <div className="snapshot-head">
        <img src="/assets/astro-wave.svg" alt="" aria-hidden="true" />
        <div>
          <p className="eyebrow">Overview</p>
          <h2>Where you stand</h2>
        </div>
      </div>
      <div className="snapshot-grid">
        {items.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <details className="how-calculated">
        <summary>How we calculated this</summary>
        <ul>
          {items.map((item) => <li key={item.formula}><code>{item.formula}</code></li>)}
          <li><code>S = median money_out</code> = {currency.format(profile.spending)}</li>
          <li><code>H = median household_bills</code> = {currency.format(profile.household_bills)}</li>
          <li><code>P = loan payment (status C or D)</code> = {currency.format(profile.loan_payment)}</li>
        </ul>
      </details>
    </section>
  )
}
