const card  = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4, padding: '16px 20px' }
const lbl   = { fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b', display: 'block', marginBottom: 10 }
const mono  = { fontFamily: 'monospace', fontSize: 12 }

const MODELS = [
  {
    name: 'Isolation Forest',
    type: 'Unsupervised',
    params: { n_estimators: 100, contamination: 0.05, max_samples: 'auto', random_state: 42 },
    trained_on: '200,000 BENIGN rows',
    description: 'Randomly partitions feature space with binary trees. Anomalies are isolated in fewer splits than dense, normal-traffic clusters.',
  },
  {
    name: 'Local Outlier Factor',
    type: 'Unsupervised',
    params: { n_neighbors: 20, contamination: 0.05, novelty: true },
    trained_on: '50,000 BENIGN rows',
    description: 'Scores each point by comparing its local density to its 20 nearest neighbours. Low-density points receive high LOF scores.',
  },
  {
    name: 'One-Class SVM',
    type: 'Unsupervised',
    params: { kernel: 'rbf', nu: 0.05, gamma: 'scale' },
    trained_on: '30,000 BENIGN rows',
    description: 'Fits a hypersphere around normal traffic in a kernel-mapped feature space. Points outside the boundary are anomalous.',
  },
  {
    name: 'Random Forest',
    type: 'Supervised',
    params: { n_estimators: 100, class_weight: 'balanced', max_features: 'sqrt', random_state: 42 },
    trained_on: '150,000 rows (all classes)',
    description: 'Supervised classifier trained on labeled BENIGN and attack flows. Provides explicit knowledge of attack patterns; significantly improves recall.',
  },
]

const DATASET = [
  ['Total flows',   '2,212,030'],
  ['BENIGN',        '1,671,484  (75.6%)'],
  ['Attack types',  '9 categories'],
  ['Features',      '77 numeric'],
]

export default function ModelsPanel() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        {MODELS.map(m => (
          <div key={m.name} style={card}>
            <span style={lbl}>Model</span>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>{m.name}</div>
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.07em', color: m.type === 'Supervised' ? '#f59e0b' : '#3b82f6', border: `1px solid ${m.type === 'Supervised' ? '#78350f' : '#1e3a5f'}`, padding: '1px 5px', borderRadius: 2 }}>{m.type.toUpperCase()}</span>
            </div>
            <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6, marginBottom: 14 }}>{m.description}</p>

            <span style={lbl}>Parameters</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
              {Object.entries(m.params).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ ...mono, color: '#64748b' }}>{k}</span>
                  <span style={{ ...mono, color: '#94a3b8' }}>{String(v)}</span>
                </div>
              ))}
            </div>

            <div style={{ paddingTop: 10, borderTop: '1px solid #2a2d3a', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>Trained on</span>
              <span style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace' }}>{m.trained_on}</span>
            </div>
          </div>
        ))}
      </div>

      <div style={card}>
        <span style={lbl}>Ensemble majority-vote logic</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto' }}>
          {MODELS.map((m, i) => (
            <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
              <div style={{ backgroundColor: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 4, padding: '10px 16px', textAlign: 'center', minWidth: 140 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: '#94a3b8', marginBottom: 4 }}>{m.name}</div>
                <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                  <span style={{ ...mono, fontSize: 11, color: '#10b981', border: '1px solid #064e3b', padding: '1px 5px', borderRadius: 2 }}>0 = normal</span>
                  <span style={{ ...mono, fontSize: 11, color: '#ef4444', border: '1px solid #7f1d1d', padding: '1px 5px', borderRadius: 2 }}>1 = anomaly</span>
                </div>
              </div>
              {i < MODELS.length - 1 && (
                <div style={{ padding: '0 10px', color: '#2a2d3a', fontSize: 18, userSelect: 'none' }}>+</div>
              )}
            </div>
          ))}

          <div style={{ padding: '0 16px', color: '#64748b', fontSize: 16 }}>→</div>

          <div style={{ backgroundColor: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 4, padding: '10px 16px' }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Vote sum</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ ...mono, fontSize: 12, color: '#64748b', width: 28, textAlign: 'center', border: '1px solid #2a2d3a', borderRadius: 2, padding: '1px 4px' }}>0–1</span>
                <span style={{ fontSize: 12, color: '#10b981', fontWeight: 500 }}>NORMAL</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ ...mono, fontSize: 12, color: '#ef4444', width: 28, textAlign: 'center', border: '1px solid #7f1d1d', borderRadius: 2, padding: '1px 4px' }}>2–4</span>
                <span style={{ fontSize: 12, color: '#ef4444', fontWeight: 500 }}>INTRUSION</span>
              </div>
            </div>
          </div>
        </div>
        <p style={{ fontSize: 12, color: '#64748b', marginTop: 12 }}>
          Threshold: ≥ 2 of 4 models vote anomaly → classified as INTRUSION and saved to database. Random Forest (supervised) provides explicit attack pattern knowledge; the three unsupervised models add generalization to unknown attack types.
        </p>
      </div>

      <div style={card}>
        <span style={lbl}>Dataset — CICIDS2017</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {DATASET.map(([k, v]) => (
            <div key={k} style={{ backgroundColor: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 4, padding: '10px 14px' }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{k}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', fontFamily: 'monospace' }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
