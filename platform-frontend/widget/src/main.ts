import { mountWidget } from "./widget";

/**
 * Entry point for the embeddable widget bundle. Reads `data-public-key` and
 * `data-api-base` off this script's own <script> tag, exactly as a customer
 * would embed it:
 *   <script src=".../widget.js" data-public-key="pk_xxx" data-api-base="https://api.example.com"></script>
 *
 * `document.currentScript` must be read synchronously at module top-level —
 * it becomes null once execution yields (e.g. after an await), so config
 * extraction happens before anything else runs.
 */
function readConfig(): { apiBase: string; publicKey: string } | null {
  const script = document.currentScript as HTMLScriptElement | null;
  if (!script) return null;

  const publicKey = script.dataset.publicKey;
  const apiBase = script.dataset.apiBase;
  if (!publicKey || !apiBase) return null;

  return { publicKey, apiBase };
}

const config = readConfig();
if (config) {
  mountWidget(config);
} else {
  console.error(
    "platform-widget: missing data-public-key or data-api-base on the embedding <script> tag.",
  );
}
