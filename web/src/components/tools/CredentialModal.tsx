import React, { useState } from "react";

interface CredentialModalProps {
  toolName: string;
  open: boolean;
  onClose: () => void;
  onSave: (apiKey: string) => void;
}

export default function CredentialModal({ toolName, open, onClose, onSave }: CredentialModalProps) {
  const [apiKey, setApiKey] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // FE-M4: Reject empty or whitespace-only API keys client-side
    const trimmed = apiKey.trim();
    if (!trimmed) {
      setValidationError("API key cannot be empty.");
      return;
    }
    setValidationError(null);
    onSave(trimmed);
    setApiKey("");
  };

  const handleClose = () => {
    setValidationError(null);
    setApiKey("");
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      data-credential-modal
    >
      <div
        role="dialog"
        aria-label={`Configure credentials for ${toolName}`}
        className="bg-background rounded-lg border p-6 w-full max-w-md shadow-lg"
      >
        <h2 className="text-lg font-semibold mb-4">Configure {toolName}</h2>
        <form onSubmit={handleSubmit}>
          <label className="block text-sm mb-2">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                if (validationError) setValidationError(null);
              }}
              className="mt-1 block w-full rounded border px-3 py-2 text-sm"
              placeholder="Enter API key"
              aria-describedby={validationError ? "credential-validation-error" : undefined}
            />
          </label>
          {validationError && (
            <p
              id="credential-validation-error"
              className="text-sm text-destructive mt-1"
              role="alert"
            >
              {validationError}
            </p>
          )}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm rounded border hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
