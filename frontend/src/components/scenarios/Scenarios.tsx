
import { useEffect, useState } from 'react'
import { runScenario } from '../../api/client'
import type { ScenarioResponse } from '../../api/client'
import { ACCOUNT_ID } from '../../config'

type ScenarioKey = 'job-loss' | 'rent-increase' | 'pay-cut' | 'new-car' | 'surprise'

type ScenarioOption = {
  key: ScenarioKey
  label: string
  shock: string
}

const scenarioOptions: ScenarioOption[] = [
  { key: 'job-loss', label: 'Lose my job', shock: 'Job loss · EI income' },
  { key: 'rent-increase', label: 'Rent increases', shock: 'Rent goes up' },
  { key: 'pay-cut', label: 'Pay cut', shock: 'Lower income' },
  { key: 'new-car', label: 'New car payment', shock: 'New payment' },
  { key: 'surprise', label: 'Surprise expense', shock: 'One-off cost' },
]

const currency = new Intl.NumberFormat('en-CA', {
  currency: 'CAD',
  style: 'currency',
  maximumFractionDigits: 0,
})

const dateFormatter = new Intl.DateTimeFormat('en-CA', {
  dateStyle: 'long',
  timeZone: 'UTC',
})

export function Scenarios() {
  const [selectedScenarios, setSelectedScenarios] = useState<ScenarioKey[]>(['job-loss'])
  const [eiShare, setEiShare] = useState(55)
  const [rentIncrease, setRentIncrease] = useState(15)
  const [payCut, setPayCut] = useState(20)
  const [carPayment, setCarPayment] = useState(250)
  const [oneOffCost, setOneOffCost] = useState(2_000)
  const [pausedLoan, setPausedLoan] = useState(false)
  const [cutEveryday, setCutEveryday] = useState(false)
  const [delayOneOff, setDelayOneOff] = useState(false)

  const [results, setResults] = useState<ScenarioResponse | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    // eslint-disable-next-line react/set-state-in-effect
    setScenarioError(null)
    setLoading(true)
    const shocks = selectedScenarios.flatMap((selectedScenario) => {
      switch (selectedScenario) {
        case 'job-loss':
          return [{ name: 'job_loss_ei', value: eiShare / 100 }]
        case 'rent-increase':
          return [{ name: 'rent_up_pct', value: rentIncrease / 100 }]
        case 'pay-cut':
          return [{ name: 'pay_cut_pct', value: payCut / 100 }]
        case 'new-car':
          return [{ name: 'new_car_payment', value: carPayment }]
        case 'surprise':
          return [{ name: 'one_off_costs', value: delayOneOff ? 0 : oneOffCost }]
      }
    })
    const timer = window.setTimeout(() => runScenario(ACCOUNT_ID, [
      ...shocks,
      ...(pausedLoan
        ? [{ name: 'loan_payment_reduction', value: 1 }]
        : []),
      ...(cutEveryday ? [{ name: 'everyday_cut_pct', value: 0.1 }] : []),
    ])
      .then((response) => {
        if (active) { setResults(response); setLoading(false) }
      })
      .catch((error: unknown) => {
        if (active) {
          setScenarioError(error instanceof Error ? error.message : 'Unable to run scenario')
          setLoading(false)
        }
      })
    , 180)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [carPayment, cutEveryday, delayOneOff, eiShare, oneOffCost, pausedLoan, payCut, rentIncrease, selectedScenarios])

  return (
    <main className="dashboard-main scenarios-main">
      <section className="page-heading scenarios-heading">
        <div>
          <p className="eyebrow">Explore your options</p>
          <h1>What if?</h1>
          <p className="welcome-copy">Choose a scenario and adjust it to see the impact.</p>
          {results && <p className="muted-copy">Calculated from banking activity through {dateFormatter.format(new Date(`${results.current_date}T00:00:00Z`))}; next payday is in {results.days_until_payday} days.</p>}
        </div>
      </section>

      <div className="scenario-picker" role="tablist" aria-label="Scenario presets">
        {scenarioOptions.map((option) => (
          <button
            className={selectedScenarios.includes(option.key) ? 'is-selected' : ''}
            key={option.key}
            onClick={() => setSelectedScenarios((selected) => selected.includes(option.key)
              ? selected.filter((key) => key !== option.key)
              : [...selected, option.key])}
            role="tab"
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="scenario-layout">
        <section className="card scenario-inputs">
          <div className="scenario-section-heading">
            <p className="eyebrow">Scenario planner</p>
            <h2>WHAT HAPPENS?</h2>
          </div>
          <div className="shock-pills">
            {selectedScenarios.map((key) => {
              const scenario = scenarioOptions.find((option) => option.key === key)
              return scenario && <span className="shock-pill" key={key}>{scenario.shock}<b>×</b></span>
            })}
          </div>

          <div className="slider-list">
            {selectedScenarios.includes('job-loss') && (
              <SliderField label="EI pays this share of income" value={`${eiShare}%`} min={0} max={100} step={1} inputValue={eiShare} onChange={setEiShare} />
            )}
            {selectedScenarios.includes('rent-increase') && (
              <SliderField label="Rent goes up by" value={`+${rentIncrease}%`} min={0} max={50} step={1} inputValue={rentIncrease} onChange={setRentIncrease} />
            )}
            {selectedScenarios.includes('pay-cut') && (
              <SliderField label="Income is reduced by" value={`-${payCut}%`} min={0} max={100} step={1} inputValue={payCut} onChange={setPayCut} />
            )}
            {selectedScenarios.includes('new-car') && (
              <SliderField label="New monthly car payment" value={currency.format(carPayment)} min={0} max={2000} step={50} inputValue={carPayment} onChange={setCarPayment} />
            )}
            {selectedScenarios.includes('surprise') && (
              <SliderField label="Surprise expense (one-off)" value={currency.format(oneOffCost)} min={0} max={5000} step={100} inputValue={oneOffCost} onChange={setOneOffCost} />
            )}
          </div>
          <p className="scenario-note"><img className="astro-icon" src="/assets/astro-avatar.svg" alt="" aria-hidden="true" /> Based on your income, spending and balance history.</p>
          {selectedScenarios.includes('rent-increase') && (
            <p className="scenario-note">Rent changes only affect payments identified as rent in your transaction history. If none are detected, this scenario will not change the forecast.</p>
          )}
          {loading && <p className="muted-copy" role="status">Updating projection…</p>}
          {scenarioError && <p className="data-status data-error">{scenarioError}</p>}
        </section>

        <section className="scenario-results">
          <article className="card runway-card">
            <p className="eyebrow eyebrow-light">Main impact</p>
            <h2>Your money would last</h2>
            <div className="runway-number">{results ? (results.runway_months >= 120 ? '120+' : results.runway_months.toFixed(1)) : '…'} <small>months</small></div>
            <div className="runway-timeline">
              <span className="timeline-fill" style={{ width: `${Math.min(((results?.runway_months ?? 0) / 12) * 100, 100)}%` }} />
              <i className="timeline-marker" style={{ left: `${Math.min(((results?.runway_months ?? 0) / 12) * 100, 100)}%` }} />
            </div>
            <div className="timeline-labels"><span>0</span><span>3</span><span>6</span><span>9</span><span>12+ months</span></div>
          </article>

          <article className="card breakdown-card">
            <div className="card-heading"><div><p className="eyebrow">The numbers</p><h2>After the shock</h2></div><span className="status-badge watch">Scenario</span></div>
            <div className="breakdown-grid">
              <BreakdownMetric label="Income after shock" value={currency.format(results?.income_after ?? 0)} />
              <BreakdownMetric label="Spending after shock" value={currency.format(results?.spending_after ?? 0)} />
              <BreakdownMetric label="Monthly gap" value={currency.format(results?.gap ?? 0)} negative />
              <BreakdownMetric label="Buffer after one-off costs" value={currency.format(Math.max((results?.buffer ?? 0) - (results?.one_off_costs ?? 0), 0))} />
            </div>
          </article>
        </section>
      </div>

      <section className="card levers-section">
        <div className="section-heading">
          <div><p className="eyebrow">Small changes, more runway</p><h2>MAKE IT LAST LONGER</h2></div>
          <span className="muted-copy">Try pulling a lever</span>
        </div>
        <div className="lever-list">
          <button className={`lever-button ${pausedLoan ? 'is-active' : ''}`} onClick={() => setPausedLoan((active) => !active)} type="button">
            <span>Pause loan <small>({currency.format(results?.loan_payment ?? 0)}/mo)</small></span><strong>{pausedLoan ? 'Applied' : 'Try it'}</strong>
          </button>
          <button className={`lever-button ${cutEveryday ? 'is-active' : ''}`} onClick={() => setCutEveryday((active) => !active)} type="button">
            <span>Cut everyday spending 10% <small>({currency.format((results?.profile.everyday_spending ?? 0) * 0.1)}/mo)</small></span><strong>{cutEveryday ? 'Applied' : 'Try it'}</strong>
          </button>
          <button className={`lever-button ${delayOneOff ? 'is-active' : ''}`} onClick={() => setDelayOneOff((active) => !active)} disabled={!selectedScenarios.includes('surprise')} type="button">
            <span>Delay one-off expense <small>({currency.format(oneOffCost)})</small></span><strong>{delayOneOff ? 'Applied' : 'Try it'}</strong>
          </button>
        </div>
        <div className="insight-box lever-insight">
          <img className="astro-icon" src="/assets/astro-avatar.svg" alt="" aria-hidden="true" />
          <p>{pausedLoan || cutEveryday || delayOneOff
            ? 'The figures above include the selected changes.'
            : 'Select an option to see how much longer your money would last.'}</p>
        </div>
      </section>
    </main>
  )
}

type SliderFieldProps = {
  label: string
  value: string
  min: number
  max: number
  step: number
  inputValue: number
  onChange: (value: number) => void
}

function SliderField({ label, value, min, max, step, inputValue, onChange }: SliderFieldProps) {
  return (
    <label className="slider-field">
      <span><strong>{label}</strong><b>{value}</b></span>
      <input
        max={max}
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        step={step}
        type="range"
        value={inputValue}
      />
      <small><i>{max > 100 ? currency.format(min) : `${min}%`}</i><i>{max > 100 ? currency.format(max) : `${max}%`}</i></small>
    </label>
  )
}

function BreakdownMetric({ label, value, negative = false }: { label: string; value: string; negative?: boolean }) {
  return <div className="breakdown-metric"><span>{label}</span><strong className={negative ? 'negative-value' : ''}>{value}</strong></div>
}
