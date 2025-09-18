// src/GeneratedKeyModal.js
import React, { useState } from 'react';
import '../App.css'; // create styles here if needed

const GeneratedKeyModal = ({ isOpen, onClose, apiKey }) => {
  const [copyButtonText, setCopyButtonText] = useState('Copy to Clipboard');

  // If the modal is not open, render nothing.
  if (!isOpen) {
    return null;
  }

  // This function handles the copy logic.
  const handleCopy = () => {
    // Use the modern navigator.clipboard API
    navigator.clipboard.writeText(apiKey).then(() => {
      // On successful copy, update the button text
      setCopyButtonText('Copied!');
      // Reset the button text after 2 seconds
      setTimeout(() => {
        setCopyButtonText('Copy to Clipboard');
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      // You could add a fallback method here for older browsers if needed
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>Here is your new API Key</h2>
        <p className="warning">
          This key will only be shown once. Copy and store it somewhere safe.
        </p>
        <div className="api-key-display">{apiKey}</div>
        <div className="modal-buttons">
          <button
            className={`copy-btn ${copyButtonText === 'Copied!' ? 'copied' : ''}`}
            onClick={handleCopy}
          >
            {copyButtonText}
          </button>
          <button className="close-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default GeneratedKeyModal;
