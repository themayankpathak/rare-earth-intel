// Rare Earth Intel question box: a Cloudflare Worker with two jobs.
//
// 1. LOOKUP: turn a question into a lookup (who, what, material, part, year); every value is checked against
//    the list of what exists in the data, anything else is refused. The website then finds the numbers itself.
// 2. WRITE: turn the facts the website found (numbers, trend, revisions, notes, checks) into a short answer.
//    A number guard then checks that every number in the model's text appears in those facts; if one does
//    not, the text is thrown away and the website shows its plain answer instead.
// The model never supplies a number of its own and never does arithmetic.
//
// Setup (Cloudflare dashboard): paste this file into a Worker, add a Workers AI binding named AI, deploy.

// Which language model to use. Any Workers AI text model works; change this one line to try another,
// then re-run scripts/evaluate_chatbot.py to measure it on the 20 test questions.
const MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

// The list of what exists in the data, published with the website by scripts/build_site.py.
const VOCABULARY_URL = "https://themayankpathak.github.io/rare-earth-intel/data/vocabulary.json";

// Only the website (and a local preview) may call this Worker from a browser.
const ALLOWED_ORIGINS = ["https://themayankpathak.github.io", "http://localhost:8000"];

const MAX_QUESTION_LENGTH = 300;
const MAX_FACTS_LENGTH = 8000;

let vocabularyCache = null;

async function vocabulary() {
  // Fetch the list once per Worker instance; Cloudflare also caches it for an hour.
  if (!vocabularyCache) {
    const response = await fetch(VOCABULARY_URL, { cf: { cacheTtl: 3600 } });
    vocabularyCache = await response.json();
  }
  return vocabularyCache;
}

export function instructions(entries) {
  // The model's instructions: what exists in the data, and the only answer format allowed.
  const lines = entries.map(e =>
    `- who="${e.entity}" what="${e.metric}" (${e.metric_means}); materials: ${e.materials.join(", ") || "none"}; ` +
    `parts: ${e.segments.join(", ") || "none"}; years: ${e.years.join(", ")}`);
  return [
    "You turn a question about rare earth data into a lookup. You never answer with numbers yourself.",
    "These are the only things in the data:",
    ...lines,
    "",
    "Rules:",
    "- Reply with one JSON object and nothing else:",
    '  {"answerable": true, "entity": "...", "metric": "...", "material": "..." or null, "segment": "..." or null, "year": "FY2024" or null, "reason": ""}',
    "- entity, metric, material, segment and year must be copied exactly from the list above.",
    "- Years are written FY2024. A plain year like 2024 means FY2024. Lynas's year ends on 30 June.",
    "- Use null for material, segment or year when the question does not say (year null = all years).",
    "- total_REO means all rare earths together; NdPr is neodymium-praseodymium; Nd, Pr, Dy, Tb, Ce, La are single elements.",
    "- Neo's parts are Magnequench, C&O (chemicals and oxides) and Rare Metals; MP's parts are Materials and Magnetics.",
    '- If the question asks for a forecast, an opinion, advice, a calculation, or anything not in the list,',
    '  reply {"answerable": false, "reason": "<one short sentence saying what is missing>"}.',
  ].join("\n");
}

export function parseReply(reply) {
  // The model's reply as an object: take the first {...} in its text (models sometimes add words around it).
  if (reply && typeof reply === "object") return reply;
  const text = String(reply ?? "");
  const start = text.indexOf("{"), end = text.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  try { return JSON.parse(text.slice(start, end + 1)); } catch { return null; }
}

export function validate(lookup, entries) {
  // Accept the model's lookup only if every value really exists in the data; otherwise refuse.
  const refuse = reason => ({ answerable: false, reason });
  if (!lookup || typeof lookup !== "object") return refuse("The question could not be turned into a lookup.");
  if (lookup.answerable === false) return refuse(String(lookup.reason || "That is not in this data.").slice(0, 200));
  const entry = entries.find(e => e.entity === lookup.entity && e.metric === lookup.metric);
  if (!entry) return refuse("There is no such figure for that company or country in this data.");
  const material = lookup.material ?? null, segment = lookup.segment ?? null, year = lookup.year ?? null;
  if (material !== null && !entry.materials.includes(material)) return refuse(`No ${lookup.metric} figure for ${material} in this data.`);
  if (segment !== null && !entry.segments.includes(segment)) return refuse(`No ${lookup.metric} figure for ${segment} in this data.`);
  if (year !== null && !entry.years.includes(year)) return refuse(`This data has no ${lookup.metric} figure for ${lookup.entity} in ${year}.`);
  return { answerable: true, entity: entry.entity, metric: entry.metric, material, segment, year };
}

