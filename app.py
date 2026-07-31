from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import database
import scraper
import threading
import queue
import csv
import io
import re
import json

import utils

import yaml

app = Flask(__name__)

def get_special_threshold():
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("special_keyword_threshold", 3)
    except Exception:
        return 3

@app.template_filter('timeago')
def timeago_filter(dt_string):
    return utils.timeago_filter(dt_string)

def get_config_options():
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        app_states = config.get("app_states", ["Not Applied", "Applied", "Rejected", "Interview", "Offer"])
        cv_types = config.get("cv_types", ["Software", "Hardware", "Data", "General"])
        page_size = config.get("page_size", 20)
        return app_states, cv_types, page_size
    except Exception:
        return ["Not Applied", "Applied", "Rejected", "Interview", "Offer"], ["Software", "Hardware", "Data", "General"], 20

@app.route('/')
def index():
    jobs = database.get_all_jobs()
    threshold = get_special_threshold()
    app_states, cv_types, page_size = get_config_options()
    return render_template('index.html', jobs=jobs, special_threshold=threshold, page_size=page_size, app_states=app_states, cv_types=cv_types)

@app.route('/api/get_job_cards')
def get_job_cards():
    jobs = database.get_all_jobs()
    threshold = get_special_threshold()
    app_states, cv_types, _ = get_config_options()
    return render_template('job_cards.html', jobs=jobs, special_threshold=threshold, app_states=app_states, cv_types=cv_types)

@app.route('/api/change_status', methods=['POST'])
def change_status():
    data = request.get_json()
    link = data.get('link')
    status = data.get('status')
    
    if link is None or status is None:
        return jsonify({'error': 'Missing link or status'}), 400
        
    database.update_job_status(link, status)
    return jsonify({'success': True, 'link': link, 'status': status})

@app.route('/api/change_cv', methods=['POST'])
def change_cv():
    data = request.get_json()
    link = data.get('link')
    cv_type = data.get('cv_type')
    
    if link is None or cv_type is None:
        return jsonify({'error': 'Missing link or cv_type'}), 400
        
    database.update_job_cv_type(link, cv_type)
    return jsonify({'success': True, 'link': link, 'cv_type': cv_type})

@app.route('/api/change_app_state', methods=['POST'])
def change_app_state():
    data = request.get_json()
    link = data.get('link')
    app_state = data.get('app_state')
    
    if link is None or app_state is None:
        return jsonify({'error': 'Missing link or app_state'}), 400
        
    database.update_job_app_state(link, app_state)
    return jsonify({'success': True, 'link': link, 'app_state': app_state})

@app.route('/api/save_note', methods=['POST'])
def save_note():
    data = request.get_json()
    link = data.get('link')
    note = data.get('note')
    
    if link is None or note is None:
        return jsonify({'error': 'Missing link or note'}), 400
        
    database.update_job_note(link, note)
    return jsonify({'success': True, 'link': link, 'note': note})

@app.route('/api/delete_job', methods=['POST'])
def delete_job():
    data = request.get_json()
    link = data.get('link')
    
    if not link:
        return jsonify({'error': 'Missing link'}), 400
        
    database.delete_job(link)
    return jsonify({'success': True, 'link': link})

