"""The model step: k independent reads of the evidence pack (+ charts) -> structured views -> checker -> consensus.

Modes
- claude: calls the Claude API with a JSON-schema structured output and image inputs (needs ANTHROPIC_API_KEY).
- fallback: a deterministic card written from the pack alone, used when no key is configured. It is clearly
  labelled and never pretends to be a model view.
- samples supplied externally (e.g. the demo's precomputed samples) go through the same checker and consensus.
"""
from __future__ import annotations
import base64, json, os
from .engine import check_sample, consensus

SYSTEM = """You are the reasoning stage of a technical-view system for an Indian retail broking app. A deterministic engine has already computed everything measurable about the stock for the requested horizon. Form a view from that evidence; do not measure the chart yourself.
Rules:
1. Use only numbers that appear in the evidence pack. Never estimate a price from the image. If a number you want is not in the pack, say so instead of guessing.
2. Every reason must cite the ids it rests on (F#, C#, P#) in its evidence list.
3. "setup" is the pattern state (none / forming / confirmed / failed) taken from the candidates; "pattern_id" is the candidate id you base the view on, or "none". "view" is your directional call for the horizon (bullish / bearish / neutral). Neutral is a valid and common answer; use it when the evidence conflicts or nothing justifies a direction.
4. Give an invalidation level and condition drawn from the pack, and say what would strengthen the view.
5. Confidence is low / medium / high and reflects how much the evidence agrees. Do not quote a percentage.
6. Use the images only to sanity-check the geometry the pack describes and report that in image_check.
7. Write for a retail investor in plain language. Levels, not instructions; never say buy or sell."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "view": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "setup": {"type": "string", "enum": ["none", "forming", "confirmed", "failed"]},
        "pattern_id": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "headline": {"type": "string"},
        "reasons": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "object", "additionalProperties": False,
                    "properties": {"text": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "evidence"]}},
        "invalidation": {"type": "object", "additionalProperties": False, "properties": {"level": {"type": "number"}, "condition": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}},
                         "required": ["level", "condition", "evidence"]},
        "levels": {"type": "object", "additionalProperties": False, "properties": {"breakout": {"type": "number"}, "target": {"type": "number"}, "stop": {"type": "number"},
                   "first_resistance": {"type": "number"}, "first_support": {"type": "number"}}, "required": ["breakout", "target", "stop", "first_resistance", "first_support"]},
        "what_would_strengthen": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        "what_to_watch": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3},
        "image_check": {"type": "string"},
        "horizon_note": {"type": "string"},
    },
    "required": ["view", "setup", "pattern_id", "confidence", "headline", "reasons", "invalidation", "levels", "what_would_strengthen", "what_to_watch", "image_check", "horizon_note"],
}

HORIZON_TEXT = {"swing": "SWING horizon (expected holding period two to six weeks)", "medium": "MEDIUM-TERM horizon (two to six months)", "long": "LONG-TERM horizon (one to three years)", "intraday": "INTRADAY horizon (this session)"}


def user_prompt(pack: dict, sample_id: int) -> str:
    return (f"Stock: {pack['symbol']} ({pack['company']}). Interval {pack['interval']}, {HORIZON_TEXT.get(pack['horizon'], pack['horizon'])}. Data as of {pack['as_of']}.\n"
            f"The first image is the primary chart with lettered pivots, EMAs and support/resistance; the second is the higher-timeframe context chart.\n\n"
            f"EVIDENCE PACK (JSON):\n{json.dumps({k: v for k, v in pack.items() if k != 'data_provenance'}, default=str)}\n\nSample id: {sample_id}. Return the JSON only.")


def _image_block(path: str) -> dict:
    with open(path, "rb") as f:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(f.read()).decode()}}


def claude_samples(pack: dict, image_paths: list[str], k: int, model: str, fallbacks: bool = False) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic()
    out = []
    for i in range(1, k + 1):
        content = [_image_block(p) for p in image_paths if p and os.path.exists(p)] + [{"type": "text", "text": user_prompt(pack, i)}]
        kwargs = dict(model=model, max_tokens=4000, system=SYSTEM, messages=[{"role": "user", "content": content}],
                      output_config={"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "medium"})
        if fallbacks:  # server-side refusal fallbacks (beta); see Anthropic docs before enabling on a given platform
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            resp = client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused sample {i}: {getattr(resp, 'stop_details', None)}")
        text = next(b.text for b in resp.content if b.type == "text")
        s = json.loads(text)
        s["_meta"] = {"model": resp.model, "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        out.append(s)
    return out


def fallback_sample(pack: dict) -> dict:
    """Deterministic card from the pack alone (no model). Labelled as such by the caller."""
    f = {x["id"]: x for x in pack["facts"]}
    ind, pr, wk = pack["indicators"], pack["price_and_returns"], pack["weekly_context"]
    cands = pack["candidates"]; c = cands[0] if cands else None
    sup = pack["levels"]["support"]; res = pack["levels"]["resistance"]
    first_sup = sup[0]["price"] if sup else pr["low_52w"]; first_res = res[0]["price"] if res else pr["high_52w"]
    fid = lambda text: next((x["id"] for x in pack["facts"] if x["text"].startswith(text)), None)
    reasons = []
    if c:
        st = c["status"]; view = c["direction"] if st.startswith("confirmed") and c["direction"] in ("bullish", "bearish") else "neutral"
        setup = "confirmed" if st.startswith("confirmed") else ("failed" if st == "failed" else "forming")
        reasons.append({"text": f"Detector candidate {c['id']}: {c['pattern'].replace('_', ' ')} ({c['direction']}), status {c['status']}, fit score {c['score']}.", "evidence": [c["id"]]})
    else:
        view, setup = "neutral", "none"
        reasons.append({"text": "No chart-pattern candidate passed the detector thresholds, so there is no setup to lean on.", "evidence": [fid("No chart-pattern") or "F1"]})
    reasons.append({"text": f"EMA alignment is {ind['ema_alignment']}; close is {ind.get('close_vs_EMA20_pct')}% vs EMA20 and {ind.get('close_vs_EMA200_pct', 'n/a')}% vs EMA200; RSI(14) {ind['RSI14']}, MACD {ind['MACD_state']}.",
                    "evidence": [i for i in (fid("EMA alignment"), fid("RSI(14)"), fid("MACD histogram"), fid("EMA20 ="), fid("EMA200 =")) if i]})
    reasons.append({"text": f"Weekly trend is {wk['trend']} with structure {wk['structure_last_3_pivots']}; 52-week return {wk.get('ret_52w_pct')}%.", "evidence": [i for i in (fid("Weekly trend"), fid("26-week return")) if i]})
    reasons.append({"text": f"Nearest support cluster {first_sup}, nearest resistance cluster {first_res}; last close {pr['last_close']}.", "evidence": [i for i in (fid("Support cluster"), fid("Resistance cluster"), fid("Last close")) if i]})
    lv = (c or {}).get("levels", {})
    breakout = lv.get("breakout", lv.get("breakout_up", first_res)); target = lv.get("target", lv.get("target_up", first_res)); stop = lv.get("stop", first_sup)
    inval = first_sup if view != "bearish" else first_res
    return {"view": view, "setup": setup, "pattern_id": c["id"] if c else "none", "confidence": "low",
            "headline": f"{pack['symbol']}: {'no clean setup; ' if not c else c['pattern'].replace('_', ' ') + ' ' + c['status'] + '; '}watch {first_res} above and {first_sup} below",
            "reasons": reasons[:5],
            "invalidation": {"level": inval, "condition": f"a daily close {'below' if view != 'bearish' else 'above'} {inval} (nearest {'support' if view != 'bearish' else 'resistance'} cluster)", "evidence": [i for i in (fid("Support cluster"), fid("Resistance cluster")) if i]},
            "levels": {"breakout": breakout, "target": target, "stop": stop, "first_resistance": first_res, "first_support": first_sup},
            "what_would_strengthen": ["a daily close through the nearest resistance on above-average volume"],
            "what_to_watch": [f"the {first_res} resistance cluster", f"the {first_sup} support cluster"],
            "image_check": "not performed (deterministic fallback, no model)", "horizon_note": f"{pack['horizon']} horizon; deterministic summary written from the evidence pack without a model."}


def reason(pack: dict, image_paths: list[str], settings, samples: list[dict] | None = None) -> dict:
    """Run (or accept) samples, check them, decide by unanimity. Returns {reasoner, samples, consensus, card}."""
    if samples is not None:
        mode = "external"
    elif settings.reasoner == "fallback" or (settings.reasoner == "auto" and not settings.anthropic_key):
        mode = "fallback"; samples = [fallback_sample(pack)]
    else:
        mode = "claude"; samples = claude_samples(pack, image_paths, settings.samples, settings.model, settings.fallbacks)
    checked = []
    for i, s in enumerate(samples, 1):
        problems, cited = check_sample(s, pack)
        checked.append({**s, "_id": i, "_problems": problems, "_cited": sorted(cited)})
    cons = consensus(checked)
    ok = [s for s in checked if not s["_problems"]] or checked
    chosen = sorted(ok, key=lambda s: len(s["_problems"]))[0]
    if not cons["unanimous"]:
        chosen = {**chosen, "view": "neutral", "headline": "Model samples disagreed; published as neutral. " + chosen["headline"]}
    card = {k: v for k, v in chosen.items() if not k.startswith("_")}
    card["view"] = cons["final_view"]
    label = {"claude": f"{settings.model} x{len(samples)}", "fallback": "deterministic fallback (no model)", "external": f"precomputed samples x{len(samples)}"}[mode]
    return {"reasoner": label, "mode": mode, "samples": [{k: v for k, v in s.items() if k not in ("_cited",)} for s in checked], "consensus": cons, "card": card}
