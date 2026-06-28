from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import database
import scraper
import threading
import queue

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

@app.route('/')
def index():
    jobs = database.get_all_jobs()
    threshold = get_special_threshold()
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        page_size = config.get("page_size", 20)
    except Exception:
        page_size = 20
    return render_template('index.html', jobs=jobs, special_threshold=threshold, page_size=page_size)

@app.route('/api/get_job_cards')
def get_job_cards():
    jobs = database.get_all_jobs()
    threshold = get_special_threshold()
    return render_template('job_cards.html', jobs=jobs, special_threshold=threshold)

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

def get_port():
    try:
        with open("config.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("port", 5050)
    except Exception:
        return 5050

if __name__ == '__main__':
    # Initialize DB on startup
    database.init_db()
    
    port = get_port()
    print("\n" + "="*50)
    print("🚀 JOBFINDER SERVER IS RUNNING!")
    print(f"👉 CLICK HERE TO OPEN: http://localhost:{port}")
    print("="*50 + "\n")
    
    # Run the app, accessible externally for Docker (binds to both IPv4 and IPv6)
    app.run(host='::', port=port, debug=False)
