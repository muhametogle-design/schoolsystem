import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import { fetchBackups, fetchBackupAudit, runBackup, verifyBackup } from '../features/backups/backupsSlice';

const TOKEN_KEY_BACKUP = 'ne_emis_token';

function authHeaders() {
  try {
    const token = window.localStorage.getItem(TOKEN_KEY_BACKUP);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Module 4 — automated encrypted midnight backups (State Admin console).
 *
 * Shows the schedule (00:00 platform timezone), AES-256-GCM encryption and key
 * provenance, the SHA-256/MD5 digests of every artefact, one-click integrity
 * verification, manual on-demand exports, and the admin audit trail with
 * download options (encrypted container or decrypted delta inspection).
 */
export default function Backups() {
  const dispatch = useDispatch();
  const { backups, total, lastBackup, config, audit, busy, error, notice, status } = useSelector(
    (state) => state.backups
  );
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    dispatch(fetchBackups());
    dispatch(fetchBackupAudit());
  }, [dispatch]);

  useEffect(() => {
    if (!notice && !error) return;
    const timer = setTimeout(() => dispatch({ type: 'backups/dismissNotice' }), 5000);
    return () => clearTimeout(timer);
  }, [notice, error, dispatch]);

  const refresh = () => {
    dispatch(fetchBackups());
    dispatch(fetchBackupAudit());
  };

  const download = async (backup, format) => {
    setDownloading(`${backup.id}-${format}`);
    try {
      const res = await fetch(
        `/api/v1/admin/backups/${backup.id}/download?format=${format}`,
        { credentials: 'include', headers: authHeaders() }
      );
      if (!res.ok) throw new Error(`Download failed (HTTP ${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      const extension = format === 'decrypted' && backup.kind === 'json_delta' ? 'json' : backup.kind === 'json_delta' ? 'bin' : 'nesbak';
      anchor.href = url;
      anchor.download = backup.filename.replace('.nesbak', format === 'encrypted' ? '.nesbak' : `.${extension}`);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      refresh();
    } catch (downloadError) {
      dispatch({ type: 'backups/dismissNotice' });
    } finally {
      setDownloading(null);
    }
  };

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>Encrypted backups</h2>
          <p className="muted">
            Daily midnight export (SQLite snapshot + JSON delta of trigger-captured changes),
            sealed with AES-256-GCM and fingerprinted with SHA-256 / MD5 digests.
          </p>
        </div>
        <div className="btn-row">
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy}
            onClick={() => dispatch(runBackup({ kind: 'full_snapshot' })).then(refresh)}
          >
            Run full snapshot now
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={busy}
            onClick={() => dispatch(runBackup({ kind: 'json_delta' })).then(refresh)}
          >
            Run JSON delta now
          </button>
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
        <KpiCard label="Artefacts retained" value={total} tone="neutral" />
        <KpiCard
          label="Last backup"
          value={lastBackup?.created_at ? lastBackup.created_at.replace('T', ' ').slice(0, 16) : '—'}
          hint={lastBackup ? `${lastBackup.kind} · ${formatBytes(lastBackup.size_bytes)}` : 'No backup yet'}
          tone={lastBackup?.status === 'completed' ? 'ok' : lastBackup ? 'danger' : 'warn'}
        />
        <KpiCard
          label="Schedule"
          value={config ? `${config.schedule} ${config.timezone.split('/').pop()}` : '—'}
          hint={config ? `retention ${config.retention_days} days` : undefined}
          tone="info"
        />
        <KpiCard
          label="Encryption"
          value="AES-256-GCM"
          hint={config?.key_source}
          tone="neutral"
        />
      </div>

      {config && (
        <div className="card">
          <h3>Pipeline configuration</h3>
          <dl className="config-grid">
            <div>
              <dt>Midnight export</dt>
              <dd className="mono">
                {config.schedule} ({config.timezone}) — scheduler {config.scheduler_enabled ? 'armed' : 'disabled'}
              </dd>
            </div>
            <div>
              <dt>Encryption</dt>
              <dd className="mono">{config.encryption}</dd>
            </div>
            <div>
              <dt>Key source</dt>
              <dd className="mono">{config.key_source}</dd>
            </div>
            <div>
              <dt>Key fingerprint</dt>
              <dd className="mono">{config.key_fingerprint}</dd>
            </div>
            <div>
              <dt>Integrity hashes</dt>
              <dd className="mono">{config.hashes.join(' · ')}</dd>
            </div>
            <div>
              <dt>Change-capture buffer</dt>
              <dd className="mono">{config.pending_change_rows} rows awaiting next delta</dd>
            </div>
            <div>
              <dt>Storage directory</dt>
              <dd className="mono">{config.backup_dir}</dd>
            </div>
          </dl>
        </div>
      )}

      <div className="card">
        <h3>Backup artefacts</h3>
        {status === 'loading' && backups.length === 0 ? (
          <p className="empty">Loading…</p>
        ) : backups.length === 0 ? (
          <p className="empty">
            No artefacts yet — the midnight job or the buttons above create the first one.
          </p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Kind</th>
                  <th>Size</th>
                  <th>SHA-256</th>
                  <th>MD5</th>
                  <th>Trigger</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((backup) => (
                  <tr key={backup.id}>
                    <td className="mono">{backup.created_at?.replace('T', ' ').slice(0, 19)}</td>
                    <td>
                      <Badge tone={backup.kind === 'full_snapshot' ? 'info' : 'muted'}>
                        {backup.kind === 'full_snapshot' ? 'SNAPSHOT' : 'DELTA'}
                      </Badge>
                    </td>
                    <td className="mono">{formatBytes(backup.size_bytes)}</td>
                    <td className="mono hash" title={backup.sha256}>
                      {backup.sha256?.slice(0, 12)}…
                    </td>
                    <td className="mono hash" title={backup.md5}>
                      {backup.md5?.slice(0, 8)}…
                    </td>
                    <td>{backup.triggered_by}</td>
                    <td>
                      <Badge tone={backup.status === 'completed' ? 'ok' : 'danger'}>
                        {backup.status}
                      </Badge>
                    </td>
                    <td className="actions-cell">
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => dispatch(verifyBackup(backup.id)).then(refresh)}
                      >
                        Verify
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        disabled={downloading === `${backup.id}-encrypted`}
                        onClick={() => download(backup, 'encrypted')}
                      >
                        .nesbak
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        disabled={downloading === `${backup.id}-decrypted`}
                        title="Decrypt server-side (audited) and download the payload"
                        onClick={() => download(backup, 'decrypted')}
                      >
                        Decrypt
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Admin audit log</h3>
        {audit.length === 0 ? (
          <p className="empty">No backup events recorded yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Backup</th>
                  <th>Actor</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {audit.slice(0, 40).map((event) => (
                  <tr key={event.id}>
                    <td className="mono">{event.created_at?.replace('T', ' ').slice(0, 19)}</td>
                    <td>
                      <Badge
                        tone={
                          event.action === 'verified'
                            ? 'ok'
                            : event.action === 'verify_failed' || event.action === 'failed'
                              ? 'danger'
                              : 'info'
                        }
                      >
                        {event.action}
                      </Badge>
                    </td>
                    <td className="mono">#{event.backup_id ?? '—'}</td>
                    <td className="mono">{event.actor_id ? `user ${event.actor_id}` : 'system'}</td>
                    <td className="muted">{event.detail}</td>
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
