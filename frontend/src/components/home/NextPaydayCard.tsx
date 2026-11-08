type NextPaydayCardProps = {
  paydayDate: string
  daysAway: number
  expectedDeposit: number
  spent: number
  remaining: number
  overspent: number
  balance: number
  lastPayday: string
  flexibleSpending: number
  dailyBudget: number
}

const currency = new Intl.NumberFormat('en-CA', {
  currency: 'CAD',
  style: 'currency',
  maximumFractionDigits: 0,
})

export function NextPaydayCard({
  paydayDate,
  daysAway,
  expectedDeposit,
  spent,
  remaining,
  overspent,
  balance,
  lastPayday,
  flexibleSpending,
  dailyBudget,
}: NextPaydayCardProps) {
  const isOver = overspent > 0
  const spentWidth = expectedDeposit > 0 ? `${Math.min((spent / expectedDeposit) * 100, 100)}%` : '0%'

  return (
    <article className="card payday-card">
      <div className="payday-heading">
        <div>
          <h2>Next payday is {paydayDate}</h2>
          <p className="payday-meta">
            {daysAway} days away <span>·</span> last deposit {currency.format(expectedDeposit)}
          </p>
        </div>
      </div>

      <div className={`spending-progress ${isOver ? 'is-over' : ''}`} aria-label={`${currency.format(spent)} spent`}>
        <span style={{ width: spentWidth }} />
      </div>
      <div className="progress-labels">
        <span>{currency.format(spent)} spent</span>
        {isOver
          ? <span className="overspent-value">{currency.format(overspent)} over</span>
          : <span>{currency.format(remaining)} remaining</span>}
      </div>
      <div className="payday-dates">
        <span>Last payday<strong>{lastPayday}</strong></span>
        <span>Next payday<strong>{paydayDate}</strong></span>
      </div>

      <div className="insight-box payday-insight">
        <span className="astro-icon" aria-hidden="true">✦</span>
        {isOver ? (
          <p>
            You have spent <strong>{currency.format(overspent)} more</strong> than your last deposit. Your
            {' '}{currency.format(balance)} balance covers it, but try to hold off on big withdrawals until payday.
          </p>
        ) : (
          <p>
            You have <strong>{currency.format(flexibleSpending)}</strong> of flexible spending this pay
            period. About <strong>{currency.format(dailyBudget)} a day</strong> keeps you on budget.
          </p>
        )}
      </div>
    </article>
  )
}
