import { Sandbox } from "railway";
import { timingSafeEqual } from "node:crypto";

// SD-49: authenticated gateway to a checkpointed Railway Sandbox VM.
// Its checkpoint must contain /tmp/zaklang and the zaklang-sandbox Docker image.

type EvaluationRequest = {
  source: string;
  task_id: string;
  language: "python" | "zak";
  timeout_s: number;
};

type Language = "python" | "zak";

interface EvalResult {
  exec_outcome: "pass" | "fail" | "timeout" | "oom" | "crash" | "not_run";
  tests_passed: number;
  tests_total: number;
  per_test: boolean[];
  failure_summary: string | null;
  compile_ok: boolean | null;
  compile_errors: Array<Record<string, unknown>>;
  transpiled_python: string | null;
  execution_ms: number;
}

const LIMIT = 20000;
let busy = false;
const program = [
  "from dataclasses import asdict",
  "import json",
  "from zakbench.evaluation.evaluator import evaluate",
  "with open('/tmp/zaklang/_request.json') as f: data = json.load(f)",
  "result = evaluate(data['source'], data['task_id'], data['language'], timeout_s=data['timeout_s'])",
  "print(json.dumps(asdict(result)))",
].join("\n");

const answer = (status: number, data: unknown) =>
  Response.json(data, { status, headers: { "Cache-Control": "no-store" } });

function authenticate(request: Request): boolean {
  const secret = Bun.env.SANDBOX_WORKER_TOKEN;
  const header = request.headers.get("authorization") ?? "";
  if (!secret || !header.startsWith("Bearer ")) return false;
  const a = Buffer.from(header.slice(7));
  const b = Buffer.from(secret);
  return a.length === b.length && timingSafeEqual(a, b);
}

// Diagnostic only: prevent tokens and submitted source from entering logs.
function reportFailure(stage: string, error: unknown): void {
  let message = error instanceof Error ? error.message : String(error);
  for (const secret of [Bun.env.RAILWAY_TOKEN, Bun.env.RAILWAY_API_TOKEN, Bun.env.SANDBOX_WORKER_TOKEN]) {
    if (secret) message = message.split(secret).join("[REDACTED]");
  }
  const name = error instanceof Error ? error.name : "UnknownError";
  console.error("SD49 orchestration failure", stage, name, message.slice(0, 250).replace(/[\r\n]/g, " "));
}

async function evaluate(data: EvaluationRequest): Promise<EvalResult> {
  const checkpoint = Bun.env.SANDBOX_CHECKPOINT;
  if (!checkpoint) throw Error("Checkpoint not configured");
  let box: Sandbox;
  try {
    box = await Sandbox.create(checkpoint, {
      networkIsolation: "ISOLATED",
      idleTimeoutMinutes: 5,
    });
  } catch (error) {
    reportFailure("create_checkpoint_vm", error);
    throw error;
  }
  let stage = "write_input";
  try {
    await box.files.write("/tmp/zaklang/_request.json", JSON.stringify(data), { mode: 0o600 });
    stage = "write_evaluator";
    await box.files.write("/tmp/zaklang/_evaluate.py", program, { mode: 0o600 });
    stage = "exec_evaluator";
    const result = await box.exec("/tmp/zaklang/.venv/bin/python _evaluate.py", {
      cwd: "/tmp/zaklang",
      timeoutSec: Math.ceil(data.timeout_s) + 90,
      maxOutputBytes: 65536,
      ephemeral: true,
    });
    if (result.exitCode !== 0 || result.timedOut || result.truncated)
      throw Error("Worker command did not finish normally");
    stage = "parse_evaluator_result";
    const payload: EvalResult = JSON.parse(result.stdout.trim());
    if (!["pass", "fail", "timeout", "oom", "crash", "not_run"].includes(payload.exec_outcome))
      throw Error("Invalid grader response");
    return payload;
  } catch (error) {
    reportFailure(stage, error);
    throw error;
  } finally {
    try { await box.destroy(); }
    catch { console.error("Sandbox teardown failed", box.id); }
  }
}

Bun.serve({
  hostname: "0.0.0.0", port: Number(Bun.env.PORT || 8080),
  async fetch(request: Request): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path === "/health" && request.method === "GET") {
      const configured = Boolean(Bun.env.SANDBOX_WORKER_TOKEN &&
        (Bun.env.RAILWAY_TOKEN || Bun.env.RAILWAY_API_TOKEN) && Bun.env.RAILWAY_ENVIRONMENT_ID &&
        Bun.env.SANDBOX_CHECKPOINT);
      return answer(configured ? 200 : 503, {
        status: configured ? "ok" : "not_configured", configured
      });
    }
    if (path !== "/evaluate") return answer(404, { detail: "Not found" });
    if (request.method !== "POST") return answer(405, { detail: "Method not allowed" });
    if (!authenticate(request)) return answer(401, { detail: "Unauthorized" });
    if (!(Bun.env.RAILWAY_TOKEN || Bun.env.RAILWAY_API_TOKEN) || !Bun.env.SANDBOX_CHECKPOINT)
      return answer(503, { detail: "Worker is not configured" });
    if (busy) return answer(429, { detail: "Worker busy" });
    const size = Number(request.headers.get("content-length") || 0);
    if (size > 25000) return answer(413, { detail: "Payload too large" });
    let data: EvaluationRequest;
    try {
      const raw = await request.text();
      if (new TextEncoder().encode(raw).length > 25000)
        return answer(413, { detail: "Payload too large" });
      const candidate = JSON.parse(raw) as Partial<EvaluationRequest>;
      if (typeof candidate.source !== "string" || !candidate.source.trim() ||
          new TextEncoder().encode(candidate.source).length > LIMIT ||
          typeof candidate.task_id !== "string" || candidate.task_id.length > 80 ||
          !/^[a-z0-9_]+$/.test(candidate.task_id) ||
          !["python", "zak"].includes(candidate.language ?? "") ||
          !Number.isFinite(candidate.timeout_s ?? 5) ||
          (candidate.timeout_s ?? 5) <= 0 || (candidate.timeout_s ?? 5) > 60)
        return answer(400, { detail: "Invalid evaluation request" });
      data = {
        source: candidate.source, task_id: candidate.task_id, language: candidate.language as Language,
        timeout_s: candidate.timeout_s ?? 5,
      };
    } catch {
      return answer(400, { detail: "Invalid JSON" });
    }
    busy = true;
    try { return answer(200, await evaluate(data)); }
    catch {
      return answer(503, { detail: "Sandbox evaluation unavailable" });
    } finally { busy = false; }
  },
});
