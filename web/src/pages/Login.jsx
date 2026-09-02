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
  const [mode, setMode] = useState('email'); // 'email' | 'staff'
  const [email, setEmail] = useState('stateadmin@education.gov');
  const [staffId, setStaffId] = useState('');
  const [password, setPassword] = useState('StateAdmin@2026');

  const submit = async (event) => {
    event.preventDefault();
    dispatch(clearError());
    const credentials = mode === 'staff' ? { staffId, password } : { email, password };
    const result = await dispatch(login(credentials));
    if (login.fulfilled.match(result)) {
      navigate(STATE_ROLES.has(result.payload.role) ? '/state' : '/school', { replace: true });
    }
  };

  const useDemo = (account) => {
    setMode('email');
    setEmail(account.email);
    setPassword(account.password);
  };

  return (
    <div className="auth">
      <section className="auth__pane">
        <div className="auth__brand"><Logo size={54} /></div>
        <h1 className="auth__title">Sign in to NE-EMIS</h1>
        <p className="auth__lede">North-East Education Management Information System — school administration and state academic oversight.</p>
        <div className="auth__modes" role="tablist" aria-label="Sign-in method">
          <button type="button" role="tab" aria-selected={mode === 'email'} className={`auth__mode ${mode === 'email' ? 'is-active' : ''}`} onClick={() => setMode('email')}>Email &amp; password</button>
          <button type="button" role="tab" aria-selected={mode === 'staff'} className={`auth__mode ${mode === 'staff' ? 'is-active' : ''}`} onClick={() => setMode('staff')}>Staff ID + PIN</button>
        </div>
        <form className="form" onSubmit={submit}>
          {mode === 'email' ? (
            <label className="field"><span className="field__label">Email address</span><input className="input" type="email" value={email} autoComplete="username" onChange={(event) => setEmail(event.target.value)} required /></label>
          ) : (
            <label className="field"><span className="field__label">Staff ID</span><input className="input" type="text" value={staffId} placeholder="e.g. NE-TID-2026-0042" autoComplete="username" onChange={(event) => setStaffId(event.target.value)} required /></label>
          )}
          <label className="field"><span className="field__label">{mode === 'staff' ? 'PIN / Password' : 'Password'}</span><input className="input" type="password" value={password} autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <p className="alert alert--danger">{error}</p>}
          <button type="submit" className="btn btn--primary btn--block" disabled={status === 'loading'}>{status === 'loading' ? 'Signing in…' : 'Sign in'}</button>
        </form>
        {mode === 'staff' && (
          <p className="auth__footnote">Teaching staff can sign in with the Staff ID printed on their NE-TID card. Your School Manager can look it up under Teachers.</p>
        )}
        <div className="demo">
          <h2 className="demo__title">Initial local accounts</h2>
          <ul className="demo__list">{DEMO_ACCOUNTS.map((account) => <li key={account.email}><button type="button" className="demo__item" onClick={() => useDemo(account)}><span className="demo__role">{account.role}</span><span className="demo__email">{account.email}</span><span className="demo__note">{account.note}</span></button></li>)}</ul>
        </div>
      </section>
      <aside className="auth__aside"><div className="auth__aside-inner"><h2>One system, clear boundaries</h2><ul className="feature-list"><li><strong>State Admin</strong><span>Creates school tenants, provisions Class 1–12 templates, and controls next roll numbers.</span></li><li><strong>Inspector</strong><span>Reads live academic structure, class rosters, and teacher assignments across schools.</span></li><li><strong>School Administration</strong><span>Manages students, teachers, subjects, schedules, and private financial records.</span></li></ul><p className="auth__footnote">The financial tier is structurally unavailable to every State role.</p></div></aside>
    </div>
  );
}
