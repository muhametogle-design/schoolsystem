import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { clearError, login } from '../features/auth/authSlice';

const DEMO_ACCOUNTS = [
  {
    role: 'State Inspector',
    email: 'inspector@education.gov',
    password: 'State@2026',
    note: 'Regional oversight — no financial access',
  },
  {
    role: 'School Manager',
    email: 'manager@greenfield.edu',
    password: 'School@2026',
    note: 'Full ERP including private billing',
  },
  {
    role: 'Teacher',
    email: 'teacher@greenfield.edu',
    password: 'Teach@2026',
    note: 'Attendance and marks entry',
  },
];

export default function Login() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { status, error } = useSelector((state) => state.auth);

  const [email, setEmail] = useState('inspector@education.gov');
  const [password, setPassword] = useState('State@2026');

  const submit = async (event) => {
    event.preventDefault();
    dispatch(clearError());
    const result = await dispatch(login({ email, password }));
    if (login.fulfilled.match(result)) {
      const role = result.payload.role;
      navigate(role === 'state_inspector' ? '/state' : '/school', { replace: true });
    }
  };

  const useDemo = (account) => {
    setEmail(account.email);
    setPassword(account.password);
  };

  return (
    <div className="auth">
      <section className="auth__pane">
        <div className="auth__brand">
          <Logo size={54} />
        </div>

        <h1 className="auth__title">Sign in to NE-EMIS</h1>
        <p className="auth__lede">
          North-East Education Management Information System — state compliance monitoring
          and private school administration.
        </p>

        <form className="form" onSubmit={submit}>
          <label className="field">
            <span className="field__label">Email address</span>
            <input
              className="input"
              type="email"
              value={email}
              autoComplete="username"
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="field">
            <span className="field__label">Password</span>
            <input
              className="input"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && <p className="alert alert--danger">{error}</p>}

          <button
            type="submit"
            className="btn btn--primary btn--block"
            disabled={status === 'loading'}
          >
            {status === 'loading' ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="demo">
          <h2 className="demo__title">Demo accounts</h2>
          <ul className="demo__list">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button type="button" className="demo__item" onClick={() => useDemo(account)}>
                  <span className="demo__role">{account.role}</span>
                  <span className="demo__email">{account.email}</span>
                  <span className="demo__note">{account.note}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <aside className="auth__aside">
        <div className="auth__aside-inner">
          <h2>One platform, three mandates</h2>
          <ul className="feature-list">
            <li>
              <strong>State Authority</strong>
              <span>Live compliance map, red-alarm escalation and read-only academic oversight.</span>
            </li>
            <li>
              <strong>School Administration</strong>
              <span>Enrolment, fee standing, performance analytics and the exam release valve.</span>
            </li>
            <li>
              <strong>Teaching Staff</strong>
              <span>Daily rosters before the 12:00 deadline and continuous assessment entry.</span>
            </li>
          </ul>
          <p className="auth__footnote">
            Financial data is cryptographically walled off from every state role.
          </p>
        </div>
      </aside>
    </div>
  );
}
