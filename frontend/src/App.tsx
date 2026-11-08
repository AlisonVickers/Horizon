import { useState } from 'react'
import { Home } from './components/home/Home'
import { Calendar } from './components/calendar/Calendar'
import { Budget } from './components/budget/Budget'
import { Scenarios } from './components/scenarios/Scenarios'
import { TopNav } from './components/layout/TopNav'
import './App.css'

type Tab = 'Home' | 'Calendar' | 'Budget' | 'Scenarios'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('Home')

  return (
    <div className="app-shell">
      <TopNav activeTab={activeTab} onTabChange={setActiveTab} />
      {activeTab === 'Home' && <Home />}
      {activeTab === 'Calendar' && <Calendar />}
      {activeTab === 'Budget' && <Budget />}
      {activeTab === 'Scenarios' && <Scenarios />}
    </div>
  )
}

export default App
