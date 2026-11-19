import React from 'react';

/**
 * Error dialog component for showing error messages
 *
 * @param {Object} props
 * @param {string} props.error - Error message to display
 * @param {Function} props.onClose - Callback when dialog is closed
 */
export function ErrorDialog({ error, onClose }) {
  if (!error) return null;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog error-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Error</h2>
          <button className="dialog-close" onClick={onClose}>×</button>
        </div>

        <div className="dialog-content">
          <div className="error-message">
            <div className="error-icon">⚠️</div>
            <div className="error-text">{error}</div>
          </div>
        </div>

        <div className="dialog-footer">
          <button className="dialog-button dialog-button-primary" onClick={onClose}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
