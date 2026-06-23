from flask import Flask, render_template, request, jsonify
import database

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

if __name__ == '__main__':
    database.init_db()
    print("Starting JobFinder UI. Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True, host='127.0.0.1', port=5000)
