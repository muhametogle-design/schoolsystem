import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { clearError, login } from '../features/auth/authSlice';

const STATE_ROLES = new Set(['state_admin', 'inspector', 'state_inspector']);

const DEMO_ACCOUNTS = [
  {
    role: 'State Admin',
    email: 'stateadmin@education.gov',
    password: 'StateAdmin@2026',
    note: 'Provision schools and oversee roll sequences; never sees billing.',
  },
  {
    role: 'Inspector',
    email: 'inspector@education.gov',
    password: 'State@2026',
    note: 'Read-only cross-school academic visibility; no financial access.',
  },
  {
    role: 'School Manager (Nugaal)',
    email: 'manager@nugaal.edu.so',
    password: 'School@2026',
    note: 'Full tenant ERP including staff, curriculum, and private billing.',
  },
  {
    role: 'Teacher (Nugaal)',
    email: 'teacher@nugaal.edu.so',
    password: 'Teach@2026',
    note: 'Teaching roster, attendance, and assessment entry.',
  },
];

export default function Login() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { status, error } = useSelector((state) => state.auth);
  const [email, setEmail] = useState('stateadmin@education.gov');
  const [password, setPassword] = useState('StateAdmin@2026');

  const submit = async (event) => {
    event.preventDefault();
    dispatch(clearError());
    const result = await dispatch(login({ email, password }));
    if (login.fulfilled.match(result)) {
      navigate(STATE_ROLES.has(result.payload.role) ? '/state' : '/school', { replace: true });
    }
  };

  const useDemo = (account) => {
    setEmail(account.email);
    setPassword(account.password);
  };

  return (
    <div className="auth">
      <section className="auth__pane">
        <div className="auth__brand"><Logo size={54} /></div>
        <h1 className="auth__title">Sign in to Educta Matrix</h1>
        <p className="auth__lede">The Unified Operating System for Regional Education — school administration, state telemetry, and student access.</p>
        <form className="form" onSubmit={submit}>
          <label className="field"><span className="field__label">Email address</span><input className="input" type="email" value={email} autoComplete="username" onChange={(event) => setEmail(event.target.value)} required /></label>
          <label className="field"><span className="field__label">Password</span><input className="input" type="password" value={password} autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <p className="alert alert--danger">{error}</p>}
          <button type="submit" className="btn btn--primary btn--block" disabled={status === 'loading'}>{status === 'loading' ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <div className="demo">
          <div style={{ marginBottom: '1rem', padding: '0.75rem', borderRadius: '8px', background: 'rgba(37, 99, 235, 0.08)', border: '1px solid rgba(37, 99, 235, 0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: '0.85rem', color: '#2563eb' }}>Educta Direct Portal</strong>
                <p style={{ margin: 0, fontSize: '0.75rem', color: '#64748b' }}>Student results, QR verify & State telemetry</p>
              </div>
              <button
                type="button"
                className="btn btn--secondary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                onClick={() => navigate('/direct')}
              >
                Launch Direct
              </button>
            </div>
          </div>
          <h2 className="demo__title">Initial local accounts</h2>
          <ul className="demo__list">{DEMO_ACCOUNTS.map((account) => <li key={account.email}><button type="button" className="demo__item" onClick={() => useDemo(account)}><span className="demo__role">{account.role}</span><span className="demo__email">{account.email}</span><span className="demo__note">{account.note}</span></button></li>)}</ul>
        </div>
      </section>
      <aside className="auth__aside"><div className="auth__aside-inner"><h2>One system, clear boundaries</h2><ul className="feature-list"><li><strong>State Admin</strong><span>Creates school tenants, provisions Class 1–12 templates, and controls next roll numbers.</span></li><li><strong>Inspector</strong><span>Reads live academic structure, class rosters, and teacher assignments across schools.</span></li><li><strong>School Administration</strong><span>Manages students, teachers, subjects, schedules, and private financial records.</span></li></ul><p className="auth__footnote">The financial tier is structurally unavailable to every State role.</p></div></aside>
    </div>
  );
}
