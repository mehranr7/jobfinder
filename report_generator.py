from datetime import datetime

class ReportGenerator:
    def __init__(self, template_path="report_template.html", output_path="results.html"):
        self.template_path = template_path
        self.output_path = output_path

    def generate(self, jobs, quiet=False):
        """
        Generates a static HTML report from the scraped jobs list.
        It reads 'report_template.html' and injects the job cards dynamically.
        """
        try:
            with open(self.template_path, "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            if not quiet:
                print(f"Template {self.template_path} not found.")
            return
            
        jobs_html = '<div class="jobs-container">\n'
        for i, job in enumerate(jobs):
            # Support both dict and JobOffer objects during transition
            job_dict = job if isinstance(job, dict) else job.to_dict()
            
            escaped_desc = job_dict['description'].replace('<', '&lt;').replace('>', '&gt;')
            jobs_html += f"""
            <div class="job-card" data-title="{job_dict['title'].lower()}" data-keyword="{job_dict['keyword'].lower()}" data-url="{job_dict['link']}" data-index="{i}">
                <h2 class="job-title">{job_dict['title']}</h2>
                <div class="job-meta">
                    <span><strong>Date:</strong> {job_dict['date']}</span> | 
                    <span><strong>Keyword:</strong> <span class="keyword-badge">{job_dict['keyword']}</span></span> | 
                    <span><strong>Link:</strong> <a href="{job_dict['link']}" target="_blank">{job_dict['link']}</a></span>
                </div>
                <div class="desc-header">
                    <strong>Description:</strong>
                    <div>
                        <button class="done-btn" onclick="toggleDone(this)">✓ Mark as Done</button>
                        <button class="copy-btn" onclick="copyToClipboard('desc-{i}', this)">Copy</button>
                    </div>
                </div>
                <div class="job-description" id="desc-{i}">{escaped_desc}</div>
            </div>
            """
        jobs_html += '</div>'
            
        html = template.replace("{{timestamp}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        html = html.replace("{{jobs_html}}", jobs_html)
        
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        if not quiet:
            print(f"\n--- SUCCESS ---")
            print(f"Report generated: {self.output_path} with {len(jobs)} jobs.")
