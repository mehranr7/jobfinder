import time
import json
import os
import re
import threading
import yaml
import traceback
import database
import utils

# Suppress FutureWarning from google.generativeai at import time
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as _legacy_genai
        GENAI_AVAILABLE = True
        genai = None  # signals to use legacy path
        _legacy_genai_module = _legacy_genai
    except ImportError:
        GENAI_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

STATE_RUNNING = "RUNNING"
STATE_PAUSED = "PAUSED"
STATE_STOPPED = "STOPPED"
current_state = STATE_RUNNING

# Cache for CV text extraction
uploaded_files_cache = {}

# General-purpose text models listed in Google's Gemini API pricing catalogue.
# The order is intentional: the evaluator tries the most capable model first,
# then moves towards faster/cheaper models when a model is unavailable or
# temporarily rate-limited. Keep this list free of audio, image, embedding,
# and tool-only models because the evaluator requests JSON text output.
DEFAULT_MODEL_PRIORITY = [
    "gemini-3.1-pro-preview",
    "gemini-2.5-pro",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite-preview-09-2025",
]

# Backwards-compatible alias for callers that imported the old constant.
FALLBACK_MODELS = DEFAULT_MODEL_PRIORITY
DEFAULT_MODEL_COOLDOWN_S = 300
MODEL_COOLDOWNS = {}
MODEL_COOLDOWNS_LOCK = threading.Lock()


def get_model_priority(config):
    """Return the configured model order, preserving YAML list order."""
    configured = config.get("evaluator_models")
    if isinstance(configured, str):
        configured = [configured]
    if not isinstance(configured, (list, tuple)):
        configured = []

    models = []
    for model in configured:
        if isinstance(model, str) and model.strip() and model.strip() not in models:
            models.append(model.strip())

    for model in DEFAULT_MODEL_PRIORITY:
        if model not in models:
            models.append(model)

    return models or list(DEFAULT_MODEL_PRIORITY)


def get_model_cooldown_s(config):
    """Return the temporary model quarantine duration in seconds."""
    try:
        return max(0.0, float(config.get("evaluator_model_cooldown_s", DEFAULT_MODEL_COOLDOWN_S)))
    except (TypeError, ValueError):
        return float(DEFAULT_MODEL_COOLDOWN_S)


def _model_cooldown_remaining(model_name):
    now = time.monotonic()
    with MODEL_COOLDOWNS_LOCK:
        entry = MODEL_COOLDOWNS.get(model_name)
        if not entry:
            return 0.0, ""
        remaining = entry["until"] - now
        if remaining <= 0:
            MODEL_COOLDOWNS.pop(model_name, None)
            return 0.0, ""
        return remaining, entry.get("reason", "temporary failure")


def _cooldown_model(model_name, reason, cooldown_s):
    if cooldown_s <= 0:
        return
    with MODEL_COOLDOWNS_LOCK:
        MODEL_COOLDOWNS[model_name] = {
            "until": time.monotonic() + cooldown_s,
            "reason": reason,
        }

def load_config():
    return utils.load_config()

def emit_log(msg, log_queue=None):
    print(msg, flush=True)
    if log_queue is not None:
        if hasattr(log_queue, "put"):
            try:
                log_queue.put(msg)
            except Exception:
                pass
        elif callable(log_queue):
            try:
                log_queue(msg)
            except Exception:
                pass

def check_state(log_queue=None):
    global current_state
    was_paused = False
    while current_state == STATE_PAUSED:
        if not was_paused:
            emit_log("\n--- EVALUATOR PAUSED ---", log_queue)
            was_paused = True
        time.sleep(0.5)
        
    if was_paused and current_state == STATE_RUNNING:
        emit_log("\n--- EVALUATOR RESUMED ---", log_queue)
        
    if current_state == STATE_STOPPED:
        emit_log("\n--- EVALUATOR STOPPED ---", log_queue)
        return False
        
    return True

