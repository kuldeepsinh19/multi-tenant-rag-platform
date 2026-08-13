import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { ThemeToggle } from "@/components/ThemeToggle";
import { StatusMessage } from "@/components/ui/StatusMessage";
import { useLogin } from "@/hooks/useLogin";
import { cx } from "@/lib/cx";
import { Navigate } from "@/router/router";
import { useAuthStore } from "@/store/auth";
import ui from "@/styles/primitives.module.css";

import styles from "./LoginPage.module.css";

/** Thin container: owns form state, delegates the network call to useLogin,
 * redirects to the caller's home route once authenticated. */
export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const role = useAuthStore((state) => state.role);
  const loginMutation = useLogin();

  if (role === "super_admin") return <Navigate to="/admin" />;
  if (role === "business_admin") return <Navigate to="/dashboard" />;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loginMutation.mutate({ email, password });
  };

  const errorMessage =
    loginMutation.isError && loginMutation.error instanceof ApiError
      ? loginMutation.error.message
      : loginMutation.isError
        ? "Something went wrong. Please try again."
        : null;

  return (
    <div className={styles.viewport}>
      <div className={styles.themeSlot}>
        <ThemeToggle />
      </div>

      <main className={cx(ui.card, styles.card)}>
        <span className={styles.mark} aria-hidden="true" />
        <h1 className={styles.title}>Sign in</h1>
        <p className={styles.subtitle}>Access your platform console.</p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={ui.field}>
            <label className={ui.label} htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              className={ui.input}
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className={ui.field}>
            <label className={ui.label} htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              className={ui.input}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {errorMessage ? <StatusMessage tone="error">{errorMessage}</StatusMessage> : null}
          <button
            type="submit"
            className={cx(ui.btn, ui.btnPrimary, ui.btnBlock, styles.submit)}
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? (
              <>
                <span className={styles.spinner} aria-hidden="true" />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
      </main>
    </div>
  );
}
