import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, setCsrfToken } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken("");
});

describe("cliente HTTP na exclusão", () => {
  it("explica HTTP 405 de uma API antiga em vez de mostrar Method Not Allowed", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: "Method Not Allowed" }), {
            status: 405,
          }),
        ),
    );
    await expect(
      apiRequest("/platforms/pilot", { method: "DELETE" }),
    ).rejects.toMatchObject({
      status: 405,
      message: expect.stringContaining("API em execução está desatualizada"),
    });
  });

  it("envia DELETE com sessão/CSRF e aceita 204 sem tentar ler JSON", async () => {
    setCsrfToken("test-csrf");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      apiRequest("/platforms/pilot", { method: "DELETE" }),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/platforms/pilot"),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRF-Token": "test-csrf" }),
      }),
    );
  });
});
