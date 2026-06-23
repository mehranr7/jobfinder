from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import database
import scraper
import threading
import queue

app = Flask(__name__)

@app.template_filter('timeago')
def timeago_filter(dt_string):
    if not dt_string:
        return "Unbekannt"
        
    try:
        dt = datetime.fromisoformat(dt_string)
    except ValueError:
        return dt_string
        
    now = datetime.now()
    diff = now - dt
    
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Gerade eben"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"vor {minutes} Minute{'n' if minutes != 1 else ''}"
        
    hours = minutes // 60
    if hours < 24:
        return f"vor {hours} Stunde{'n' if hours != 1 else ''}"
        
    days = hours // 24
    if days < 7:
        if days == 1:
            return "Gestern"
        return f"vor {days} Tag{'en' if days != 1 else ''}"
        
    weeks = days // 7
    if weeks < 4:
        return f"vor {weeks} Woche{'n' if weeks != 1 else ''}"
        
    months = days // 30
    return f"vor {months} Monat{'en' if months != 1 else ''}"

@app.route('/')
def index():
    jobs = database.get_all_jobs()
    return render_template('index.html', jobs=jobs)

@app.route('/api/toggle_done', methods=['POST'])
def toggle_done():
    data = request.get_json()
    link = data.get('link')
    is_done = data.get('is_done')
    
    if link is None or is_done is None:
        return jsonify({'error': 'Missing link or is_done'}), 400
        
    database.update_job_status(link, bool(is_done))
    return jsonify({'success': True, 'link': link, 'is_done': bool(is_done)})

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
                # Replace newlines with <br> for HTML rendering, or just send plain text
                # We will send plain text and let the frontend format it
                formatted_msg = msg.replace('\n', '<br>')
                yield f"data: {formatted_msg}\n\n"
            except queue.Empty:
                pass
                
        # Send a final termination event
        yield "event: close\ndata: \n\n"
        
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Initialize DB on startup
    database.init_db()
    
    print("\n" + "="*50)
    print("🚀 JOBFINDER SERVER IS RUNNING!")
    print("👉 CLICK HERE TO OPEN: http://localhost:5000")
    print("="*50 + "\n")
    
    # Run the app, accessible externally for Docker
    app.run(host='0.0.0.0', port=5000, debug=False)
