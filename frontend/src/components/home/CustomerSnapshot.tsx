import type { Profile } from '../../api/client'

const currency = new Intl.NumberFormat('en-CA', { currency: 'CAD', style: 'currency', maximumFractionDigits: 0 })

export function CustomerSnapshot({ profile, runway }: { profile: Profile; runway: number }) {
  const runwayText = runway >= 120 ? 'No shortfall' : `${runway.toFixed(1)} months`
  const items = [
    { label: 'Monthly income', value: currency.format(profile.income) },
    { label: 'Fixed costs', value: currency.format(profile.fixed_costs) },
    { label: 'Savings buffer', value: currency.format(profile.buffer) },
    { label: 'Runway today', value: runwayText },
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
    </section>
  )
}
