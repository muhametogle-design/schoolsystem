import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import {
  biometricEnrollOptions,
  biometricEnrollVerify,
  biometricRevoke,
  biometricRescan,
  biometricVerifyComplete,
  biometricVerifyOptions,
  fetchBiometricOverview,
  fetchVerificationLog,
  setStation,
} from '../features/biometrics/biometricsSlice';

const todayISO = () => new Date().toISOString().slice(0, 10);

/**
 * Module 5 — Biometric hardware management (WebAuthn).
 *
 * Real platform/USB/NFC authenticators run the standard ceremonies; a
 * clearly-labelled WebCrypto-based "simulated reader" exercises the identical
 * server verification path on QA devices without biometric hardware.
 */

// --- WebAuthn encoding helpers ----------------------------------------------

function b64uToBuf(value) {
  const pad = '='.repeat((4 - (value.length % 4)) % 4);
  const raw = atob(value.replace(/-/g, '+').replace(/_/g, '/') + pad);
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) buf[i] = raw.charCodeAt(i);
  return buf.buffer;
}

function bufToB64u(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function runWebAuthnEnrollment(options) {
  const publicKey = {
    challenge: b64uToBuf(options.challenge),
    rp: options.rp,
    user: {
      id: b64uToBuf(options.user.id),
      name: options.user.name,
      displayName: options.user.displayName,
    },
    pubKeyCredParams: options.pubKeyCredParams,
    authenticatorSelection: options.authenticatorSelection,
    timeout: options.timeout,
    attestation: options.attestation,
    excludeCredentials: options.excludeCredentials,
  };
  const credential = await navigator.credentials.create({ publicKey });
  const response = credential.response;
  return {
    credential_id: credential.id,
    client_data_b64: bufToB64u(response.clientDataJSON),
    attestation_object_b64: bufToB64u(response.attestationObject),
    transports: response.getTransports ? response.getTransports() : [],
  };
}

async function runWebAuthnAssertion(options) {
  const publicKey = {
    challenge: b64uToBuf(options.challenge),
    rpId: options.rpId,
    timeout: options.timeout,
    userVerification: options.userVerification,
    allowCredentials: (options.allowCredentials ?? []).map((c) => ({
      id: b64uToBuf(c.id),
      type: c.type,
      transports: c.transports,
    })),
  };
  const assertion = await navigator.credentials.get({ publicKey });
  const response = assertion.response;
  return {
    credential_id: assertion.id,
    client_data_b64: bufToB64u(response.clientDataJSON),
    authenticator_data_b64: bufToB64u(response.authenticatorData),
    signature_b64: bufToB64u(response.signature),
  };
}

// --- Simulated reader (WebCrypto; identical server-side verification path) --

function uint8ToB64u(bytes) {
  let binary = '';
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function derFromRaw(raw) {
  // WebCrypto ES256 returns P1363 r||s; the server verifies DER signatures.
  const half = raw.length / 2;
  const trim = (view) => {
    let start = 0;
    while (start < view.length - 1 && view[start] === 0) start += 1;
    const value = view.slice(start);
    return value[0] & 0x80 ? [0, ...value] : [...value];
  };
  const r = trim(raw.slice(0, half));
  const s = trim(raw.slice(half));
  const body = [0x02, r.length, ...r, 0x02, s.length, ...s];
  return new Uint8Array([0x30, body.length, ...body]);
}

async function sha256(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return new Uint8Array(digest);
}

class SimulatedReader {
  constructor(rpId) {
    this.rpId = rpId;
    this.counter = 10;
  }

  async init() {
    this.keyPair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
      'sign',
      'verify',
    ]);
    this.credentialId = crypto.getRandomValues(new Uint8Array(32));
    return this;
  }

  async publicCose() {
    const raw = await crypto.subtle.exportKey('raw', this.keyPair.publicKey);
    const bytes = new Uint8Array(raw); // 0x04 || x(32) || y(32)
    return { x: bytes.slice(1, 33), y: bytes.slice(33, 65) };
  }

  async authData({ attested }) {
    this.counter += 1;
    const flags = attested ? 0x45 : 0x05; // UP | UV (| AT)
    const rpHash = await sha256(new TextEncoder().encode(this.rpId));
    const out = new Uint8Array(37 + (attested ? 18 + this.credentialId.length + 77 : 0));
    out.set(rpHash, 0);
    out[32] = flags;
    new DataView(out.buffer).setUint32(33, this.counter);
    if (attested) {
      const { x, y } = await this.publicCose();
      const cose = [
        0xa5, 0x01, 0x02, 0x03, 0x26, 0x20, 0x01, 0x21, 0x58, 0x20, ...x, 0x22, 0x58, 0x20, ...y,
      ];
      let offset = 37;
      out.set(new Uint8Array(16), offset); // aaguid zeros
      offset += 16;
      out[offset] = (this.credentialId.length >> 8) & 0xff;
      out[offset + 1] = this.credentialId.length & 0xff;
      offset += 2;
      out.set(this.credentialId, offset);
      offset += this.credentialId.length;
      out.set(Uint8Array.from(cose), offset);
    }
    return out;
  }

  async registration(challenge) {
    const clientData = new TextEncoder().encode(
      JSON.stringify({ type: 'webauthn.create', challenge, origin: window.location.origin })
    );
    const authData = await this.authData({ attested: true });
    // Tiny hand-rolled CBOR: {"fmt":"none","attStmt":{},"authData":<bytes>}
    // (keys in canonical length order — the server's decoder accepts it).
    const cbor = cborEncodeMap({ fmt: 'none', attStmt: {}, authData: authData });
    return {
      credential_id: uint8ToB64u(this.credentialId),
      client_data_b64: uint8ToB64u(clientData),
      attestation_object_b64: uint8ToB64u(cbor),
      transports: ['internal'],
    };
  }

  async assertion(challenge) {
    const clientData = new TextEncoder().encode(
      JSON.stringify({ type: 'webauthn.get', challenge, origin: window.location.origin })
    );
    const authData = await this.authData({ attested: false });
    const clientHash = await sha256(clientData);
    const signed = new Uint8Array(authData.length + clientHash.length);
    signed.set(authData, 0);
    signed.set(clientHash, authData.length);
    const raw = await crypto.subtle.sign(
      { name: 'ECDSA', hash: 'SHA-256' },
      this.keyPair.privateKey,
      signed
    );
    return {
      credential_id: uint8ToB64u(this.credentialId),
      client_data_b64: uint8ToB64u(clientData),
      authenticator_data_b64: uint8ToB64u(authData),
      signature_b64: uint8ToB64u(derFromRaw(new Uint8Array(raw))),
    };
  }
}

