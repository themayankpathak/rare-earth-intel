// Rare Earth Intel question box: a Cloudflare Worker.
//
// It receives a question from the website, asks a language model to turn it into a LOOKUP (who, what,
// material, part, year), checks every value against the list of what exists in the data, and sends the
// lookup back. The website then finds the numbers itself and shows them with document and page.
// The model never writes a number and never does arithmetic.
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

    let question = "";
    try { question = String((await request.json()).question || "").trim(); } catch { /* handled below */ }
    if (!question) return reply({ error: "Ask a question." }, 400, allowed);
    if (question.length > MAX_QUESTION_LENGTH) return reply({ error: `Keep the question under ${MAX_QUESTION_LENGTH} characters.` }, 400, allowed);

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
