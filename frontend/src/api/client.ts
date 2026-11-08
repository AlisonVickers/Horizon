export type StandingOrder = {
  purpose: string
  amount: number
}

export type Profile = {
  income: number
  fixed_costs: number
  spending: number
  buffer: number
  household_bills: number
  loan_payment: number
  everyday_spending: number
}

export type UpcomingExpense = { name: string; purpose: string; amount: number; due_date: string | null; key: string }

export type Benchmark = {
  label: string
  you: number
  peer_median: number
  difference_pct: number
  percentile: number
  is_good: boolean
}

export type HomeResponse = {
  account_id: number
  current_date: string | null
  last_payday: string
  next_payday: string
  days_until_payday: number
  pay_period_day: number
  pay_period_length: number
  expected_deposit: number
  spent_since_payday: number
  flexible_spending_remaining: number
  overspent_since_payday: number
  profile: Profile
  benchmarks: Benchmark[]
  summary_month: string
  balance: number
  latest_month: {
    income: number
    spending: number
    flexible_spending_left: number
  }
  upcoming_expenses: UpcomingExpense[]
  due_before_payday: number
  savings_goal: { name: string; target: number; current: number; progress_pct: number; rationale: string } | null
  standing_orders: UpcomingExpense[]
  recent_transactions: Array<{
    date: string
    direction: string
    purpose: string | null
    amount: number
    signed_amount: number
    balance: number
  }>
}

export type BudgetResponse = {
  account_id: number
  month: string
  current_date: string
  pay_period_day: number
  pay_period_length: number
  total_income: number
  total_spending: number
  categories: Array<{ name: string; amount: number }>
  goals: Array<{
    name: string
    monthly_savings: number
    monthly_limit: number
    rationale: string
  }>
}

export type ScenarioResponse = {
  account_id: number
  current_date: string
  next_payday: string
  days_until_payday: number
  runway_months: number
  income_after: number
  spending_after: number
  loan_payment: number
  buffer: number
  one_off_costs: number
  income_after_shock: number
  spending_after_shock: number
  gap: number
  runway: number
  profile: Profile
}

export type CalendarResponse = {
  account_id: number
  as_of: string
  current_date: string
  last_payday: string
  next_payday: string
  days_until_payday: number
  pay_period_day: number
  pay_period_length: number
  expected_deposit: number
  spent_since_payday: number
  overspent_since_payday: number
  events: Array<{
    date: string | null
    type: string
    label: string
    amount: number
    source: string
  }>
  months: Array<{
    month: string
    income: number
    bills: number
    everyday: number
    spending: number
    saved: number
    everyday_vs_peers_pct: number
  }>
  last_seven_days: Array<{ date: string; amount: number }>
  peer_everyday_median: number
}

export type DashboardResponse = {
  account_id: number
  data_as_of: string | null
  period: { start_date: string; end_date: string }
  balance: { historical_month_end_balance: number | null; as_of: string | null; is_live: boolean }
  cashflow: { predicted_recurring_income: number; predicted_recurring_expenses: number; event_count: number }
  projected_balance: {
    starting_balance: number
    projected_ending_balance: number
    lowest_projected_balance: number
    timeline: Array<{ date: string; category: string; event_type: string; amount: number; projected_balance: number }>
  } | null
  balance_alerts: {
    status: 'ok' | 'warning' | 'unavailable'
    safety_buffer: number
    alerts: Array<{ date: string | null; type: string; projected_balance: number; shortfall: number }>
  }
}

export type AssistantResponse = {
  message: string
  data: Record<string, unknown>
  tool_trace: string[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function getHome(accountId: number) {
  return request<HomeResponse>(`/accounts/${accountId}/home`)
}

export function getBudgets(accountId: number) {
  return request<BudgetResponse>(`/accounts/${accountId}/budgets`)
}

export function runScenario(
  accountId: number,
  shocks: Array<{ name: string; value: number }>,
) {
  return request<ScenarioResponse>(`/accounts/${accountId}/scenarios/run`, {
    method: 'POST',
    body: JSON.stringify({ shocks }),
  })
}

export function getCalendar(accountId: number) {
  return request<CalendarResponse>(`/accounts/${accountId}/calendar`)
}

export function askAssistant(accountId: number, prompt: string) {
  return request<AssistantResponse>(`/accounts/${accountId}/assistant`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

/** Heena's dashboard: projects the balance forward from the last month-end using detected recurring events. */
export function getDashboard(accountId: number, startDate: string, endDate: string, safetyBuffer = 500) {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate, safety_buffer: String(safetyBuffer) })
  return request<DashboardResponse>(`/api/accounts/${accountId}/dashboard?${query}`)
}
