import time
import json
import os
import yaml
import traceback
import database
import google.generativeai as genai

STATE_RUNNING = "RUNNING"
STATE_PAUSED = "PAUSED"
STATE_STOPPED = "STOPPED"
current_state = STATE_RUNNING

# Cache for uploaded Gemini files
uploaded_files_cache = {}

def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

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

import PyPDF2

def get_uploaded_cvs(cv_paths, log_queue=None):
    """
    Extracts text locally from PDF CVs to bypass upload API limits.
    """
    global uploaded_files_cache
    gemini_files = []
    
    for path in cv_paths:
        if not os.path.exists(path):
            emit_log(f"[!] CV file not found: {path}", log_queue)
            continue
            
        # Check cache
        if path in uploaded_files_cache:
            gemini_files.append(f"--- CV: {path} ---\n" + uploaded_files_cache[path])
            continue
            
        emit_log(f"Extracting text from {path} locally...", log_queue)
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

def main_loop(log_queue=None):
    global current_state
    current_state = STATE_RUNNING
    
    emit_log("--- EVALUATOR STARTED ---", log_queue)
    
    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        emit_log("[!] Gemini API key not set in config.yml. Evaluator stopping.", log_queue)
        current_state = STATE_STOPPED
        return
        
    genai.configure(api_key=api_key)
    
    model_name = config.get("evaluator_model", "gemini-1.5-flash")
    delay_s = config.get("evaluator_delay_s", 5)
    cv_paths = config.get("cv_paths", [])
    
    # Ensure instruction file exists
    if not os.path.exists("llm_instruction.txt"):
        with open("llm_instruction.txt", "w", encoding="utf-8") as f:
            f.write('You are an expert HR recruiter evaluating a job match. Analyze the job description against my CVs. Return JSON with "eval_score" (0-100) and "eval_reason" (1-3 sentences).')
            
    with open("llm_instruction.txt", "r", encoding="utf-8") as f:
        instruction_text = f.read()

    # Upload CVs
    if cv_paths:
        gemini_cvs = get_uploaded_cvs(cv_paths, log_queue)
    else:
        emit_log("[!] No CVs configured in config.yml. Evaluation will run without CVs.", log_queue)
        gemini_cvs = []

    # Initialize Model with JSON enforcement
    model = genai.GenerativeModel(
        model_name,
        system_instruction=instruction_text,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 8192
        }
    )
    
    while current_state == STATE_RUNNING:
        if not check_state(log_queue):
            break
            
        try:
            # Fetch unevaluated unseen jobs
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM jobs WHERE status = 'Unseen' AND (eval_score IS NULL OR eval_reason IS NULL) ORDER BY discovered_at DESC")
            jobs_to_evaluate = [dict(row) for row in c.fetchall()]
            conn.close()
            
            if not jobs_to_evaluate:
                # No jobs, sleep and poll again
                time.sleep(10)
                continue
                
            for job in jobs_to_evaluate:
                if not check_state(log_queue):
                    break
                    
                emit_log(f"\nEvaluating: {job['title']}...", log_queue)
                
                # Build prompt
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
                
                prompt = [job_details]
                # Append CV files to prompt
                prompt.extend(gemini_cvs)
                
                try:
                    response = model.generate_content(prompt)
                    res_text = response.text.strip()
                    
                    # Parse JSON and strip markdown backticks
                    res_text = response.text.strip()
                    if res_text.startswith("```json"):
                        res_text = res_text[7:]
                    elif res_text.startswith("```"):
                        res_text = res_text[3:]
                        
                    if res_text.endswith("```"):
                        res_text = res_text[:-3]
                        
                    res_text = res_text.strip()
                    
                    # Defensively fix truncated JSON (missing closing braces)
                    if not res_text.endswith("}"):
                        if not res_text.endswith('"'):
                            res_text += '"'
                        res_text += "\n}"
                        
                    emit_log(f"Gemini raw response: {res_text}", log_queue)
                    
                    try:
                        data = json.loads(res_text)
                    except json.JSONDecodeError:
                        # Fallback: find the JSON block using regex if basic stripping failed
                        import re
                        match = re.search(r'\{.*\}', res_text, re.DOTALL)
                        if match:
                            res_text = match.group(0)
                        data = json.loads(res_text)
                    score = data.get("eval_score", 0)
                    reason = data.get("eval_reason", "No reason provided.")
                    selected_cv = data.get("selected_cv", "")
                    cover_letter = data.get("cover_letter", "")
                    
                    # Ensure score is integer and bounded
                    score = max(0, min(100, int(score)))
                    
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
                        emit_log(f"[!] Rate limit or quota exceeded. Sleeping for 60 seconds before retrying...", log_queue)
                        time.sleep(60)
                        break # Break inner loop, fetch jobs again after sleep
                # Rate limit cooldown
                emit_log(f"Cooldown: Waiting {delay_s}s for rate limits...", log_queue)
                time.sleep(delay_s)
                
        except Exception as e:
            emit_log(f"[!] Evaluator loop error: {e}", log_queue)
            traceback.print_exc()
            time.sleep(10)

    if log_queue is not None:
        log_queue.put("DONE")

def evaluate_job_by_link(link, log_queue=None):
    config = load_config()
    api_key = config.get("gemini_api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        emit_log("[!] Gemini API key not set.", log_queue)
        return False
    genai.configure(api_key=api_key)
    model_name = config.get("evaluator_model", "gemini-1.5-flash")
    if not os.path.exists("llm_instruction.txt"):
        with open("llm_instruction.txt", "w", encoding="utf-8") as f:
            f.write('You are an expert HR recruiter evaluating a job match. Analyze the job description against my CVs. Return JSON with "eval_score" (0-100) and "eval_reason" (1-3 sentences).')
    with open("llm_instruction.txt", "r", encoding="utf-8") as f:
        instruction_text = f.read()
    cv_paths = config.get("cv_paths", [])
    gemini_cvs = get_uploaded_cvs(cv_paths, log_queue) if cv_paths else []
    model = genai.GenerativeModel(
        model_name,
        system_instruction=instruction_text,
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 8192}
    )
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
    
    prompt = [job_details]
    prompt.extend(gemini_cvs)
    
    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        elif res_text.startswith("```"):
            res_text = res_text[3:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
        res_text = res_text.strip()
        if not res_text.endswith("}"):
            if not res_text.endswith('"'):
                res_text += '"'
            res_text += "\n}"
            
        import json
        try:
            data = json.loads(res_text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', res_text, re.DOTALL)
            if match:
                res_text = match.group(0)
            data = json.loads(res_text)
            
        score = data.get("eval_score", 0)
        reason = data.get("eval_reason", "No reason provided.")
        selected_cv = data.get("selected_cv", "")
        cover_letter = data.get("cover_letter", "")
        score = max(0, min(100, int(score)))
        
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
