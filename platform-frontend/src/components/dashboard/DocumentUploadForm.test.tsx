/**
 * Upload is the entry point to the whole RAG pipeline. The behaviours worth
 * pinning are the guards (no file selected must not fire a request) and the
 * post-submit reset — without clearing the native input, re-selecting the same
 * filename fires no change event and the user cannot retry a failed upload.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentUploadForm } from "@/components/dashboard/DocumentUploadForm";

function renderForm(overrides: Partial<Parameters<typeof DocumentUploadForm>[0]> = {}) {
  const onUpload = vi.fn();
  const { container } = render(
    <DocumentUploadForm
      onUpload={onUpload}
      isPending={false}
      errorMessage={undefined}
      {...overrides}
    />,
  );
  return { onUpload, container };
}

function fileInput(): HTMLInputElement {
  return screen.getByLabelText(/upload document/i) as HTMLInputElement;
}

function select(file: File): void {
  fireEvent.change(fileInput(), { target: { files: [file] } });
}

const handbook = () => new File(["policy text"], "handbook.txt", { type: "text/plain" });

describe("DocumentUploadForm", () => {
  it("labels the file input for assistive tech", () => {
    renderForm();

    expect(fileInput()).toHaveAttribute("id", "document-upload-input");
    expect(fileInput().type).toBe("file");
  });

  it("disables Upload until a file is chosen", () => {
    renderForm();

    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  it("enables Upload once a file is chosen", () => {
    renderForm();

    select(handbook());

    expect(screen.getByRole("button", { name: /upload/i })).toBeEnabled();
  });

  it("passes the selected File through to onUpload", () => {
    const { onUpload } = renderForm();
    const file = handbook();

    select(file);
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("does not submit when no file is selected", () => {
    const { onUpload, container } = renderForm();

    // Submit the form directly — the disabled button cannot be clicked.
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onUpload).not.toHaveBeenCalled();
  });

  it("clears the native input after submitting so the same file can be retried", () => {
    renderForm();

    select(handbook());
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    expect(fileInput().value).toBe("");
  });

  it("shows progress and blocks re-submission while the upload is in flight", () => {
    renderForm({ isPending: true });

    const button = screen.getByRole("button", { name: /uploading/i });
    expect(button).toBeDisabled();
  });

  it("surfaces an upload error as an alert", () => {
    renderForm({ errorMessage: "That file type isn't supported." });

    expect(screen.getByRole("alert")).toHaveTextContent("That file type isn't supported.");
  });

  it("renders no alert when there is no error", () => {
    renderForm();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  // KNOWN GAP: there is no client-side type or size validation — no `accept`
  // attribute, no extension check, no size cap. The backend is the only gate
  // (.txt/.md/.pdf/.docx, 25 MB — src/documents/router.py), so an unsupported
  // file makes a full round trip before being rejected. Recorded, not fixed.
  it("currently accepts any file type client-side, deferring validation to the backend", () => {
    const { onUpload } = renderForm();
    const executable = new File(["MZ"], "payload.exe", { type: "application/x-msdownload" });

    expect(fileInput()).not.toHaveAttribute("accept");

    select(executable);
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    expect(onUpload).toHaveBeenCalledWith(executable);
  });
});
