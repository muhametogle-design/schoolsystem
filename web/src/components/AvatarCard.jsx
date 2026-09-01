import { useEffect, useRef, useState } from 'react';

/**
 * Refinement 5 — Role-gated profile photo/avatar card.
 *
 * School Managers see an active media upload button (📷) over the avatar plus
 * an "Upload New Media" CTA driving a hidden <input type="file"
 * accept="image/*">. Selections are downscaled in-browser, previewed
 * instantly, then synced to the profile's media state on the server.
 *
 * Every other role (Teachers, read-only viewers) receives the exact same
 * card with a READ-ONLY badge and no way to reach the file input.
 */

const MAX_EDGE = 400; // px — the backend accepts up to 512 KiB decoded
const MAX_FILE_BYTES = 8 * 1024 * 1024; // raw camera shots are fine pre-scale

/** Read + downscale an image File into a compact data URL. */
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('Please choose an image file (png, jpeg, webp or gif).'));
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      reject(new Error('That image is larger than 8 MB — please crop or compress it first.'));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read the selected file.'));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('The selected file is not a readable image.'));
      img.onload = () => {
        const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
        const width = Math.max(1, Math.round(img.width * scale));
        const height = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        // Keep PNGs lossless-looking; everything else becomes a compact JPEG.
        const mime = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
        resolve(canvas.toDataURL(mime, 0.85));
      };
      img.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}

function initialsOf(name = '') {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('') || '?'
  );
}

export default function AvatarCard({
  name,
  subtitle,
  photoData,
  canEdit = false,
  busy = false,
  notice,
  error,
  onUpload,
  onRemove,
}) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [localError, setLocalError] = useState(null);

  // The server copy always wins once it arrives — preview only bridges the
  // gap between file selection and the confirmed media state.
  useEffect(() => {
    setPreview(null);
  }, [photoData]);

  const shown = preview ?? photoData ?? null;

  const pickFile = () => inputRef.current?.click();

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-selecting the same file
    if (!file) return;
    setLocalError(null);
    try {
      const dataUrl = await fileToDataUrl(file);
      setPreview(dataUrl); // instant preview…
      onUpload?.(dataUrl); // …then update the profile media state
    } catch (err) {
      setLocalError(err.message);
    }
  };

  const shownError = localError ?? error;

  return (
    <figure className="avatar-card" aria-label={`Profile photo for ${name}`}>
      <div className={`avatar-card__frame ${shown ? 'has-photo' : ''}`}>
        {shown ? (
          <img className="avatar-card__img" src={shown} alt={`Profile photo of ${name}`} />
        ) : (
          <span className="avatar-card__initials" aria-hidden="true">
            {initialsOf(name)}
          </span>
        )}
        {canEdit ? (
          <button
            type="button"
            className="avatar-card__edit"
            onClick={pickFile}
            disabled={busy}
            title="Upload a new profile photo"
            aria-label={`Upload a new profile photo for ${name}`}
          >
            📷
          </button>
        ) : (
          <span className="avatar-card__lock" title="Only school managers can change profile photos">
            READ-ONLY
          </span>
        )}
      </div>

      <figcaption className="avatar-card__meta">
        <strong className="avatar-card__name">{name}</strong>
        {subtitle && <span className="avatar-card__sub">{subtitle}</span>}

        {canEdit ? (
          <>
            {/* Hidden file input — the entire picker flow lives behind it. */}
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="avatar-card__input"
              aria-hidden="true"
              tabIndex={-1}
              onChange={handleFile}
            />
            <span className="avatar-card__actions">
              <button type="button" className="btn btn--sm btn--primary" onClick={pickFile} disabled={busy}>
                {busy ? 'Uploading…' : shown ? '⤒ Upload New Media' : '⤒ Upload New Media'}
              </button>
              {photoData && onRemove && (
                <button type="button" className="btn btn--sm btn--danger" onClick={onRemove} disabled={busy}>
                  Remove
                </button>
              )}
            </span>
            <span className="avatar-card__hint">PNG/JPEG/WebP up to 8 MB — auto-resized, visible school-wide.</span>
          </>
        ) : (
          <span className="avatar-card__hint">
            <span className="avatar-card__read-only-badge">🔒 Managed by school admin</span>
          </span>
        )}

        {notice && <span className="alert alert--ok avatar-card__alert" role="status">{notice}</span>}
        {shownError && <span className="alert alert--danger avatar-card__alert" role="alert">{shownError}</span>}
      </figcaption>
    </figure>
  );
}
