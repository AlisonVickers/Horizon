import { useState } from 'react'
import { getCalendar } from '../../api/client'
import type { CalendarResponse } from '../../api/client'
import { useAccountData } from '../../hooks/useAccountData'
import { ACCOUNT_ID } from '../../config'

type CalendarView = 'Week' | 'Month' | 'Year'
type Events = CalendarResponse['events']
type Months = CalendarResponse['months']

const currency = new Intl.NumberFormat('en-CA', {
  currency: 'CAD',
  style: 'currency',
  maximumFractionDigits: 0,
})
const monthName = new Intl.DateTimeFormat('en-CA', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const shortMonth = new Intl.DateTimeFormat('en-CA', { month: 'short', timeZone: 'UTC' })
const dayLabel = new Intl.DateTimeFormat('en-CA', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })

const toDate = (iso: string) => new Date(`${iso}T00:00:00Z`)
const monthKey = (iso: string) => iso.slice(0, 7)

export function Calendar() {
  const [view, setView] = useState<CalendarView>('Month')
  const { data, error, loading } = useAccountData<CalendarResponse>(() => getCalendar(ACCOUNT_ID))

  return (
    <main className="dashboard-main calendar-main">
      <section className="page-heading calendar-heading">
        <div>
          <p className="eyebrow">Your money timeline</p>
          <h1>Calendar</h1>
          <p className="welcome-copy">See what is coming in, going out, and what your pay periods can handle.</p>
          {loading && <p className="data-status">Syncing your calendar…</p>}
          {error && <p className="data-status data-error">Could not load the calendar. {error}</p>}
        </div>
        <div className="view-toggle" aria-label="Calendar view">
          {(['Week', 'Month', 'Year'] as CalendarView[]).map((option) => (
            <button
              className={view === option ? 'is-selected' : ''}
              key={option}
              onClick={() => setView(option)}
              type="button"
            >
              {option}
            </button>
          ))}
        </div>
      </section>

      {data && view === 'Month' && <MonthView data={data} />}
      {data && view === 'Week' && <WeekView data={data} />}
      {data && view === 'Year' && <YearView months={data.months} />}
    </main>
  )
}

function MonthView({ data }: { data: CalendarResponse }) {
  const asOf = data.as_of ?? data.current_date
  const availableMonths = Array.from(new Set([
    ...data.months.map((month) => month.month),
    monthKey(data.next_payday),
  ])).sort()
  const [selected, setSelected] = useState(monthKey(asOf))
  const index = availableMonths.indexOf(selected)

  const [year, month] = selected.split('-').map(Number)
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const firstDay = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7
  const cells = Array.from({ length: firstDay + daysInMonth }, (_, cell) =>
    cell < firstDay ? null : `${selected}-${String(cell - firstDay + 1).padStart(2, '0')}`)
  const byDay = new Map<string, Events>()
  data.events.forEach((event) => {
    if (!event.date) return
    byDay.set(event.date, [...(byDay.get(event.date) ?? []), event])
  })

  return (
    <>
      <div className="calendar-layout">
        <article className="card month-card">
          <div className="month-card-header">
            <button className="month-arrow" disabled={index <= 0} onClick={() => setSelected(availableMonths[index - 1])} type="button" aria-label="Previous month">‹</button>
            <h2>{monthName.format(toDate(`${selected}-01`))}</h2>
            <button className="month-arrow" disabled={index >= availableMonths.length - 1} onClick={() => setSelected(availableMonths[index + 1])} type="button" aria-label="Next month">›</button>
          </div>
          <div className="large-calendar">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
              <span className="large-weekday" key={day}>{day}</span>
            ))}
            {cells.map((iso, cell) => {
              const dayEvents = iso ? byDay.get(iso) ?? [] : []
              const income = dayEvents.filter((event) => event.type === 'income' || event.type === 'payday')
              const bills = dayEvents.filter((event) => event.type === 'standing_order')
              const spent = dayEvents.filter((event) => event.type === 'expense').reduce((sum, event) => sum + event.amount, 0)
              return (
                <div className={`large-calendar-day ${iso === null ? 'is-muted' : ''}`} key={iso ?? `blank-${cell}`}>
                  <span className={iso === asOf ? 'today-number' : ''}>{iso ? Number(iso.slice(8)) : ''}</span>
                  {income.length > 0 && (
                    <small className="calendar-event payday-event" title={income.map((event) => event.label).join(', ')}>
                      {income.some((event) => event.type === 'payday') ? 'Payday' : '+'}{currency.format(income.reduce((sum, event) => sum + event.amount, 0))}
                    </small>
                  )}
                  {bills.map((bill) => <small className="calendar-event bill-event" key={bill.label}>{bill.label}</small>)}
                  {spent > 0 && <small className="calendar-event" title="Money out this day">−{currency.format(spent)}</small>}
                  {iso === asOf && <small className="calendar-event today-event">Today</small>}
                </div>
              )
            })}
          </div>
          <div className="calendar-legend">
            <span><i className="legend-dot payday-dot" /> Money in / payday</span>
            <span><i className="legend-dot bill-dot" /> Upcoming bill</span>
            <span><i className="legend-dot period-dot" /> Money out</span>
          </div>
        </article>
        <OutlookCard month={data.months.find((row) => row.month === selected)} label={selected} />
      </div>
      <WeekSummary days={data.last_seven_days} />
    </>
  )
}

