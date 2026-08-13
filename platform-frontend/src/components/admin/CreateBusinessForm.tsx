import { useState, type FormEvent } from "react";

import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./CreateBusinessForm.module.css";

interface Props {
  onCreate: (name: string) => void;
  isPending: boolean;
  errorMessage: string | undefined;
}

export function CreateBusinessForm({ onCreate, isPending, errorMessage }: Props) {
  const [name, setName] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed);
    setName("");
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className={styles.inline}>
        <div className={cx(ui.field, styles.grow)}>
          <label className={ui.label} htmlFor="new-business-name">
            New business name
          </label>
          <input
            id="new-business-name"
            className={ui.input}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Acme Corp"
            required
          />
        </div>
        <button
          type="submit"
          className={cx(ui.btn, ui.btnPrimary, styles.action)}
          disabled={isPending || !name.trim()}
        >
          {isPending ? "Creating…" : "Create business"}
        </button>
      </div>
      {errorMessage ? <StatusMessage tone="error">{errorMessage}</StatusMessage> : null}
    </form>
  );
}