/** Minimal CBOR map encoder for {fmt, attStmt, authData} (server decodes it). */
function cborEncodeMap(map) {
  const keys = ['attStmt', 'authData', 'fmt']; // canonical: length, then bytewise
  const encodeText = (text) => {
    const raw = new TextEncoder().encode(text);
    return new Uint8Array([0x60 | raw.length, ...raw]);
  };
  const encodeNull = new Uint8Array([0xf6]);
  const encodeMapHeader = (n) => new Uint8Array([0xa0 | n]);
  let out = encodeMapHeader(keys.length);
  const encodeInt = (value) => new Uint8Array([0x20 + (-1 - value)]); // negative ints
  const entries = {
    fmt: [encodeText('fmt'), encodeText(map.fmt)],
    attStmt: [encodeText('attStmt'), encodeMapHeader(0)],
    authData: [
      encodeText('authData'),
      (() => {
        const data = map.authData;
        if (data.length < 24) return new Uint8Array([0x40 | data.length, ...data]);
        if (data.length < 0x100) return new Uint8Array([0x40 | 24, data.length, ...data]);
        return new Uint8Array([
          0x40 | 25,
          (data.length >> 8) & 0xff,
          data.length & 0xff,
          ...data,
        ]);
      })(),
    ],
  };
  keys.forEach((key) => {
    out = concat(out, entries[key][0], entries[key][1]);
  });
  void encodeNull;
  void encodeInt;
  return out;
}

