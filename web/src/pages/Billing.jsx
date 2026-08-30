import { useEffect, useState } from 'react';
import { api } from '../api/client';

const EMPTY_INVOICE = { student_id: '', description: '', amount_due: '', due_date: '' };

function readable(error) {
  return error?.message || 'Unable to update billing records.';
}

/** Manager-only private billing editor. No State route can render this page. */
export default function Billing() {
  const [profile, setProfile] = useState(null);
  const [rates, setRates] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [students, setStudents] = useState([]);
  const [invoice, setInvoice] = useState(EMPTY_INVOICE);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [profileData, ratesData, invoicesData, studentsData] = await Promise.all([
        api('/api/v1/school/profile'),
        api('/api/v1/school/finance/tuition-rates'),
        api('/api/v1/school/finance/invoices'),
        api('/api/v1/school/students'),
      ]);
      setProfile({
        ...profileData,
        billing: profileData.billing ?? {},
      });
      setRates(ratesData.tuition_rates ?? []);
      setInvoices(invoicesData.invoices ?? []);
      setStudents(studentsData.students ?? []);
    } catch (loadError) {
      setError(readable(loadError));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveProfile = async (event) => {
    event.preventDefault();
    if (!profile) return;
    setSaving(true);
    setError('');
    try {
      await api('/api/v1/school/profile', {
        method: 'PATCH',
        body: {
          school_name: profile.school_name,
          proprietor_name: profile.proprietor_name || null,
          contact_phone: profile.contact_phone || null,
          contact_email: profile.contact_email || null,
          physical_address: profile.physical_address || null,
          billing_contact_name: profile.billing.contact_name || null,
          billing_phone: profile.billing.phone || null,
          billing_email: profile.billing.email || null,
          billing_address: profile.billing.address || null,
          billing_notes: profile.billing.notes || null,
        },
      });
      setNotice('School identity and private billing contact details saved.');
    } catch (saveError) {
      setError(readable(saveError));
    } finally {
      setSaving(false);
    }
  };

  const editRate = async (rate) => {
    const amount = window.prompt(`Term fee for ${rate.class_level}`, rate.base_tuition_amount);
    if (amount === null) return;
    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError('Enter a positive tuition amount.');
      return;
    }
    try {
      await api(`/api/v1/school/finance/tuition-rates/${rate.id}`, {
        method: 'PATCH',
        body: { base_tuition_amount: numericAmount },
      });
      await load();
      setNotice(`${rate.class_level} tuition rate updated.`);
    } catch (saveError) {
      setError(readable(saveError));
    }
  };

  const createInvoice = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api('/api/v1/school/finance/invoices', {
        method: 'POST',
        body: {
          student_id: Number(invoice.student_id),
          description: invoice.description,
          amount_due: Number(invoice.amount_due),
          due_date: invoice.due_date || null,
        },
      });
      setInvoice(EMPTY_INVOICE);
      await load();
      setNotice('Private student invoice created.');
    } catch (saveError) {
      setError(readable(saveError));
    } finally {
      setSaving(false);
    }
  };

  const editInvoice = async (entry) => {
    const description = window.prompt('Invoice description', entry.description);
    if (description === null || !description.trim()) return;
    const amount = window.prompt('Amount due', entry.amount_due);
    if (amount === null) return;
    const dueDate = window.prompt('Due date (YYYY-MM-DD; blank to clear)', entry.due_date ?? '');
    if (dueDate === null) return;
    try {
      await api(`/api/v1/school/finance/invoices/${entry.id}`, {
        method: 'PATCH',
        body: { description: description.trim(), amount_due: Number(amount), due_date: dueDate || null },
      });
      await load();
      setNotice('Invoice updated.');
    } catch (saveError) {
      setError(readable(saveError));
    }
  };

  const removeInvoice = async (entry) => {
    if (!window.confirm(`Delete invoice for ${entry.student}? This also deletes its payments.`)) return;
    try {
      await api(`/api/v1/school/finance/invoices/${entry.id}`, { method: 'DELETE' });
      await load();
      setNotice('Invoice deleted.');
    } catch (deleteError) {
      setError(readable(deleteError));
    }
  };

  const addPayment = async (entry) => {
    const amount = window.prompt(`Payment amount (balance ${entry.balance})`, entry.balance);
    if (amount === null) return;
    const paymentMethod = window.prompt('Payment method: Cash, Mobile_Money, Bank_Transfer, or Card', 'Cash');
    if (paymentMethod === null) return;
    try {
      await api(`/api/v1/school/finance/invoices/${entry.id}/payments`, {
        method: 'POST',
        body: { amount: Number(amount), payment_method: paymentMethod, reference_number: null },
      });
      await load();
      setNotice('Payment recorded.');
    } catch (paymentError) {
      setError(readable(paymentError));
    }
  };

  const removePayment = async (entry, payment) => {
    if (!window.confirm(`Remove ${payment.amount} payment from this invoice?`)) return;
    try {
      await api(`/api/v1/school/finance/invoices/${entry.id}/payments/${payment.id}`, { method: 'DELETE' });
      await load();
      setNotice('Payment removed and invoice balance recalculated.');
    } catch (deleteError) {
      setError(readable(deleteError));
    }
  };

  return (
    <div className="stack">
      <section className="card private-card">
        <header className="card__head">
          <h2 className="card__title">School identity & billing profile</h2>
          <span className="card__hint">Private tenant data — unavailable to State Admins and Inspectors.</span>
        </header>
        {error && <p className="alert alert--danger">{error}</p>}
        {notice && <p className="alert alert--ok">{notice}</p>}
        {!profile ? <p className="empty">Loading billing profile…</p> : (
          <form className="student-form__grid" onSubmit={saveProfile}>
            <label className="field"><span className="field__label">School name</span><input className="input" value={profile.school_name ?? ''} onChange={(e) => setProfile({ ...profile, school_name: e.target.value })} required /></label>
            <label className="field"><span className="field__label">Proprietor</span><input className="input" value={profile.proprietor_name ?? ''} onChange={(e) => setProfile({ ...profile, proprietor_name: e.target.value })} /></label>
            <label className="field"><span className="field__label">School code</span><input className="input" value={profile.school_code ?? ''} disabled aria-label="State-assigned school code" /></label>
            <label className="field"><span className="field__label">Main phone</span><input className="input" value={profile.contact_phone ?? ''} onChange={(e) => setProfile({ ...profile, contact_phone: e.target.value })} /></label>
            <label className="field"><span className="field__label">Main email</span><input className="input" type="email" value={profile.contact_email ?? ''} onChange={(e) => setProfile({ ...profile, contact_email: e.target.value })} /></label>
            <label className="field field--wide"><span className="field__label">Address</span><textarea className="input" rows="2" value={profile.physical_address ?? ''} onChange={(e) => setProfile({ ...profile, physical_address: e.target.value })} /></label>
            <label className="field"><span className="field__label">Billing contact</span><input className="input" value={profile.billing.contact_name ?? ''} onChange={(e) => setProfile({ ...profile, billing: { ...profile.billing, contact_name: e.target.value } })} /></label>
            <label className="field"><span className="field__label">Billing phone</span><input className="input" value={profile.billing.phone ?? ''} onChange={(e) => setProfile({ ...profile, billing: { ...profile.billing, phone: e.target.value } })} /></label>
            <label className="field"><span className="field__label">Billing email</span><input className="input" type="email" value={profile.billing.email ?? ''} onChange={(e) => setProfile({ ...profile, billing: { ...profile.billing, email: e.target.value } })} /></label>
            <label className="field field--wide"><span className="field__label">Billing address</span><textarea className="input" rows="2" value={profile.billing.address ?? ''} onChange={(e) => setProfile({ ...profile, billing: { ...profile.billing, address: e.target.value } })} /></label>
            <label className="field field--wide"><span className="field__label">Billing notes</span><textarea className="input" rows="2" value={profile.billing.notes ?? ''} onChange={(e) => setProfile({ ...profile, billing: { ...profile.billing, notes: e.target.value } })} /></label>
            <div className="student-form__foot field--wide"><button className="btn btn--primary" disabled={saving}>{saving ? 'Saving…' : 'Save billing profile'}</button></div>
          </form>
        )}
      </section>

      <section className="card private-card">
        <header className="card__head"><h2 className="card__title">Termly tuition rates</h2><span className="card__hint">Edit a rate to apply your school’s current billing configuration.</span></header>
        <div className="table-wrap"><table className="table"><thead><tr><th>Class</th><th>Cycle</th><th>Amount</th><th /></tr></thead><tbody>{rates.map((rate) => <tr key={rate.id}><td>{rate.class_level}</td><td>{rate.billing_cycle}</td><td>{Number(rate.base_tuition_amount).toLocaleString()}</td><td className="table__actions"><button className="btn btn--small" type="button" onClick={() => editRate(rate)}>Edit</button></td></tr>)}</tbody></table></div>
      </section>

      <section className="card private-card">
        <header className="card__head"><h2 className="card__title">Invoices & payments</h2><span className="card__hint">Create, edit, delete, and reconcile private student billing records.</span></header>
        <form className="management-form management-form--invoice" onSubmit={createInvoice}>
          <label className="field"><span className="field__label">Student</span><select className="input" value={invoice.student_id} onChange={(e) => setInvoice({ ...invoice, student_id: e.target.value })} required><option value="">Select student…</option>{students.map((student) => <option key={student.id} value={student.id}>{student.roll_number ?? student.national_student_id} · {student.first_name} {student.last_name}</option>)}</select></label>
          <label className="field"><span className="field__label">Description</span><input className="input" value={invoice.description} onChange={(e) => setInvoice({ ...invoice, description: e.target.value })} required placeholder="Term 1 tuition" /></label>
          <label className="field"><span className="field__label">Amount due</span><input className="input" type="number" min="0" step="0.01" value={invoice.amount_due} onChange={(e) => setInvoice({ ...invoice, amount_due: e.target.value })} required /></label>
          <label className="field"><span className="field__label">Due date</span><input className="input" type="date" value={invoice.due_date} onChange={(e) => setInvoice({ ...invoice, due_date: e.target.value })} /></label>
          <button className="btn btn--primary" disabled={saving}>Create invoice</button>
        </form>
        <div className="table-wrap"><table className="table"><thead><tr><th>Student</th><th>Description</th><th>Due / paid / balance</th><th>Status</th><th>Payments</th><th /></tr></thead><tbody>{invoices.map((entry) => <tr key={entry.id}><td>{entry.student}</td><td>{entry.description}<br /><span className="muted">Due {entry.due_date ?? '—'}</span></td><td>{entry.amount_due} / {entry.amount_paid} / <strong>{entry.balance}</strong></td><td>{entry.status}</td><td>{entry.payments?.length ? entry.payments.map((payment) => <div className="payment-line" key={payment.id}>{payment.amount} {payment.method} <button type="button" className="link-button link-button--danger" onClick={() => removePayment(entry, payment)}>remove</button></div>) : '—'}</td><td className="table__actions"><button type="button" className="btn btn--small" onClick={() => addPayment(entry)} disabled={entry.balance <= 0}>Payment</button>{' '}<button type="button" className="btn btn--small" onClick={() => editInvoice(entry)}>Edit</button>{' '}<button type="button" className="btn btn--small btn--danger" onClick={() => removeInvoice(entry)}>Delete</button></td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