def get_uploaded_cvs(cv_paths, log_queue=None):
    """
    Extracts text locally from PDF CVs.
    """
    global uploaded_files_cache
    gemini_files = []
    
    for path in cv_paths:
        if not os.path.exists(path):
            emit_log(f"[!] CV file not found: {path}", log_queue)
            continue
            
        if path in uploaded_files_cache:
            gemini_files.append(f"--- CV: {path} ---\n" + uploaded_files_cache[path])
            continue
            
        if not PYPDF2_AVAILABLE:
            emit_log("[!] PyPDF2 is not installed. Skipping PDF CV text extraction.", log_queue)
            continue

        emit_log(f"Extracting text from {path}...", log_queue)
        try:
            text = ""
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            uploaded_files_cache[path] = text
            gemini_files.append(f"--- CV: {path} ---\n" + text)
            emit_log(f"  -> Extracted {len(text)} characters", log_queue)
        except Exception as e:
            emit_log(f"[!] Failed to extract {path}: {e}", log_queue)
            
    return gemini_files

def _parse_response(res_text):
    """Parse JSON from Gemini response text, stripping markdown fences defensively."""
    res_text = res_text.strip()
    if res_text.startswith("```json"):
        res_text = res_text[7:]
    elif res_text.startswith("```"):
        res_text = res_text[3:]
    if res_text.endswith("```"):
        res_text = res_text[:-3]
    res_text = res_text.strip()
    
    try:
        return json.loads(res_text)
    except json.JSONDecodeError:
        # Try extracting largest JSON substring
        match = re.search(r'\{[\s\S]*\}', res_text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Defensively fix truncated JSON
        fixed = res_text
        if not fixed.endswith("}"):
            if not fixed.endswith('"'):
                fixed += '"'
            fixed += "\n}"
        return json.loads(fixed)

def _call_gemini_single(api_key, model_name, instruction_text, prompt_parts):
    """
    Executes a single API call against a specific Gemini model name.
    """
    if GENAI_AVAILABLE and genai is not None:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents="\n\n".join(prompt_parts),
            config=genai_types.GenerateContentConfig(
                system_instruction=instruction_text,
                response_mime_type="application/json",
                max_output_tokens=8192
            )
        )
        return response.text.strip()
    
    if GENAI_AVAILABLE and genai is None:
        _legacy_genai_module.configure(api_key=api_key)
        model = _legacy_genai_module.GenerativeModel(
            model_name,
            system_instruction=instruction_text,
            generation_config={
                "response_mime_type": "application/json",
                "max_output_tokens": 8192
            }
        )
        response = model.generate_content(prompt_parts)
        return response.text.strip()
    
    raise RuntimeError("No Gemini SDK available. Install google-genai: pip install google-genai")

def _call_gemini(api_key, model_names, instruction_text, prompt_parts, log_queue=None,
                 model_cooldown_s=DEFAULT_MODEL_COOLDOWN_S):
    """
    Calls Gemini using the configured priority order and falls back on error.

    ``model_names`` may be a string for backwards compatibility, or an
    ordered list/tuple. The first entry always has the highest priority.
    """
    if isinstance(model_names, str):
        models_to_try = [model_names] + [m for m in DEFAULT_MODEL_PRIORITY if m != model_names]
    else:
        models_to_try = []
        for model in model_names or DEFAULT_MODEL_PRIORITY:
            if isinstance(model, str) and model.strip() and model.strip() not in models_to_try:
                models_to_try.append(model.strip())
        if not models_to_try:
            models_to_try = list(DEFAULT_MODEL_PRIORITY)

    last_error = None
    attempted_model = False

    for index, m in enumerate(models_to_try, start=1):
        remaining, reason = _model_cooldown_remaining(m)
        if remaining:
            emit_log(
                f"  -> Skipping Gemini model {m}: {reason}; "
                f"cooldown {remaining:.0f}s remaining",
                log_queue,
            )
            continue

        attempted_model = True
        try:
            emit_log(f"  -> Trying Gemini model {index}/{len(models_to_try)}: {m}", log_queue)
            return _call_gemini_single(api_key, m, instruction_text, prompt_parts)
        except Exception as e:
            last_error = e
            err_str = str(e)
            err_lower = err_str.lower()
            if (
                "404" in err_str
                or "403" in err_str
                or "not found" in err_lower
                or "unsupported" in err_lower
                or "permission" in err_lower
                or "forbidden" in err_lower
                or "invalid model" in err_lower
            ):
                _cooldown_model(m, "unavailable", model_cooldown_s)
                emit_log(
                    f"[!] Model '{m}' unavailable; cooling it down for "
                    f"{model_cooldown_s:.0f}s and trying fallback...",
                    log_queue,
                )
                continue
            elif "429" in err_str or "quota" in err_str.lower():
                _cooldown_model(m, "rate limited", model_cooldown_s)
                emit_log(
                    f"[!] Rate limit on '{m}'; cooling it down for "
                    f"{model_cooldown_s:.0f}s and trying fallback model...",
                    log_queue,
                )
                continue
            else:
                # Other error, try fallback
                emit_log(f"[!] Error calling '{m}': {e}. Trying fallback...", log_queue)
                continue

    if not attempted_model:
        raise RuntimeError("All Gemini models are in cooldown; no API request was made.")
    raise last_error or RuntimeError("All Gemini model fallbacks failed.")

