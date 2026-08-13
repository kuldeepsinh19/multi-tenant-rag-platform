import { useRef, useState, type FormEvent } from "react";

import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./DocumentUploadForm.module.css";

interface Props {
  onUpload: (file: File) => void;
  isPending: boolean;
  errorMessage: string | undefined;
}

export function DocumentUploadForm({ onUpload, isPending, errorMessage }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    onUpload(file);
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className={styles.inline}>
        <div className={cx(ui.field, styles.grow)}>
          <label className={ui.label} htmlFor="document-upload-input">
            Upload document
          </label>
          <input
            id="document-upload-input"
            className={ui.fileInput}
            ref={inputRef}
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        <button
          type="submit"
          className={cx(ui.btn, ui.btnPrimary, styles.action)}
          disabled={isPending || !file}
        >
          {isPending ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              Uploading…
            </>
          ) : (
            "Upload"
          )}
        </button>
      </div>
      {errorMessage ? <StatusMessage tone="error">{errorMessage}</StatusMessage> : null}
    </form>
  );
}
