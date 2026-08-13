import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Header } from "./components/Header";
import { RepositoryPanel } from "./components/RepositoryPanel";
import { QueryPanel } from "./components/QueryPanel";
import { AnswerPanel } from "./components/AnswerPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import type { RAGResponse, RepositoryRecord } from "./api/types";

describe("RepoPilot UI Components", () => {
  const mockRepo: RepositoryRecord = {
    repository_id: "repo-30aab1f218fd",
    canonical_path: "C:/Users/wwwri/OneDrive/Documents/AI-PROJECTS/repo-pilot",
    display_name: "repo-pilot",
    status: "ready",
    created_at: "2026-08-13T00:00:00Z",
    updated_at: "2026-08-13T00:00:00Z",
    indexed_file_count: 98,
    indexed_chunk_count: 423,
    embedding_enabled: false,
  };

  it("Header renders title and online status badge", () => {
    render(<Header isBackendOnline={true} />);
    expect(screen.getByText("RepoPilot")).toBeDefined();
    expect(screen.getByText("API Engine Connected")).toBeDefined();
  });

  it("RepositoryPanel renders registered repository and ready status", () => {
    const onSelect = vi.fn();
    const onRegister = vi.fn();
    const onTrigger = vi.fn();

    render(
      <RepositoryPanel
        repositories={[mockRepo]}
        activeRepository={mockRepo}
        onSelectRepository={onSelect}
        onRegisterRepository={onRegister}
        onTriggerIndexing={onTrigger}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText("repo-pilot")).toBeDefined();
    expect(screen.getByText("Ready")).toBeDefined();
    expect(screen.getByText(/98 files \/ 423 chunks/)).toBeDefined();
  });

  it("QueryPanel allows submitting questions when repository is ready", () => {
    const onSubmit = vi.fn();

    render(
      <QueryPanel
        activeRepository={mockRepo}
        onQuerySubmit={onSubmit}
        isLoading={false}
      />
    );

    const textarea = screen.getByPlaceholderText(/Ask any natural language question/i);
    fireEvent.change(textarea, {
      target: { value: "Where is scan_repository and validate_repository_path defined in scanner?" },
    });

    const submitBtn = screen.getByRole("button", { name: /Ask RepoPilot/i });
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith({
      repository_path: mockRepo.canonical_path,
      question: "Where is scan_repository and validate_repository_path defined in scanner?",
      mode: "auto",
      top_k: 8,
      min_relevance_score: 0.005,
    });
  });

  it("AnswerPanel renders grounded answer and performance metrics", () => {
    const mockResponse: RAGResponse = {
      question: "Where is scan_repository defined?",
      answer: "Defined in scanner.py [1].",
      status: "grounded",
      citations: [
        {
          relative_path: "backend/app/services/ingestion/scanner.py",
          index_number: 1,
          is_valid: true,
          start_line: 250,
          end_line: 324,
          symbol_name: "scan_repository",
        },
      ],
      retrieval_mode: "auto",
      retrieved_candidate_count: 8,
      evidence_count: 1,
      valid_citation_count: 1,
      invalid_citation_count: 0,
      context_character_count: 800,
      context_truncated: false,
      provider_name: "mock",
      model_name: "mock-gpt-4",
      performance_ms: {
        retrieval_ms: 3.1,
        evidence_selection_ms: 0.4,
        context_assembly_ms: 0.2,
        llm_generation_ms: 0.1,
        total_ms: 3.8,
      },
    };

    render(<AnswerPanel response={mockResponse} />);

    expect(screen.getByText("Grounded Evidence Answer")).toBeDefined();
    expect(screen.getByText("Defined in scanner.py [1].")).toBeDefined();
    expect(screen.getByText(/Total: 3.8ms/)).toBeDefined();
  });

  it("EvidencePanel renders citation cards with symbol and line range", () => {
    const citations = [
      {
        relative_path: "backend/app/services/ingestion/scanner.py",
        index_number: 1,
        is_valid: true,
        start_line: 55,
        end_line: 88,
        symbol_name: "validate_repository_path",
      },
    ];

    render(<EvidencePanel citations={citations} />);

    expect(screen.getByText("[1]")).toBeDefined();
    expect(
      screen.getByText(/backend\/app\/services\/ingestion\/scanner\.py/)
    ).toBeDefined();
    expect(screen.getByText(/L55-L88/)).toBeDefined();
    expect(screen.getByText("validate_repository_path")).toBeDefined();
  });
});
