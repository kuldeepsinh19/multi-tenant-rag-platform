/**
 * The document list is the business admin's only window into asynchronous
 * ingestion, so every one of the four backend statuses must be distinguishable,
 * and a failed document must surface its reason. The four render states
 * (loading / error / empty / populated) are the states CLAUDE.md requires every
 * data-driven view to handle.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Document, DocumentStatus } from "@/api/documents";
import { DocumentList } from "@/components/dashboard/DocumentList";

function doc(overrides: Partial<Document> = {}): Document {
  return {
    id: "d1",
    business_id: "b1",
    filename: "handbook.pdf",
    mime_type: "application/pdf",
    status: "ready",
    error: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderList(overrides: Partial<Parameters<typeof DocumentList>[0]> = {}) {
  const onDelete = vi.fn();
  render(
    <DocumentList
      documents={[doc()]}
      isLoading={false}
      isError={false}
      errorMessage={undefined}
      onDelete={onDelete}
      deletingId={undefined}
      {...overrides}
    />,
  );
  return { onDelete };
}

describe("DocumentList — render states", () => {
  it("shows a loading skeleton while fetching", () => {
    renderList({ isLoading: true, documents: undefined });

    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText(/loading documents/i)).toBeInTheDocument();
  });

  it("shows the error reason when the fetch fails", () => {
    renderList({ isError: true, errorMessage: "Network unreachable", documents: undefined });

    expect(screen.getByRole("alert")).toHaveTextContent(/couldn't load documents/i);
    expect(screen.getByRole("alert")).toHaveTextContent("Network unreachable");
  });

  it("shows an actionable empty state when the tenant has no documents", () => {
    renderList({ documents: [] });

    expect(screen.getByText(/no documents uploaded yet/i)).toBeInTheDocument();
    expect(screen.getByText(/upload a document above/i)).toBeInTheDocument();
  });

  it("treats undefined documents as empty rather than crashing", () => {
    renderList({ documents: undefined });

    expect(screen.getByText(/no documents uploaded yet/i)).toBeInTheDocument();
  });

  it("renders one row per document", () => {
    renderList({
      documents: [doc({ id: "d1", filename: "a.pdf" }), doc({ id: "d2", filename: "b.md" })],
    });

    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.md")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});

describe("DocumentList — ingestion status", () => {
  const statuses: DocumentStatus[] = ["pending", "processing", "ready", "failed"];

  it.each(statuses)("renders the %s status label", (status) => {
    renderList({ documents: [doc({ status })] });

    expect(screen.getByText(status)).toBeInTheDocument();
  });

  it("surfaces the failure reason on a failed document as an alert", () => {
    renderList({
      documents: [doc({ status: "failed", error: "This document could not be processed." })],
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This document could not be processed.",
    );
  });

  it("does not render an error line for a ready document", () => {
    renderList({ documents: [doc({ status: "ready", error: null })] });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not render an error line for a failed document with no reason", () => {
    renderList({ documents: [doc({ status: "failed", error: null })] });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("DocumentList — deletion", () => {
  it("passes the document id to onDelete", () => {
    const { onDelete } = renderList({ documents: [doc({ id: "doc-42" })] });

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(onDelete).toHaveBeenCalledWith("doc-42");
  });

  it("disables the button and shows progress for the document being deleted", () => {
    renderList({ documents: [doc({ id: "doc-42" })], deletingId: "doc-42" });

    const button = screen.getByRole("button", { name: /deleting/i });
    expect(button).toBeDisabled();
  });

  it("leaves other rows interactive while one is being deleted", () => {
    renderList({
      documents: [doc({ id: "d1", filename: "a.pdf" }), doc({ id: "d2", filename: "b.pdf" })],
      deletingId: "d1",
    });

    expect(screen.getByRole("button", { name: /^delete$/i })).toBeEnabled();
  });
});