def load_instruction():
    default_inst = (
        'You are an expert HR recruiter evaluating a job match. '
        'Analyze the job description against my CVs. Return JSON with "eval_score" (0-100), '
        '"eval_reason" (1-3 sentences in English), "selected_cv" (filename), and "cover_letter" (German text or empty).'
    )
    if not os.path.exists("llm_instruction.txt"):
        with open("llm_instruction.txt", "w", encoding="utf-8") as f:
            f.write(default_inst)
    with open("llm_instruction.txt", "r", encoding="utf-8") as f:
        return f.read()

def evaluate_job_data(job, api_key, model_names, instruction_text, gemini_cvs, log_queue=None,
                      model_cooldown_s=DEFAULT_MODEL_COOLDOWN_S):
    """
    Evaluates a single job dict and updates the database.
    Returns parsed result dict or None on error.
    """
    job_details = f"Job Title: {job.get('title', '')}\nCompany: {job.get('company', '')}\n\n"
    pos_kws = job.get('keywords') or ""
    neg_kws = job.get('negative_keywords') or ""
    if pos_kws:
        job_details += f"Matched Positive Keywords: {pos_kws}\n"
    if neg_kws:
        job_details += f"Matched Negative Keywords: {neg_kws}\n"
    pos_desc = job.get('description_tags') or ""
    neg_desc = job.get('neg_description_tags') or ""
    if pos_desc:
        job_details += f"Matched Positive Description Tags: {pos_desc}\n"
    if neg_desc:
        job_details += f"Matched Negative Description Tags: {neg_desc}\n"
    job_details += f"\nJob Description:\n{job.get('description', '')}"
    
    prompt = [job_details] + gemini_cvs
    
    res_text = _call_gemini(
        api_key,
        model_names,
        instruction_text,
        prompt,
        log_queue,
        model_cooldown_s,
    )
    data = _parse_response(res_text)
    
    score = max(0, min(100, int(data.get("eval_score", 0))))
    reason = data.get("eval_reason", "No reason provided.")
    selected_cv = data.get("selected_cv", "")
    cover_letter = data.get("cover_letter", "")
    
    database.update_job_eval(job['link'], score, reason, selected_cv, cover_letter)
    emit_log(f"  -> Score: {score}/100 | Best CV: {selected_cv or 'None'} | Job: {job.get('title', '')[:40]}", log_queue)
    
    # Broadcast a structured event for frontend real-time update. JSON avoids
    # delimiter bugs when URLs contain ':' (for example https://... or query
    # strings) and carries the already-persisted evaluation fields directly.
    eval_event = {
        "link": job["link"],
        "eval_score": score,
        "eval_reason": reason,
        "selected_cv": selected_cv,
        "cover_letter": cover_letter,
    }
    emit_log(
        "EVAL_UPDATE:" + json.dumps(eval_event, ensure_ascii=False, separators=(",", ":")),
        log_queue,
    )
    
    return {
        "link": job['link'],
        "eval_score": score,
        "eval_reason": reason,
        "selected_cv": selected_cv,
        "cover_letter": cover_letter
    }