export function writingInstructions() {
  // The model's instructions for writing the answer from the facts the website found.
  return [
    "You write a short answer to a question about rare earth data, using ONLY the facts given as JSON.",
    "Rules:",
    "- 2 to 4 plain sentences, under 90 words. No lists, no headings, no markdown.",
    "- Start with the direct answer: the figure, its unit, the year, and the document it comes from.",
    "- Then add the most useful context from the facts: the trend over nearby years, a revision between documents",
    "  (say when an earlier figure was an estimate), a note, or an open question.",
    "- Copy every number exactly as it is written in the facts. Do not round, convert or recalculate.",
    "- Never calculate anything: no percentages, differences, totals, averages or growth rates.",
    "- Write counts in words (two editions, three reports), never as digits.",
    "- If the facts do not say something, do not say it.",
  ].join("\n");
}

export function numbersIn(text) {
  // Every number written in a text, as plain values: "41,992,000" -> 41992000, "$4.7/kg" -> 4.7.
  return (String(text).match(/\d[\d,]*(?:\.\d+)?/g) || []).map(n => Number(n.replace(/,/g, "")));
}

export function guard(text, facts) {
  // True if every number in the model's text also appears somewhere in the facts it was given.
  const allowed = new Set(numbersIn(JSON.stringify(facts)));
  const unknown = numbersIn(text).filter(n => !allowed.has(n));
  return { ok: unknown.length === 0, unknown };
}

function reply(body, status, origin) {
  // A 204 reply (the answer to the browser's "may I?" preflight check) must have no body at all.
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
    if (request.method === "OPTIONS") return reply({}, 204, allowed);
    if (request.method !== "POST") return reply({ error: "Send a POST request with a question." }, 405, allowed);
    if (!ALLOWED_ORIGINS.includes(origin)) return reply({ error: "This question box only answers the Rare Earth Intel website." }, 403, allowed);

    let body = {};
    try { body = await request.json(); } catch { /* handled below */ }
    const question = String(body.question || "").trim();
    if (!question) return reply({ error: "Ask a question." }, 400, allowed);
    if (question.length > MAX_QUESTION_LENGTH) return reply({ error: `Keep the question under ${MAX_QUESTION_LENGTH} characters.` }, 400, allowed);

    // Job 2: write the answer from the facts the website found, then check every number in it.
    if (body.mode === "write") {
      const facts = body.facts;
      if (!facts || JSON.stringify(facts).length > MAX_FACTS_LENGTH) return reply({ error: "No facts to write from." }, 400, allowed);
      try {
        const result = await env.AI.run(MODEL, {
          messages: [{ role: "system", content: writingInstructions() },
                     { role: "user", content: `Question: ${question}\nFacts: ${JSON.stringify(facts)}` }],
          max_tokens: 220,
          temperature: 0,
        });
        const text = String(result.response ?? "").trim();
        const check = guard(text, facts);
        return reply(check.ok ? { text, verified: true, model: MODEL }
                              : { verified: false, unknown: check.unknown.slice(0, 5), model: MODEL }, 200, allowed);
      } catch (error) {
        return reply({ error: "The question box is unavailable right now. The search table below always works." }, 503, allowed);
      }
    }

    // Job 1: turn the question into a checked lookup.
    try {
      const entries = await vocabulary();
      const result = await env.AI.run(MODEL, {
        messages: [{ role: "system", content: instructions(entries) }, { role: "user", content: question }],
        max_tokens: 200,
        temperature: 0,
      });
      const lookup = validate(parseReply(result.response), entries);
      return reply({ ...lookup, model: MODEL }, 200, allowed);
    } catch (error) {
      // Most often the free daily allowance is used up; the website points to the search table instead.
      return reply({ error: "The question box is unavailable right now. The search table below always works." }, 503, allowed);
    }
  },
};
