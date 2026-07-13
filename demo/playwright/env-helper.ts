/** Update .env with key=value pairs (merge, do not overwrite unrelated keys). */
import fs from "fs";
import path from "path";

const envPath = path.resolve(__dirname, "../../.env");

export function updateEnv(updates: Record<string, string>): void {
  let content = "";
  if (fs.existsSync(envPath)) {
    content = fs.readFileSync(envPath, "utf-8");
  }

  const lines = content.split(/\r?\n/);
  const keys = new Set(Object.keys(updates));

  const out: string[] = [];
  for (const line of lines) {
    const match = line.match(/^([A-Z0-9_]+)=/);
    if (match && keys.has(match[1])) {
      continue;
    }
    if (line.trim() !== "") {
      out.push(line);
    }
  }

  for (const [key, value] of Object.entries(updates)) {
    out.push(`${key}=${value}`);
  }

  fs.writeFileSync(envPath, out.join("\n") + "\n", "utf-8");
  console.log(`Updated .env: ${Object.keys(updates).join(", ")}`);
}

export function readEnv(): Record<string, string> {
  if (!fs.existsSync(envPath)) {
    return {};
  }
  const result: Record<string, string> = {};
  for (const line of fs.readFileSync(envPath, "utf-8").split(/\r?\n/)) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m) {
      result[m[1]] = m[2];
    }
  }
  return result;
}
