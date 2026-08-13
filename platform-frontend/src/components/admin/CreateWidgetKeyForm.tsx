import { useState, type FormEvent } from "react";

import type { WidgetKey } from "@/api/businesses";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./CreateWidgetKeyForm.module.css";

interface Props {
  onCreate: (allowedDomains: string[]) => void;
  isPending: boolean;
  errorMessage: string | undefined;
  createdKey: WidgetKey | undefined;
}

export function CreateWidgetKeyForm({ onCreate, isPending, errorMessage, createdKey }: Props) {
  const [domains, setDomains] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const list = domains
      .split(",")
      .map((domain) => domain.trim())
      .filter(Boolean);
    if (list.length === 0) return;
    onCreate(list);
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 className={styles.heading}>Create widget key</h3>
      <div className={ui.field}>
        <label className={ui.label} htmlFor="widget-key-domains">
          Allowed domains (comma-separated)
        </label>
        <input
          id="widget-key-domains"
          className={ui.input}
          value={domains}
          onChange={(event) => setDomains(event.target.value)}
          placeholder="example.com, www.example.com"
          required
        />
      </div>
      <button
        type="submit"
        className={cx(ui.btn, ui.btnPrimary, styles.action)}
        disabled={isPending || !domains.trim()}
      >
        {isPending ? "Creating…" : "Create widget key"}
      </button>
      {errorMessage ? <StatusMessage tone="error">{errorMessage}</StatusMessage> : null}
      {createdKey ? (
        <StatusMessage tone="success">
          Public key: <code className={styles.key}>{createdKey.public_key}</code>
        </StatusMessage>
      ) : null}
    </form>
  );
}
