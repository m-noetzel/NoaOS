import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

// Read the manifest from the public directory
const _dirname = dirname(fileURLToPath(import.meta.url));
const manifestPath = resolve(_dirname, "../../public/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));

describe("PWA manifest", () => {
  it("has required fields (name, short_name, start_url, display, icons)", () => {
    expect(manifest).toHaveProperty("name");
    expect(manifest).toHaveProperty("short_name");
    expect(manifest).toHaveProperty("start_url");
    expect(manifest).toHaveProperty("display");
    expect(manifest).toHaveProperty("icons");
    expect(Array.isArray(manifest.icons)).toBe(true);
    expect(manifest.icons.length).toBeGreaterThan(0);
  });

  it('manifest display mode is "standalone"', () => {
    expect(manifest.display).toBe("standalone");
  });

  it('manifest has correct app name "Noa"', () => {
    expect(manifest.name).toBe("Noa");
    expect(manifest.short_name).toBe("Noa");
  });

  it("icons include 192x192 and 512x512 sizes", () => {
    const sizes = manifest.icons.map(
      (icon: { sizes: string }) => icon.sizes,
    );
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");

    // Verify icons have required properties
    for (const icon of manifest.icons) {
      expect(icon).toHaveProperty("src");
      expect(icon).toHaveProperty("sizes");
      expect(icon).toHaveProperty("type");
    }
  });
});
