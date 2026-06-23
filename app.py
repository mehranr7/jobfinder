from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import database
import scraper
import threading
import queue

import utils

app = Flask(__name__)

@app.template_filter('timeago')
def timeago_filter(dt_string):
    return utils.timeago_filter(dt_string)

@app.route('/')
def index():
    jobs = database.get_all_jobs()
    return render_template('index.html', jobs=jobs)

@app.route('/api/get_job_cards')
def get_job_cards():
    jobs = database.get_all_jobs()
    return render_template('job_cards.html', jobs=jobs)

@app.route('/api/toggle_done', methods=['POST'])
def toggle_done():
    data = request.get_json()
    link = data.get('link')
    is_done = data.get('is_done')
    
    if link is None or is_done is None:
        return jsonify({'error': 'Missing link or is_done'}), 400
        
    database.update_job_status(link, bool(is_done))
    return jsonify({'success': True, 'link': link, 'is_done': bool(is_done)})

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

if __name__ == '__main__':
    # Initialize DB on startup
    database.init_db()
    
    print("\n" + "="*50)
    print("🚀 JOBFINDER SERVER IS RUNNING!")
    print("👉 CLICK HERE TO OPEN: http://localhost:5000")
    print("="*50 + "\n")
    
    # Run the app, accessible externally for Docker
    app.run(host='0.0.0.0', port=5000, debug=False)