@app.route('/api/update_tags', methods=['GET'])
def update_tags():
    def generate():
        try:
            scraper.load_config()
            keywords = scraper.KEYWORDS
            negative_keywords = scraper.NEGATIVE_KEYWORDS
            
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT link, title, description FROM jobs")
            jobs = [dict(row) for row in c.fetchall()]
            conn.close()
            
            total = len(jobs)
            for i, job in enumerate(jobs):
                title = job['title']
                desc = job['description'] or ""
                
                matched_kws = []
                for kw in keywords:
                    if re.search(re.escape(kw), title, re.IGNORECASE):
                        matched_kws.append(kw)
                
                matched_neg_kws = []
                for nkw in negative_keywords:
                    if re.search(re.escape(nkw), title, re.IGNORECASE):
                        matched_neg_kws.append(nkw)
                
                desc_tags = []
                for kw in keywords:
                    if re.search(re.escape(kw), desc, re.IGNORECASE):
                        desc_tags.append(kw)
                seen = set()
                unique_tags = [x for x in desc_tags if not (x in seen or seen.add(x))]
                
                neg_desc_tags = []
                for nkw in negative_keywords:
                    if re.search(re.escape(nkw), desc, re.IGNORECASE):
                        neg_desc_tags.append(nkw)
                seen_neg = set()
                unique_neg_tags = [x for x in neg_desc_tags if not (x in seen_neg or seen_neg.add(x))]
                
                database.update_job_tags(
                    job['link'],
                    ", ".join(matched_kws),
                    ", ".join(matched_neg_kws),
                    ", ".join(unique_tags),
                    ", ".join(unique_neg_tags)
                )
                
                if i % 10 == 0:
                    yield f"data: {json.dumps({'progress': i, 'total': total, 'success': False})}\n\n"
                    
            yield f"data: {json.dumps({'progress': total, 'total': total, 'success': True})}\n\n"
            yield "event: close\ndata: \n\n"
        except Exception as e:
            print(f"Error updating tags: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "event: close\ndata: \n\n"
            
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/export_csv', methods=['POST'])
def export_csv():
    data = request.get_json()
    links = data.get('links', [])
    
    if not links:
        return jsonify({'error': 'No links provided'}), 400
        
    jobs = database.get_jobs_by_links(links)
    
    # Create CSV in memory
    si = io.StringIO()
    # Define columns
    fieldnames = [
        'title', 'company', 'platform', 'status', 'app_state', 'cv_type', 'note',
        'eval_score', 'eval_reason', 'selected_cv', 'cover_letter',
        'keywords', 'negative_keywords', 'description_tags', 'neg_description_tags',
        'date_of_release', 'discovered_at', 'link', 'description'
    ]
    
    writer = csv.DictWriter(si, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for job in jobs:
        # Sanitize fields with newlines to prevent Excel/Numbers from cutting rows
        sanitized_job = {}
        for k, v in job.items():
            if isinstance(v, str):
                sanitized_job[k] = v.replace('\r\n', '  ').replace('\n', '  ').replace('\r', '  ')
            else:
                sanitized_job[k] = v
        writer.writerow(sanitized_job)
        
    # Prepend UTF-8 BOM so Excel opens it correctly with all German characters
    output = '\ufeff' + si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment;filename=JobFinder_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@app.route('/api/run_scraper')
def run_scraper():
    def generate():
        q = queue.Queue()
        thread = threading.Thread(target=scraper.main, args=(q,))
        thread.start()
        
        while thread.is_alive() or not q.empty():
            try:
                # Wait for up to 1 second for a new message
                msg = q.get(timeout=1.0)
                # Print to terminal so it's visible in docker logs
                print(msg, flush=True)
                # Replace newlines with <br> for HTML rendering
                formatted_msg = msg.replace('\n', '<br>')
                yield f"data: {formatted_msg}\n\n"
            except queue.Empty:
                pass
                
        # Send a final termination event
        yield "event: close\ndata: \n\n"
        
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/pause_scraper', methods=['POST'])
def pause_scraper():
    scraper.current_state = scraper.STATE_PAUSED
    return jsonify({"success": True})

@app.route('/api/resume_scraper', methods=['POST'])
def resume_scraper():
    scraper.current_state = scraper.STATE_RUNNING
    return jsonify({"success": True})

@app.route('/api/stop_scraper', methods=['POST'])
def stop_scraper():
    scraper.current_state = scraper.STATE_STOPPED
    return jsonify({"success": True})

@app.route('/api/get_evaluator_state', methods=['GET'])
def get_evaluator_state():
    return jsonify({"state": evaluator.current_state})

@app.route('/api/toggle_evaluator', methods=['POST'])
def toggle_evaluator():
    if evaluator.current_state == evaluator.STATE_PAUSED:
        evaluator.current_state = evaluator.STATE_RUNNING
    else:
        evaluator.current_state = evaluator.STATE_PAUSED
    return jsonify({"success": True, "state": evaluator.current_state})

@app.route('/api/evaluate_job', methods=['POST'])
def evaluate_job():
    data = request.get_json()
    link = data.get('link')
    if not link:
        return jsonify({'error': 'Missing link'}), 400
    
    # Run evaluation asynchronously so we don't block the UI
    def run_eval():
        evaluator.evaluate_job_by_link(link, broadcast_eval_log)
        # We don't notify the UI directly here to refresh, but the eval terminal stream
        # will print "-> Score: " which triggers a UI refresh anyway!
        
    threading.Thread(target=run_eval).start()
    return jsonify({'success': True})

# --- EVALUATOR API ---

# Global queue for SSE, cleared periodically or capped
evaluator_log_queues = []

def broadcast_eval_log(msg):
    print(msg, flush=True)
    # Send to all connected UI clients
    dead_queues = []
    for q in evaluator_log_queues:
        try:
            q.put_nowait(msg)
        except queue.Full:
            dead_queues.append(q)
    for q in dead_queues:
        if q in evaluator_log_queues:
            evaluator_log_queues.remove(q)

@app.route('/api/eval_stream')
def eval_stream():
    def generate():
        q = queue.Queue(maxsize=100)
        evaluator_log_queues.append(q)
        try:
            while True:
                msg = q.get()
                formatted_msg = msg.replace('\n', '<br>')
                yield f"data: {formatted_msg}\n\n"
        except GeneratorExit:
            if q in evaluator_log_queues:
                evaluator_log_queues.remove(q)
    return Response(generate(), mimetype='text/event-stream')

def get_port():
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("port", 5050)
    except Exception:
        return 5050

import evaluator

if __name__ == '__main__':
    # Initialize DB on startup
    database.init_db()
    
    # Start Evaluator Daemon
    eval_thread = threading.Thread(target=evaluator.main_loop, args=(broadcast_eval_log,), daemon=True)
    eval_thread.start()
    
    port = get_port()
    print("\n" + "="*50)
    print("🚀 JOBFINDER SERVER IS RUNNING!")
    print(f"👉 CLICK HERE TO OPEN: http://localhost:{port}")
    print("="*50 + "\n")
    
    # Run the app, accessible externally for Docker (binds to both IPv4 and IPv6)
    app.run(host='::', port=port, debug=False)
