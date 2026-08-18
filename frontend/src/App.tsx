import { useState, useEffect, useRef } from 'react'
import { TelemetryDashboard } from './components/TelemetryDashboard'

function App() {
  const [connected, setConnected] = useState(false)
  const [data, setData] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://localhost:8000/ws/all`)

      ws.onopen = () => {
        setConnected(true)
        console.log('WebSocket connected')
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          setData((prev: any) => ({ ...prev, [msg.type]: msg.data }))
        } catch (e) {
          console.error('Parse error:', e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        setTimeout(connectWebSocket, 3000)
      }

      wsRef.current = ws
    }

    connectWebSocket()

    return () => {
      wsRef.current?.close()
    }
  }, [])

  return (
    <div className="app">
      <header className="header">
        <h1>Unified Market Intelligence</h1>
        <div className="header-status">
          <span className={`status-badge ${connected ? 'live' : ''}`}>
            {connected ? 'LIVE' : 'CONNECTING'}
          </span>
        </div>
      </header>

      <aside className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-title">Navigation</div>
          <div className="nav-item active">Dashboard</div>
          <div className="nav-item">Analytics</div>
          <div className="nav-item">Agents</div>
          <div className="nav-item">Execution</div>
          <div className="nav-item">Risk</div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-title">Agents</div>
          <div className="agent-list">
            <div className="agent-card">
              <div className="agent-icon fordge">F</div>
              <div className="agent-info">
                <div className="agent-name">Fordge</div>
                <div className="agent-role">Research & Backtesting</div>
              </div>
            </div>
            <div className="agent-card">
              <div className="agent-icon atlas">A</div>
              <div className="agent-info">
                <div className="agent-name">Atlas</div>
                <div className="agent-role">Sentiment Analysis</div>
              </div>
            </div>
            <div className="agent-card">
              <div className="agent-icon phantom">P</div>
              <div className="agent-info">
                <div className="agent-name">Phantom</div>
                <div className="agent-role">Execution</div>
              </div>
            </div>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-title">Risk Status</div>
          <div className="metric">
            <span className="metric-label">Risk Level</span>
            <span className="metric-value neutral">MODERATE</span>
          </div>
          <div className="risk-bar">
            <div className="risk-bar-fill moderate" style={{ width: '45%' }}></div>
          </div>
        </div>
      </aside>

      <main className="main">
        <TelemetryDashboard data={data} />
      </main>
    </div>
  )
}

export default App
