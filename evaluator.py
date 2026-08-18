import time
import json
import os
import re
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

def load_config():
    return utils.load_config()

def emit_log(msg, log_queue=None):
    print(msg)
    if log_queue is not None:
        if hasattr(log_queue, "put"):
            log_queue.put(msg)
        elif callable(log_queue):
            log_queue(msg)

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
                    text += page.extract_text() + "\n"
            uploaded_files_cache[path] = text
            gemini_files.append(f"--- CV: {path} ---\n" + text)
            emit_log(f"  -> Extracted {len(text)} characters", log_queue)
        except Exception as e:
            emit_log(f"[!] Failed to extract {path}: {e}", log_queue)
            
    return gemini_files

def _parse_response(res_text):
    """Parse JSON from Gemini response text, stripping markdown fences."""
    if res_text.startswith("```json"):
        res_text = res_text[7:]
    elif res_text.startswith("```"):
        res_text = res_text[3:]
    if res_text.endswith("```"):
        res_text = res_text[:-3]
    res_text = res_text.strip()
    
    # Defensively fix truncated JSON
    if not res_text.endswith("}"):
        if not res_text.endswith('"'):
            res_text += '"'
        res_text += "\n}"
    
    try:
        return json.loads(res_text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

def _call_gemini(api_key, model_name, instruction_text, prompt_parts):
    """
    Calls the Gemini API using whichever SDK version is available.
    Returns the response text.
    """
    # Try new google-genai SDK first
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
    
    # Fallback: legacy google.generativeai SDK
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
        
    model_name = config.get("evaluator_model", "gemini-2.5-flash")
    delay_s = config.get("evaluator_delay_s", 5)
    cv_paths = config.get("cv_paths", [])
    
    # Ensure instruction file exists
    if not os.path.exists("llm_instruction.txt"):
        with open("llm_instruction.txt", "w", encoding="utf-8") as f:
            f.write('You are an expert HR recruiter evaluating a job match. Analyze the job description against my CVs. Return JSON with "eval_score" (0-100) and "eval_reason" (1-3 sentences).')
            
    with open("llm_instruction.txt", "r", encoding="utf-8") as f:
        instruction_text = f.read()

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
            c.execute("SELECT * FROM jobs WHERE status IN ('Unseen', 'Later') AND (eval_score IS NULL OR eval_reason IS NULL) ORDER BY discovered_at DESC")
            jobs_to_evaluate = [dict(row) for row in c.fetchall()]
            conn.close()
            
            if not jobs_to_evaluate:
                time.sleep(10)
                continue
                
            for job in jobs_to_evaluate:
                if not check_state(log_queue):
                    break
                    
                emit_log(f"\nEvaluating: {job['title']}...", log_queue)
                
                job_details = f"Job Title: {job['title']}\nCompany: {job['company']}\n\n"
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
                job_details += f"\nJob Description:\n{job['description']}"
                
                prompt = [job_details] + gemini_cvs
                
                try:
                    res_text = _call_gemini(api_key, model_name, instruction_text, prompt)
                    emit_log(f"Gemini raw response: {res_text}", log_queue)
                    
                    data = _parse_response(res_text)
                    score = max(0, min(100, int(data.get("eval_score", 0))))
                    reason = data.get("eval_reason", "No reason provided.")
                    selected_cv = data.get("selected_cv", "")
                    cover_letter = data.get("cover_letter", "")
                    
                    database.update_job_eval(job['link'], score, reason, selected_cv, cover_letter)
                    emit_log(f"  -> Score: {score}/100, Best CV: {selected_cv}", log_queue)
                    if cover_letter:
                        emit_log(f"  -> Generated Cover Letter!", log_queue)
                    
                except json.JSONDecodeError:
                    emit_log(f"[!] Error: Gemini did not return valid JSON.", log_queue)
                    database.update_job_eval(job['link'], 0, "Error: Invalid JSON response from Gemini.")
                except Exception as e:
                    emit_log(f"[!] Evaluation failed: {e}", log_queue)
                    if "429" in str(e) or "Quota" in str(e):
                        emit_log(f"[!] Rate limit exceeded. Sleeping 60s before retrying...", log_queue)
                        time.sleep(60)
                        break
                        
                emit_log(f"Cooldown: Waiting {delay_s}s for rate limits...", log_queue)
                time.sleep(delay_s)
                
        except Exception as e:
            emit_log(f"[!] Evaluator loop error: {e}", log_queue)
            traceback.print_exc()
            time.sleep(10)

    if log_queue is not None:
        log_queue.put("DONE")

def evaluate_job_by_link(link, log_queue=None):
    if not GENAI_AVAILABLE:
        emit_log("[!] Gemini SDK not installed.", log_queue)
        return False

    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        emit_log("[!] Gemini API key not set.", log_queue)
        return False

    model_name = config.get("evaluator_model", "gemini-2.5-flash")

    if not os.path.exists("llm_instruction.txt"):
        with open("llm_instruction.txt", "w", encoding="utf-8") as f:
            f.write('You are an expert HR recruiter evaluating a job match. Analyze the job description against my CVs. Return JSON with "eval_score" (0-100) and "eval_reason" (1-3 sentences).')
    with open("llm_instruction.txt", "r", encoding="utf-8") as f:
        instruction_text = f.read()

    cv_paths = config.get("cv_paths", [])
    gemini_cvs = get_uploaded_cvs(cv_paths, log_queue) if cv_paths else []

    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE link = ?", (link,))
    job_row = c.fetchone()
    conn.close()
    if not job_row:
        return False

    job = dict(job_row)
    emit_log(f"\nManually Evaluating: {job['title']}...", log_queue)
    
    job_details = f"Job Title: {job['title']}\nCompany: {job['company']}\n\n"
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
    job_details += f"\nJob Description:\n{job['description']}"
    
    prompt = [job_details] + gemini_cvs
    
    try:
        res_text = _call_gemini(api_key, model_name, instruction_text, prompt)
        data = _parse_response(res_text)
        score = max(0, min(100, int(data.get("eval_score", 0))))
        reason = data.get("eval_reason", "No reason provided.")
        selected_cv = data.get("selected_cv", "")
        cover_letter = data.get("cover_letter", "")
        
        database.update_job_eval(job['link'], score, reason, selected_cv, cover_letter)
        emit_log(f"  -> Score: {score}/100, Best CV: {selected_cv}", log_queue)
        return True
    except Exception as e:
        emit_log(f"[!] Manual evaluation failed: {e}", log_queue)
        return False

def run(log_queue=None):
    main_loop(log_queue)

if __name__ == "__main__":
    main_loop()
