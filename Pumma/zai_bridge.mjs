// Pumma zai bridge - connects the Pumma Python server to the z-ai-web-dev-sdk
// (used inside the Z.ai sandbox for live previews). Reads JSON on stdin:
//   { "messages": [ { "role": "system"|"user"|"assistant", "content": "..." }, ... ] }
// Writes JSON on stdout: { "reply": "..." }  or  { "error": "..." }
// Note: the Pumma identity system prompt is added by the Python side (pumma.py).
import fs from "fs";

async function main() {
  let raw = "";
  try {
    raw = fs.readFileSync(0, "utf8");
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: "Cannot read stdin: " + e.message }));
    return;
  }
  let input;
  try {
    input = JSON.parse(raw);
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: "Invalid JSON input." }));
    return;
  }
  const msgs = Array.isArray(input.messages) ? input.messages : [];
  if (!msgs.length) {
    process.stdout.write(JSON.stringify({ error: "No messages." }));
    return;
  }
  // The z-ai sdk expects the system prompt on the "assistant" role slot.
  const msgs2 = msgs.map((m, i) =>
    i === 0 && m.role === "system" ? { ...m, role: "assistant" } : m
  );

  const { default: ZAI } = await import("z-ai-web-dev-sdk");
  const zai = await ZAI.create();
  const completion = await zai.chat.completions.create({
    messages: msgs2,
    thinking: { type: "disabled" },
  });
  const reply = completion?.choices?.[0]?.message?.content || "";
  if (!reply) {
    process.stdout.write(JSON.stringify({ error: "Empty model response." }));
    return;
  }
  process.stdout.write(JSON.stringify({ reply }));
}

main().catch((e) => {
  process.stdout.write(JSON.stringify({ error: String(e && e.message ? e.message : e) }));
});
