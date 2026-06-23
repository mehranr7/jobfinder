from flask import Flask, render_template, request, jsonify, Response
import database
import scraper
import threading
import queue

app = Flask(__name__)

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
    database.init_db()
    print("Starting JobFinder UI. Open http://localhost:5000 in your browser.")
    app.run(debug=False, host='0.0.0.0', port=5000)
