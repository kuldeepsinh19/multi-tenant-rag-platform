import { useState, type FormEvent } from "react";

import { StatusMessage } from "@/components/ui/StatusMessage";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./InviteAdminForm.module.css";

interface Props {
  onInvite: (email: string, password: string) => void;
  isPending: boolean;
  errorMessage: string | undefined;
  successMessage: string | undefined;
}

export function InviteAdminForm({ onInvite, isPending, errorMessage, successMessage }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email.trim() || !password) return;
    onInvite(email.trim(), password);
    setEmail("");
    setPassword("");
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 className={styles.heading}>Invite business admin</h3>
      <div className={styles.grid}>
        <div className={ui.field}>
          <label className={ui.label} htmlFor="invite-admin-email">
            Email
          </label>
          <input
            id="invite-admin-email"
            className={ui.input}
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@example.com"
            required
          />
        </div>
        <div className={ui.field}>
          <label className={ui.label} htmlFor="invite-admin-password">
            Temporary password
          </label>
          <input
            id="invite-admin-password"
            className={ui.input}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
      </div>
      <button
        type="submit"
        className={cx(ui.btn, ui.btnPrimary, styles.action)}
        disabled={isPending || !email.trim() || !password}
      >
        {isPending ? "Inviting…" : "Invite admin"}
      </button>
      {errorMessage ? <StatusMessage tone="error">{errorMessage}</StatusMessage> : null}
      {successMessage ? <StatusMessage tone="success">{successMessage}</StatusMessage> : null}
    </form>
  );
}
