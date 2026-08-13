import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";

/**
 * Minimal History-API-based router. react-router-dom@7.18.2 (latest stable)
 * was evaluated and rejected: installing it introduced a NEW high-severity
 * advisory (GHSA-qwww-vcr4-c8h2, react-router CSRF bypass, affecting the
 * 7.12.0-8.2.0 range) not present in this repo's pre-existing audit baseline,
 * and `npm audit fix` could only "fix" it by downgrading below the vulnerable
 * range's floor (7.11.0) or a `--force` major bump — neither acceptable for a
 * 3-route app. See report for full before/after audit numbers. This router
 * covers exactly what this app needs: path-based navigation via
 * pushState/popstate, a <Link>, and a declarative <Navigate> redirect.
 */

type Listener = () => void;

function subscribe(listener: Listener): () => void {
  window.addEventListener("popstate", listener);
  return () => window.removeEventListener("popstate", listener);
}

function getSnapshot(): string {
  return window.location.pathname;
}

function navigate(to: string): void {
  if (window.location.pathname !== to) {
    window.history.pushState(null, "", to);
  }
  // pushState doesn't fire popstate — notify listeners manually.
  window.dispatchEvent(new PopStateEvent("popstate"));
}

interface RouterContextValue {
  pathname: string;
  navigate: (to: string) => void;
}

const RouterContext = createContext<RouterContextValue | null>(null);

export function RouterProvider({ children }: { children: ReactNode }) {
  const pathname = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const value = useMemo(() => ({ pathname, navigate }), [pathname]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

function useRouterContext(): RouterContextValue {
  const ctx = useContext(RouterContext);
  if (!ctx) throw new Error("useRouterContext must be used within a RouterProvider");
  return ctx;
}

export function useLocation(): { pathname: string } {
  const { pathname } = useRouterContext();
  return { pathname };
}

export function useNavigate(): (to: string) => void {
  const { navigate: nav } = useRouterContext();
  return useCallback((to: string) => nav(to), [nav]);
}

/** Renders `children` only when the current pathname matches exactly. */
export function Route({ path, children }: { path: string; children: ReactNode }) {
  const { pathname } = useLocation();
  return pathname === path ? <>{children}</> : null;
}

/** Declarative redirect — navigates on mount/when `to` changes. */
export function Navigate({ to }: { to: string }) {
  const nav = useNavigate();
  useEffect(() => {
    nav(to);
  }, [nav, to]);
  return null;
}

export function Link({
  to,
  children,
  ...rest
}: { to: string; children: ReactNode } & Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "onClick"
>) {
  const nav = useNavigate();
  return (
    <a
      href={to}
      {...rest}
      onClick={(event) => {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
        event.preventDefault();
        nav(to);
      }}
    >
      {children}
    </a>
  );
}
