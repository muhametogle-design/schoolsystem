import { useRef, useState } from 'react';

/**
 * Role-gated profile photo/avatar card.
 *
 * School Managers/Admins get the 📷 media upload button and 'Upload New
 * Media' CTA; every other role sees a read-only badge. Files are validated
 * as images, downscaled client-side (max 512px) and previewed instantly.
 */

const MAX_EDGE = 512;

function initialsOf(name) {
  return (name ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('') || '•';
}

async function fileToDataUrl(file) {
  const raw = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not read the selected file'));
    reader.readAsDataURL(file);
  });
  // Downscale through a canvas so the stored payload stays lightweight.
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('The selected file is not a valid image'));
    img.src = raw;
  });
  const scale = Math.min(1, MAX_EDGE / Math.max(image.width, image.height));
  if (scale >= 1 && raw.length < 400_000) return raw;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(image.width * scale);
  canvas.height = Math.round(image.height * scale);
  canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.85);
}

export default function AvatarCard({ name, photoUrl, canEdit, onUpload, size = 96, subtitle }) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const shown = preview ?? photoUrl;

  const pickFile = () => inputRef.current?.click();

  const onFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Only image files are accepted');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const dataUrl = await fileToDataUrl(file);
      setPreview(dataUrl); // instant preview before the API confirms
      await onUpload?.(dataUrl);
    } catch (err) {
      setPreview(null);
      setError(err.message ?? 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const removePhoto = async () => {
    setError(null);
    setBusy(true);
    try {
      setPreview(null);
      await onUpload?.(null);
    } catch (err) {
      setError(err.message ?? 'Could not remove the photo');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="avatar-card">
      <div className="avatar" style={{ width: size, height: size }}>
        {shown ? (
          <img className="avatar__img" src={shown} alt={name ? `${name} profile photo` : 'Profile photo'} />
        ) : (
          <span className="avatar__initials" aria-hidden="true">{initialsOf(name)}</span>
        )}
        {canEdit && (
          <button
            type="button"
            className="avatar__camera"
            title="Upload new media"
            aria-label="Upload new profile photo"
            onClick={pickFile}
            disabled={busy}
          >
            📷
          </button>
        )}
      </div>

      <div className="avatar-card__meta">
        {subtitle && <span className="avatar-card__subtitle">{subtitle}</span>}
        {canEdit ? (
          <div className="avatar-card__actions">
            <button type="button" className="btn btn--small btn--primary" onClick={pickFile} disabled={busy}>
              {busy ? 'Uploading…' : 'Upload New Media'}
            </button>
            {shown && (
              <button type="button" className="btn btn--small btn--ghost" onClick={removePhoto} disabled={busy}>
                Remove
              </button>
            )}
          </div>
        ) : (
          <span className="avatar-card__lock" title="Only School Managers can change profile media">
            🔒 Photo managed by school administration
          </span>
        )}
        {error && <span className="avatar-card__error">{error}</span>}
      </div>

      {/* Hidden file input — media selection is manager-gated above. */}
      {canEdit && (
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="avatar-card__input"
          onChange={onFile}
          hidden
        />
      )}
    </div>
  );
}
