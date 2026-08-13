import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

// @testing-library/react's auto-cleanup only self-registers when a test
// framework global (afterEach) is detected automatically; with `globals:
// false` we register it explicitly so each test starts from an empty DOM.
afterEach(() => {
  cleanup();
});