def main_loop(log_queue=None):
    global current_state
    current_state = STATE_RUNNING
    
    emit_log("--- EVALUATOR STARTED ---", log_queue)
    
    if not GENAI_AVAILABLE:
        emit_log("[!] Gemini SDK not installed. Install with: pip install google-genai", log_queue)
        current_state = STATE_STOPPED
        return
    
    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        emit_log("[!] Gemini API key not set in config.yml. Evaluator stopping.", log_queue)
        current_state = STATE_STOPPED
        return
        
    model_names = get_model_priority(config)
    emit_log(f"Gemini model priority: {' -> '.join(model_names)}", log_queue)
    model_cooldown_s = get_model_cooldown_s(config)
    emit_log(f"Unavailable-model cooldown: {model_cooldown_s:.0f}s", log_queue)
    delay_s = max(1, config.get("evaluator_delay_s", 5))
    cv_paths = config.get("cv_paths", [])
    evaluator_min_score = config.get("evaluator_min_score", 5)
    instruction_text = load_instruction()

    if cv_paths:
        gemini_cvs = get_uploaded_cvs(cv_paths, log_queue)
    else:
        emit_log("[!] No CVs configured in config.yml. Evaluation will run without CVs.", log_queue)
        gemini_cvs = []
    
    while current_state == STATE_RUNNING:
        if not check_state(log_queue):
            break
            
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("""
                SELECT * FROM jobs 
                WHERE status IN ('Unseen', 'Later') 
                  AND (eval_score IS NULL OR eval_reason IS NULL OR eval_reason = '' OR eval_reason LIKE 'Error%')
                  AND (eval_reason IS NULL OR eval_reason NOT LIKE 'Below threshold%')
                ORDER BY discovered_at DESC
            """)
            jobs_to_evaluate = [dict(row) for row in c.fetchall()]
            conn.close()
            
            if not jobs_to_evaluate:
                time.sleep(10)
                continue
                
            emit_log(f"Found {len(jobs_to_evaluate)} unseen/later jobs to evaluate...", log_queue)
            
            for job in jobs_to_evaluate:
                if not check_state(log_queue):
                    break

                kw_score = job.get('keyword_score') or 0
                if kw_score < evaluator_min_score:
                    emit_log(f"  [⏸] Skipped (kw_score={kw_score} < {evaluator_min_score}): {job.get('title', '')}", log_queue)
                    # Mark with a placeholder so it doesn't get re-queued each loop
                    database.update_job_eval(job['link'], None, f"Below threshold (kw_score={kw_score})")
                    continue

                
                try:
                    evaluate_job_data(
                        job,
                        api_key,
                        model_names,
                        instruction_text,
                        gemini_cvs,
                        log_queue,
                        model_cooldown_s,
                    )
                except Exception as e:
                    emit_log(f"[!] Evaluation failed for '{job.get('title', '')}': {e}", log_queue)
                    if "429" in str(e) or "quota" in str(e).lower():
                        emit_log("[!] Rate limit hit. Sleeping 30s before continuing...", log_queue)
                        time.sleep(30)
                    else:
                        time.sleep(2)
                        
                emit_log(f"Cooldown: Waiting {delay_s}s for rate limits...", log_queue)
                time.sleep(delay_s)
                
        except Exception as e:
            emit_log(f"[!] Evaluator loop error: {e}", log_queue)
            traceback.print_exc()
            time.sleep(10)

    if log_queue is not None:
        try:
            log_queue.put("DONE")
        except Exception:
            pass

def evaluate_job_by_link(link, log_queue=None):
    """
    Manually evaluates a single job by link. Returns dict with eval results or None.
    """
    if not GENAI_AVAILABLE:
        emit_log("[!] Gemini SDK not installed.", log_queue)
        return None

    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        emit_log("[!] Gemini API key not set.", log_queue)
        return None

    model_names = get_model_priority(config)
    emit_log(f"Gemini model priority: {' -> '.join(model_names)}", log_queue)
    model_cooldown_s = get_model_cooldown_s(config)
    instruction_text = load_instruction()
    cv_paths = config.get("cv_paths", [])
    gemini_cvs = get_uploaded_cvs(cv_paths, log_queue) if cv_paths else []

    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE link = ?", (link,))
    job_row = c.fetchone()
    conn.close()
    if not job_row:
        emit_log(f"[!] Job not found in database for link: {link}", log_queue)
        return None

    job = dict(job_row)
    emit_log(f"\nManually Evaluating: {job.get('title', '')} ({job.get('company', '')})...", log_queue)
    
    try:
        res = evaluate_job_data(
            job,
            api_key,
            model_names,
            instruction_text,
            gemini_cvs,
            log_queue,
            model_cooldown_s,
        )
        return res
    except Exception as e:
        emit_log(f"[!] Manual evaluation failed: {e}", log_queue)
        return None

def run(log_queue=None):
    main_loop(log_queue)

if __name__ == "__main__":
    main_loop()
