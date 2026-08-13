import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./client";

describe("RepoPilot API Client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("should handle successful health check response", async () => {
    const mockResponse = { status: "ok" };
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);
    vi.stubGlobal("fetch", mockFetch);

    const res = await api.getHealth();
    expect(res).toEqual({ status: "ok" });
  });

  it("should handle HTTP 400 Bad Request error detail", async () => {
    const errorBody = { detail: "Repository path does not exist" };
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => errorBody,
    } as Response);
    vi.stubGlobal("fetch", mockFetch);

    await expect(api.registerRepository("/invalid/path")).rejects.toThrow(
      "Repository path does not exist"
    );
  });

  it("should handle network connection failure gracefully", async () => {
    const mockFetch = vi.fn().mockRejectedValueOnce(new Error("Failed to fetch"));
    vi.stubGlobal("fetch", mockFetch);

    await expect(api.getHealth()).rejects.toThrow(
      "Network or server connection failure: Failed to fetch"
    );
  });
});
