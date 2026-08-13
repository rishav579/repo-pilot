import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "./client";

describe("RepoPilot API Client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("should handle successful health check response", async () => {
    const mockResponse = { status: "ok" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const res = await api.getHealth();
    expect(res).toEqual({ status: "ok" });
  });

  it("should handle HTTP 400 Bad Request error detail", async () => {
    const errorBody = { detail: "Repository path does not exist" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => errorBody,
    } as Response);

    await expect(api.registerRepository("/invalid/path")).rejects.toThrow(ApiError);
  });

  it("should handle network connection failure gracefully", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Failed to fetch"));

    await expect(api.getHealth()).rejects.toThrow(
      "Network or server connection failure: Failed to fetch"
    );
  });
});