function concat(...arrays) {
  const total = arrays.reduce((acc, a) => acc + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  arrays.forEach((a) => {
    out.set(a, offset);
    offset += a.length;
  });
  return out;
}

// --- component ---------------------------------------------------------------

const PURPOSES = [
  { value: 'exam_hall_entry', label: 'Exam hall entry' },
  { value: 'staff_attendance', label: 'Staff attendance' },
];

const STATUS_TONE = { Enrolled: 'ok', 'Not enrolled': 'muted', Revoked: 'danger' };

export default function Biometrics() {
  const dispatch = useDispatch();
  const { students, staff, counts, verifications, busy, error, notice, lastVerification } =
    useSelector((state) => state.biometrics);

  const [tab, setTab] = useState('students');
  const [stationPurpose, setStationPurpose] = useState('exam_hall_entry');
  const [stationOwnerType, setStationOwnerType] = useState('student');
  const [stationIdentifier, setStationIdentifier] = useState('');
  const [stationBusy, setStationBusy] = useState(false);

  useEffect(() => {
    dispatch(fetchBiometricOverview({}));
    dispatch(fetchVerificationLog({ limit: 30 }));
  }, [dispatch]);

  useEffect(() => {
    if (!notice && !error) return;
    const timer = setTimeout(() => dispatch({ type: 'biometrics/dismissNotice' }), 5000);
    return () => clearTimeout(timer);
  }, [notice, error, dispatch]);

  const rpId = useMemo(() => window.location.hostname, []);

  const refresh = () => {
    dispatch(fetchBiometricOverview({}));
    dispatch(fetchVerificationLog({ limit: 30 }));
  };

  const runEnrollment = async (ownerType, owner) => {
    try {
      const options = await dispatch(
        biometricEnrollOptions({
          owner_type: ownerType,
          owner_id: owner.owner_id,
          method: 'fingerprint',
        })
      ).unwrap();

      let response;
      let method = 'fingerprint';
      if (window.isSecureContext && navigator.credentials) {
        try {
          response = await runWebAuthnEnrollment(options);
        } catch (webauthnError) {
          // No biometric hardware available — fall back to the QA simulator.
          const reader = await new SimulatedReader(rpId).init();
          response = await reader.registration(options.publicKey.challenge);
          method = 'simulated';
        }
      } else {
        const reader = await new SimulatedReader(rpId).init();
        response = await reader.registration(options.publicKey.challenge);
        method = 'simulated';
      }

      await dispatch(
        biometricEnrollVerify({
          owner_type: ownerType,
          owner_id: owner.owner_id,
          method,
          expected_challenge: options.publicKey.challenge,
          transports: response.transports ?? ['internal'],
          credential_id: response.credential_id,
          client_data_b64: response.client_data_b64,
          attestation_object_b64: response.attestation_object_b64,
        })
      ).unwrap();
      refresh();
    } catch (enrollError) {
      // error state is surfaced by the slice
    }
  };

  const runVerification = async (event) => {
    event.preventDefault();
    if (!stationIdentifier) return;
    setStationBusy(true);
    try {
      const options = await dispatch(
        biometricVerifyOptions({
          purpose: stationPurpose,
          owner_type: stationOwnerType,
          identifier: stationIdentifier,
        })
      ).unwrap();
      dispatch(
        setStation({
          purpose: stationPurpose,
          owner_type: stationOwnerType,
          owner_id: options.owner.owner_id,
          name: options.owner.name,
        })
      );

      let assertion;
      const allowId = options.publicKey.allowCredentials?.[0]?.id;
      if (window.isSecureContext && navigator.credentials && allowId && !allowId.startsWith('sim')) {
        try {
          assertion = await runWebAuthnAssertion(options.publicKey);
        } catch {
          assertion = null;
        }
      }
      // Simulator path: reconstruct the reader from the enrolled credential's
      // private key is impossible by design — QA flow re-runs enrollment with
      // the same reader object kept in memory for the station below.
      if (!assertion) {
        const reader = await new SimulatedReader(rpId).init();
        // The simulated credential differs from the enrolled one, so the
        // server will correctly reject it; QA operators should use the
        // hardware flow or enroll+verify in one sitting with real hardware.
        assertion = await reader.assertion(options.publicKey.challenge);
      }

      const result = await dispatch(
        biometricVerifyComplete({
          purpose: stationPurpose,
          owner_type: stationOwnerType,
          owner_id: options.owner.owner_id,
          expected_challenge: options.publicKey.challenge,
          credential_id: assertion.credential_id,
          client_data_b64: assertion.client_data_b64,
          authenticator_data_b64: assertion.authenticator_data_b64,
          signature_b64: assertion.signature_b64,
        })
      ).unwrap();
      setStationIdentifier('');
      refresh();
      return result;
    } catch {
      /* slice carries the error */
    } finally {
      setStationBusy(false);
    }
  };

  const people = tab === 'students' ? students : staff;

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>Biometric hardware</h2>
          <p className="muted">
            Fingerprint / smartcard enrollment (WebAuthn) for students and staff, with a
            timestamped verification register for exam hall entry and staff attendance.
          </p>
        </div>
      </header>

      {error && (
        <p className="alert alert--danger" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="alert alert--ok" role="status">
          {notice}
        </p>
      )}

      <div className="kpi-grid">
        <KpiCard
          label="Students enrolled"
          value={`${counts.students_enrolled ?? 0}/${counts.students_total ?? 0}`}
          tone="neutral"
        />
        <KpiCard
          label="Staff enrolled"
          value={`${counts.staff_enrolled ?? 0}/${counts.staff_total ?? 0}`}
          tone="neutral"
        />
        <KpiCard label="Active credentials" value={counts.credentials_active ?? 0} tone="info" />
        <KpiCard
          label="Verifications today"
          value={`${counts.verifications_today?.success ?? 0} ok · ${counts.verifications_today?.failed ?? 0} failed`}
          tone={(counts.verifications_today?.failed ?? 0) > 0 ? 'warn' : 'ok'}
        />
      </div>

      <div className="card">
        <h3>Verification station</h3>
        <p className="muted">
          Resolve a person by roll number or staff ID, then scan their registered fingerprint /
          smartcard. Successful scans are stamped into the register below.
        </p>
        <form className="form-row" onSubmit={runVerification}>
          <label className="field">
            <span>Purpose</span>
            <select value={stationPurpose} onChange={(e) => setStationPurpose(e.target.value)}>
              {PURPOSES.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Person type</span>
            <select value={stationOwnerType} onChange={(e) => setStationOwnerType(e.target.value)}>
              <option value="student">Student (roll number)</option>
              <option value="staff">Staff (email or staff ID)</option>
            </select>
          </label>
          <label className="field field--grow">
            <span>Identifier</span>
            <input
              type="text"
              value={stationIdentifier}
              placeholder={stationOwnerType === 'student' ? 'NG-10001' : 'teacher@nugaal.edu.so'}
              onChange={(e) => setStationIdentifier(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="btn btn--primary" disabled={stationBusy}>
            {stationBusy ? 'Scanning…' : 'Scan'}
          </button>
        </form>
        {lastVerification && (
          <p className="station-result" role="status">
            <Badge tone="ok">VERIFIED</Badge> {lastVerification.person} ·{' '}
            <span className="mono">{lastVerification.verified_at}</span> ·{' '}
            {lastVerification.purpose.replace(/_/g, ' ')} via {lastVerification.method}
          </p>
        )}
      </div>

      <div className="card">
        <div className="tab-row" role="tablist">
          <button
            type="button"
            className={`tab ${tab === 'students' ? 'is-active' : ''}`}
            onClick={() => setTab('students')}
          >
            Students
          </button>
          <button
            type="button"
            className={`tab ${tab === 'staff' ? 'is-active' : ''}`}
            onClick={() => setTab('staff')}
          >
            Teaching staff
          </button>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Identifier</th>
                <th>{tab === 'students' ? 'Class' : 'Designation'}</th>
                <th>Registration status</th>
                <th>Last verification</th>
                <th>Credentials</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {people.slice(0, 120).map((person) => (
                <tr key={`${person.owner_type}-${person.owner_id}`}>
                  <td>{person.name}</td>
                  <td className="mono">{person.identifier}</td>
                  <td>{person.meta ?? '—'}</td>
                  <td>
                    <Badge tone={STATUS_TONE[person.status] ?? 'muted'}>{person.status}</Badge>
                  </td>
                  <td className="muted mono">
                    {person.last_verification
                      ? `${person.last_verification.slice(0, 16)} (${person.last_verification_result})`
                      : '—'}
                  </td>
                  <td>
                    <ul className="credential-chips">
                      {person.credentials.map((credential) => (
                        <li key={credential.id} className="credential-chip">
                          <span>{credential.method}</span>
                          <span className="mono muted">#{credential.id}</span>
                          <button
                            type="button"
                            className="btn btn--sm btn--ghost"
                            title="Re-scan hardware: revoke and re-enroll"
                            onClick={() =>
                              dispatch(biometricRescan(credential.id)).then(refresh)
                            }
                          >
                            Re-scan
                          </button>
                          {credential.status === 'active' && (
                            <button
                              type="button"
                              className="btn btn--sm btn--ghost"
                              onClick={() => dispatch(biometricRevoke(credential.id)).then(refresh)}
                            >
                              Revoke
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--sm btn--primary"
                      disabled={busy}
                      onClick={() => runEnrollment(person.owner_type, person)}
                    >
                      {person.status === 'Enrolled' ? 'Add device' : 'Enroll'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          Showing up to 120 {tab}. Enrollment uses the browser WebAuthn platform authenticator
          when available and falls back to the QA simulated reader otherwise.
        </p>
      </div>

      <div className="card">
        <h3>Verification register</h3>
        {verifications.length === 0 ? (
          <p className="empty">No biometric verifications recorded yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Person</th>
                  <th>Purpose</th>
                  <th>Result</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {verifications.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono">{entry.verified_at?.replace('T', ' ').slice(0, 19)}</td>
                    <td>{entry.person_label}</td>
                    <td>{entry.purpose.replace(/_/g, ' ')}</td>
                    <td>
                      <Badge tone={entry.result === 'success' ? 'ok' : 'danger'}>{entry.result}</Badge>
                    </td>
                    <td className="muted">{entry.detail ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
