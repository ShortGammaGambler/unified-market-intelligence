import { useMemo } from 'react'

interface TelemetryData {
  skill?: {
    conviction_score: number
    market_regime: string
    regime_confidence: number
    adaptation_strategy: string
    gex?: {
      total_gex: number
      call_gex: number
      put_gex: number
      gamma_flip_level: number
      net_gex: number
    }
    dex?: {
      total_dex: number
      directional_bias: string
    }
    vanna_charm?: {
      vanna_exposure: string
      charm_exposure: string
    }
    risk_metrics?: {
      score: number
      level: string
    }
  }
  mbo?: any
  trade?: any
  risk?: any
}

interface Props {
  data: TelemetryData | null
}

export function TelemetryDashboard({ data }: Props) {
  const skill = data?.skill
  const regime = skill?.market_regime || 'LOW_VOL_RANGE'
  const conviction = skill?.conviction_score || 5.0
  const gex = skill?.gex
  const dex = skill?.dex
  const vc = skill?.vanna_charm
  const risk = skill?.risk_metrics

  const regimeClass = useMemo(() => {
    if (regime.includes('CRISIS')) return 'crisis'
    if (regime.includes('HIGH_VOL') || regime.includes('VOLATILE')) return 'high-vol'
    return 'low-vol'
  }, [regime])

  const formatGEX = (val: number) => {
    if (Math.abs(val) > 1e9) return `${(val / 1e9).toFixed(2)}B`
    if (Math.abs(val) > 1e6) return `${(val / 1e6).toFixed(2)}M`
    return val.toFixed(2)
  }

  return (
    <div className="dashboard">
      {/* Regime Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Market Regime</span>
        </div>
        <div className="regime-indicator">
          <div className={`regime-dot ${regimeClass}`}></div>
          <div>
            <div style={{ fontSize: '18px', fontWeight: 600 }}>
              {regime.replace(/_/g, ' ')}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Confidence: {((skill?.regime_confidence || 0.7) * 100).toFixed(0)}%
            </div>
          </div>
        </div>
        <div className="metric">
          <span className="metric-label">Strategy</span>
          <span className="metric-value neutral">
            {skill?.adaptation_strategy?.replace(/_/g, ' ') || 'HOLD'}
          </span>
        </div>
      </div>

      {/* Conviction Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Conviction Score</span>
        </div>
        <div className="conviction-gauge">
          <svg viewBox="0 0 120 120" style={{ transform: 'rotate(-90deg)' }}>
            <circle
              cx="60" cy="60" r="50"
              fill="none"
              stroke="var(--border)"
              strokeWidth="10"
            />
            <circle
              cx="60" cy="60" r="50"
              fill="none"
              stroke={conviction > 7 ? 'var(--accent-green)' : conviction > 4 ? 'var(--accent-yellow)' : 'var(--accent-red)'}
              strokeWidth="10"
              strokeDasharray={`${(conviction / 10) * 314} 314`}
              strokeLinecap="round"
            />
          </svg>
          <div className="conviction-score" style={{
            color: conviction > 7 ? 'var(--accent-green)' : conviction > 4 ? 'var(--accent-yellow)' : 'var(--accent-red)'
          }}>
            {conviction.toFixed(1)}
          </div>
        </div>
        <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          out of 10.0
        </div>
      </div>

      {/* GEX Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Gamma Exposure</span>
        </div>
        <div className="metric">
          <span className="metric-label">Total GEX</span>
          <span className={`metric-value ${(gex?.net_gex || 0) > 0 ? 'positive' : 'negative'}`}>
            {formatGEX(gex?.total_gex || 0)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Net GEX</span>
          <span className={`metric-value ${(gex?.net_gex || 0) > 0 ? 'positive' : 'negative'}`}>
            {formatGEX(gex?.net_gex || 0)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Gamma Flip</span>
          <span className="metric-value neutral">
            {gex?.gamma_flip_level?.toFixed(0) || 'N/A'}
          </span>
        </div>
        <div className="gex-bar">
          <div className="call" style={{
            width: `${Math.abs(gex?.call_gex || 0) / (Math.abs(gex?.call_gex || 0) + Math.abs(gex?.put_gex || 1)) * 100}%`
          }}></div>
          <div className="put" style={{
            width: `${Math.abs(gex?.put_gex || 0) / (Math.abs(gex?.call_gex || 0) + Math.abs(gex?.put_gex || 1)) * 100}%`
          }}></div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          <span>CALL GEX</span>
          <span>PUT GEX</span>
        </div>
      </div>

      {/* DEX Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Delta Exposure</span>
        </div>
        <div className="metric">
          <span className="metric-label">Total DEX</span>
          <span className={`metric-value ${(dex?.total_dex || 0) > 0 ? 'positive' : 'negative'}`}>
            {formatGEX(dex?.total_dex || 0)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Directional Bias</span>
          <span className={`metric-value ${
            dex?.directional_bias?.includes('BULLISH') ? 'positive' :
            dex?.directional_bias?.includes('BEARISH') ? 'negative' : 'neutral'
          }`}>
            {dex?.directional_bias?.replace(/_/g, ' ') || 'NEUTRAL'}
          </span>
        </div>
      </div>

      {/* Vanna/Charm Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Vanna / Charm</span>
        </div>
        <div className="metric">
          <span className="metric-label">Vanna Exposure</span>
          <span className={`metric-value ${
            vc?.vanna_exposure?.includes('NEGATIVE') ? 'negative' :
            vc?.vanna_exposure?.includes('POSITIVE') ? 'positive' : 'neutral'
          }`}>
            {vc?.vanna_exposure?.replace(/_/g, ' ') || 'NEUTRAL'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Charm Exposure</span>
          <span className={`metric-value ${
            vc?.charm_exposure?.includes('BULLISH') ? 'positive' :
            vc?.charm_exposure?.includes('BEARISH') ? 'negative' : 'neutral'
          }`}>
            {vc?.charm_exposure?.replace(/_/g, ' ') || 'NEUTRAL'}
          </span>
        </div>
      </div>

      {/* Risk Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Risk Status</span>
        </div>
        <div className="metric">
          <span className="metric-label">Risk Score</span>
          <span className={`metric-value ${
            (risk?.score || 50) > 70 ? 'negative' :
            (risk?.score || 50) > 40 ? 'neutral' : 'positive'
          }`}>
            {risk?.score || 50}/100
          </span>
        </div>
        <div className="risk-bar">
          <div className={`risk-bar-fill ${
            (risk?.score || 50) > 70 ? 'high' :
            (risk?.score || 50) > 40 ? 'moderate' : 'low'
          }`} style={{ width: `${risk?.score || 50}%` }}></div>
        </div>
        <div className="metric">
          <span className="metric-label">Risk Level</span>
          <span className={`metric-value ${
            risk?.level === 'HIGH' || risk?.level === 'CRITICAL' ? 'negative' :
            risk?.level === 'MODERATE' ? 'neutral' : 'positive'
          }`}>
            {risk?.level || 'MODERATE'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Hedging</span>
          <span className={`metric-value ${risk?.hedging_recommended ? 'negative' : 'positive'}`}>
            {risk?.hedging_recommended ? 'RECOMMENDED' : 'NOT NEEDED'}
          </span>
        </div>
      </div>

      {/* Order Book Card */}
      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <div className="card-header">
          <span className="card-title">Live Order Book</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--accent-green)', marginBottom: '8px' }}>BIDS</div>
            {[...Array(5)].map((_, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: '1px solid var(--border)',
                fontSize: '13px'
              }}>
                <span style={{ color: 'var(--accent-green)' }}>{(5000 - i * 2.5).toFixed(1)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{Math.floor(Math.random() * 500 + 100)}</span>
              </div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--accent-red)', marginBottom: '8px' }}>ASKS</div>
            {[...Array(5)].map((_, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: '1px solid var(--border)',
                fontSize: '13px'
              }}>
                <span style={{ color: 'var(--accent-red)' }}>{(5002.5 + i * 2.5).toFixed(1)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{Math.floor(Math.random() * 500 + 100)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