function OutlookCard({ month, label }: { month: Months[number] | undefined; label: string }) {
  const title = `${new Intl.DateTimeFormat('en-CA', { month: 'long', timeZone: 'UTC' }).format(toDate(`${label}-01`))} outlook`
  if (!month) {
    return (
      <aside className="card outlook-card">
        <p className="eyebrow">Selected month</p>
        <h2>{title}</h2>
        <p className="muted-copy">This month has not happened yet. Upcoming payday and bills are shown on the calendar.</p>
      </aside>
    )
  }
  const diff = Math.round(month.everyday_vs_peers_pct)
  return (
    <aside className="card outlook-card">
      <p className="eyebrow">Selected month</p>
      <h2>{title}</h2>
      <div className="outlook-list">
        <div><span>Money in</span><strong className="positive-value">{currency.format(month.income)}</strong></div>
        <div><span>Bills, loan and fees</span><strong>{currency.format(month.bills)}</strong></div>
        <div><span>Everyday spending</span><strong>{currency.format(month.everyday)}</strong></div>
        <div>
          <span>{month.saved >= 0 ? 'Saved' : 'Drawn from savings'}</span>
          <strong className={month.saved >= 0 ? 'positive-value' : 'negative-value'}>{currency.format(Math.abs(month.saved))}</strong>
        </div>
      </div>
      <div className="insight-box outlook-insight">
        <img className="astro-icon" src="/assets/astro-avatar.svg" alt="" aria-hidden="true" />
        <p>
          Your everyday spending this month was <strong>{Math.abs(diff)}% {diff >= 0 ? 'above' : 'below'}</strong> the
          typical customer in the dataset.
        </p>
      </div>
    </aside>
  )
}

function WeekSummary({ days }: { days: CalendarResponse['last_seven_days'] }) {
  const maxSpend = Math.max(...days.map((day) => day.amount), 0)
  const total = days.reduce((sum, day) => sum + day.amount, 0)

  return (
    <section className="week-summary">
      <div className="section-heading">
        <div><p className="eyebrow">Last seven days</p><h2>Week at a glance</h2></div>
        <span className="muted-copy">Total spent {currency.format(total)}</span>
      </div>
      <div className="week-cards">
        {days.map((day) => (
          <article className="week-day-card" key={day.date}>
            <span>{dayLabel.format(toDate(day.date))}</span>
            <div className="week-bar-track"><i style={{ height: `${maxSpend > 0 ? (day.amount / maxSpend) * 100 : 0}%` }} /></div>
            <strong>{currency.format(day.amount)}</strong>
          </article>
        ))}
      </div>
    </section>
  )
}

function WeekView({ data }: { data: CalendarResponse }) {
  const onTrack = data.overspent_since_payday === undefined || data.spent_since_payday <= data.expected_deposit
  return (
    <section className="week-view-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Daily view</p><h2>Day {data.pay_period_day} of {data.pay_period_length} in this pay period</h2></div>
        <span className={`status-badge ${onTrack ? '' : 'watch'}`}>{onTrack ? 'Pay period on track' : 'Spending ahead of income'}</span>
      </div>
      <WeekSummary days={data.last_seven_days} />
    </section>
  )
}

function YearView({ months }: { months: Months }) {
  const maxAbs = Math.max(...months.map((month) => Math.abs(month.saved)), 1)
  const total = months.reduce((sum, month) => sum + month.saved, 0)
  const best = months.reduce((top, month) => (month.saved > top.saved ? month : top), months[0])
  const worst = months.reduce((low, month) => (month.saved < low.saved ? month : low), months[0])

  return (
    <section className="year-view-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Savings history</p><h2>Last 12 months</h2></div>
        <span className="muted-copy">Net {total >= 0 ? 'saved' : 'drawn'} <strong>{currency.format(Math.abs(total))}</strong></span>
      </div>
      <div className="card year-chart-card">
        <div className="year-chart">
          {months.map((month) => (
            <div className="year-bar-column" key={month.month} title={`${month.month}: ${currency.format(month.saved)}`}>
              <div className={`year-bar ${month.saved < 0 ? 'is-negative' : ''}`} style={{ height: `${(Math.abs(month.saved) / maxAbs) * 100}%` }} />
              <span>{shortMonth.format(toDate(`${month.month}-01`))}</span>
            </div>
          ))}
        </div>
        {best && worst && (
          <div className="insight-box year-insight">
            <img className="astro-icon" src="/assets/astro-avatar.svg" alt="" aria-hidden="true" />
            <p>
              You saved the most in <strong>{monthName.format(toDate(`${best.month}-01`))}</strong> ({currency.format(best.saved)}).
              {worst.saved < 0 && <> Your toughest month was <strong>{monthName.format(toDate(`${worst.month}-01`))}</strong>, when you drew {currency.format(Math.abs(worst.saved))} from savings.</>}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
