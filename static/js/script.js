// ── Utility helpers ─────────────────────────────────────────────────────────

function toggleDescription(elementId, btn) {
    const desc = document.getElementById(elementId);
    if (desc.style.display === 'none' || desc.style.display === '') {
        desc.style.display = 'block';
        btn.innerText = '🔼';
    } else {
        desc.style.display = 'none';
        btn.innerText = '🔽';
    }
}

function copyToClipboard(elementId, btn) {
    const el = document.getElementById(elementId);
    const originalDisplay = el.style.display;
    if (originalDisplay === 'none' || originalDisplay === '') el.style.display = 'block';
    const text = el.innerText;
    if (originalDisplay === 'none' || originalDisplay === '') el.style.display = 'none';
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerText;
        btn.innerText = "✅";
        setTimeout(() => btn.innerText = originalText, 2000);
    }).catch(err => console.error('Failed to copy: ', err));
}

function timeago(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    const diff = Math.floor((Date.now() - d) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return d.toLocaleDateString('de-DE');
}

function esc(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Status change ────────────────────────────────────────────────────────────

const STATUS_EMOJI_MAP = { Unseen: '🆕', Later: '⏳', Issue: '⚠️', Skipped: '❌', Applied: '✅', Interview: '🎯' };

function changeStatus(btn, link, newStatus) {
    const card = btn.closest('.job-card');
    if (btn.disabled) return;
    const originalText = btn.innerText;
    btn.innerText = "…";
    btn.disabled = true;

    fetch('/api/change_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link, status: newStatus })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const group = btn.closest('.status-btn-group');
            if (group) group.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            card.setAttribute('data-status', newStatus);
            card.className = card.className.replace(/\bstatus-[a-z]+\b/g, '').trim();
            card.classList.add('status-' + newStatus.toLowerCase());
            btn.innerText = STATUS_EMOJI_MAP[newStatus] || originalText;
            btn.disabled = false;
            // Update tab counts
            refreshStatusCounts();
            // If status filter is active and card no longer matches, remove it from DOM
            if (state.status && state.status !== newStatus) {
                card.remove();
                state.totalCount = Math.max(0, state.totalCount - 1);
                updateCountDisplay();
            }
        } else {
            alert("Failed to update status.");
            btn.innerText = originalText;
            btn.disabled = false;
        }
    })
    .catch(() => {
        alert("Failed to update status due to network error.");
        btn.innerText = originalText;
        btn.disabled = false;
    });
}

function changeCvType(selectElement, link) {
    const cvType = selectElement.value;
    if (!cvType) return; // Do nothing if empty/placeholder selected
    const card = selectElement.closest('.job-card');
    selectElement.disabled = true;
    fetch('/api/change_cv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link, cv_type: cvType })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Flash success color on the select
            selectElement.style.outline = '2px solid var(--success)';
            setTimeout(() => { selectElement.style.outline = ''; }, 1800);
            // Update the CV label badge in the card if present
            const cvLabel = card ? card.querySelector('.cv-badge-label') : null;
            if (cvLabel) cvLabel.textContent = '📄 ' + cvType;
        } else { alert("Failed to update CV."); }
        selectElement.disabled = false;
    })
    .catch(() => { alert("Failed to update CV due to network error."); selectElement.disabled = false; });
}

// ── Notes modal ──────────────────────────────────────────────────────────────

function openNoteModal(link) {
    const noteBtn = document.querySelector(`button[data-note-link="${link}"]`);
    const noteText = noteBtn ? noteBtn.getAttribute('data-note') : '';
    document.getElementById('noteJobLink').value = link;
    document.getElementById('noteTextarea').value = noteText;
    document.getElementById('noteModal').style.display = 'flex';
}

function closeNoteModal() {
    document.getElementById("noteModal").style.display = "none";
    document.getElementById("noteTextarea").value = "";
    document.getElementById("noteJobLink").value = "";
}

function openEvalModal(reason) {
    document.getElementById("evalReasonText").innerText = reason || "No reasoning provided by Gemini.";
    document.getElementById("evalModal").style.display = "flex";
}

function copyCoverLetterDirectly(btn) {
    if (btn.disabled) return;
    let letter = btn.getAttribute('data-letter') || "";
    letter = letter.replace(/\\n/g, '\n');
    navigator.clipboard.writeText(letter).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = "✅ Copied!";
        btn.disabled = true;
        setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
    }).catch(() => alert("Failed to copy Cover Letter to clipboard."));
}

function copyCoverLetter() {
    const ta = document.getElementById('coverLetterTextarea');
    navigator.clipboard.writeText(ta.value);
}

function saveNote() {
    const link = document.getElementById('noteJobLink').value;
    const note = document.getElementById('noteTextarea').value;
    fetch('/api/save_note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link, note })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const noteBtn = document.querySelector(`button[data-note-link="${link}"]`);
            if (noteBtn) {
                noteBtn.setAttribute('data-note', note);
                noteBtn.style.color = 'var(--success)';
                setTimeout(() => noteBtn.style.color = '', 2000);
            }
            closeNoteModal();
        } else { alert("Failed to save note."); }
    })
    .catch(() => alert("Failed to save note due to network error."));
}

function deleteJob(btn, link) {
    if (!confirm("Are you sure you want to permanently delete this job offer?")) return;
    const card = btn.closest('.job-card');
    btn.disabled = true;
    btn.innerText = "⏳";
    fetch('/api/delete_job', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            card.style.transition = 'opacity 0.3s, transform 0.3s';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            setTimeout(() => {
                card.remove();
                state.totalCount = Math.max(0, state.totalCount - 1);
                updateCountDisplay();
            }, 300);
        } else {
            alert("Failed to delete job.");
            btn.innerText = "🗑️";
            btn.disabled = false;
        }
    })
    .catch(() => { alert("Failed to delete job due to network error."); btn.innerText = "🗑️"; btn.disabled = false; });
}

// ── Scraper controls ─────────────────────────────────────────────────────────

function runScraper() {
    const btn = document.getElementById('runScraperBtn');
    const pauseBtn = document.getElementById('pauseScraperBtn');
    const resumeBtn = document.getElementById('resumeScraperBtn');
    const stopBtn = document.getElementById('stopScraperBtn');
    const termOut = document.getElementById('terminalOutput');
    const termWrapper = document.getElementById('terminalOutputWrapper');

    btn.disabled = true;
    btn.style.display = 'none';
    pauseBtn.style.display = 'inline-block';
    resumeBtn.style.display = 'none';
    stopBtn.style.display = 'inline-block';
    termWrapper.style.display = 'block';
    termOut.innerHTML = 'Starting scraper...\n';

    const source = new EventSource('/api/run_scraper');

    function resetButtons() {
        btn.disabled = false;
        btn.innerText = "🚀 Run Scraper";
        btn.style.display = 'inline-block';
        pauseBtn.style.display = 'none';
        resumeBtn.style.display = 'none';
        stopBtn.style.display = 'none';
    }

    source.onmessage = function (event) {
        if (event.data === "DONE") {
            source.close();
            resetButtons();
            termOut.innerHTML += '\nScraper finished.\n';
        } else {
            if (!event.data.includes("-> UI_RELOAD")) {
                termOut.innerHTML += event.data + '\n';
                termWrapper.scrollTop = termWrapper.scrollHeight;
            }
            if (event.data.includes("-> UI_RELOAD")) {
                prependLatestJob();
            }
        }
    };

    source.onerror = function () {
        source.close();
        resetButtons();
        termOut.innerHTML += '\nError connecting to scraper stream.\n';
    };
}

function pauseScraper() {
    fetch('/api/pause_scraper', { method: 'POST' }).then(() => {
        document.getElementById('pauseScraperBtn').style.display = 'none';
        document.getElementById('resumeScraperBtn').style.display = 'inline-block';
    });
}

function resumeScraper() {
    fetch('/api/resume_scraper', { method: 'POST' }).then(() => {
        document.getElementById('resumeScraperBtn').style.display = 'none';
        document.getElementById('pauseScraperBtn').style.display = 'inline-block';
    });
}

function stopScraper() {
    fetch('/api/stop_scraper', { method: 'POST' }).then(() => {
        document.getElementById('pauseScraperBtn').style.display = 'none';
        document.getElementById('resumeScraperBtn').style.display = 'none';
    });
}

function updateTags() {
    const btn = document.getElementById('updateTagsBtn');
    if (!btn || btn.disabled) return;
    const originalText = btn.innerText;
    btn.innerText = "⏳ Updating...";
    btn.disabled = true;
    const progressContainer = document.getElementById('updateProgressContainer');
    const progressBar = document.getElementById('updateProgressBar');
    const progressText = document.getElementById('updateProgressText');
    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.innerText = 'Starting...';

    const source = new EventSource('/api/update_tags');
    source.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            if (data.error) { alert("Failed to update tags: " + data.error); source.close(); resetUI(); return; }
            const pct = data.total > 0 ? (data.progress / data.total) * 100 : 100;
            progressBar.style.width = pct + '%';
            progressText.innerText = `Updating ${data.progress} of ${data.total} jobs...`;
            if (data.success) {
                source.close();
                btn.innerText = "✅ Done!";
                fetchJobs(true);
                setTimeout(resetUI, 2000);
            }
        } catch (e) { console.error("Error parsing progress:", e, event.data); }
    };
    source.onerror = function () { source.close(); alert("Network error while updating tags."); resetUI(); };

    function resetUI() {
        btn.innerText = originalText;
        btn.disabled = false;
        setTimeout(() => { progressContainer.style.display = 'none'; }, 500);
    }
}

function toggleTerminal(wrapperId) {
    const wrapper = document.getElementById(wrapperId);
    wrapper.style.display = wrapper.style.display === "none" ? "block" : "none";
}

// ── Evaluator ────────────────────────────────────────────────────────────────

function buildEvalHtml(job, status) {
    if (typeof EVALUATOR_ENABLED === 'undefined' || !EVALUATOR_ENABLED) return '';
    
    const hasScore = job.eval_score !== '' && job.eval_score !== null && job.eval_score !== undefined;
    const kwScore = (job.keyword_score !== undefined && job.keyword_score !== null && job.keyword_score !== '') ? parseInt(job.keyword_score) : 0;
    const minThreshold = window.EVALUATOR_MIN_SCORE || 5;
    const isBelowThreshold = !hasScore && kwScore < minThreshold;
    
    if (hasScore) {
        const score = parseInt(job.eval_score);
        const evalColor = score >= 70 ? 'green' : (score >= 40 ? 'yellow' : 'red');
        let html = `<span class="eval-badge eval-${evalColor}" data-reason="${esc(job.eval_reason)}" onclick="openEvalModal(this.getAttribute('data-reason'))" title="Click to read AI reasoning">✨ Match: ${score}%</span>`;
        if (job.selected_cv) {
            html += ` <span class="keyword-badge" title="Best CV Match" style="background-color:#34495e;color:white;">📄 ${esc(job.selected_cv)}</span>`;
        }
        if (job.cover_letter) {
            const escapedLetter = esc(job.cover_letter).replace(/\n/g, '\\n');
            html += ` <button class="eval-badge eval-green" style="background:linear-gradient(135deg,#3498db,#2980b9);border:none;font-size:inherit;font-family:inherit;" data-letter="${escapedLetter}" onclick="copyCoverLetterDirectly(this)" title="Click to copy Cover Letter">📋 Cover Letter</button>`;
        }
        html += ` <button class="eval-badge" style="background-color:#9b59b6;color:white;border:none;font-size:inherit;font-family:inherit;margin-left:5px;" onclick="evaluateJob(this,'${esc(job.link)}')" title="Click to re-evaluate this job">🔄 Reevaluate</button>`;
        return html;
    } else if (isBelowThreshold) {
        let html = `<span class="eval-badge eval-below" title="Keyword score (${kwScore}) is below auto-evaluation threshold (${minThreshold})">⏸ Below Threshold</span>`;
        html += ` <button class="eval-badge eval-yellow" style="border:none;font-size:inherit;font-family:inherit;margin-left:5px;" onclick="evaluateJob(this,'${esc(job.link)}')" title="Click to manually evaluate this job with AI">✨ Evaluate</button>`;
        return html;
    } else {
        let html = `<button class="eval-badge eval-yellow" style="border:none;font-size:inherit;font-family:inherit;" onclick="evaluateJob(this,'${esc(job.link)}')" title="Click to manually evaluate this job">✨ Evaluate</button>`;
        if (status === 'Unseen') {
            html += ` <span class="eval-badge eval-green blurred-eval loading-blink">✨ Match: 100%</span>`;
            html += ` <span class="keyword-badge blurred-eval loading-blink" style="background-color:#34495e;color:white;">📄 Software</span>`;
            html += ` <button class="eval-badge eval-green blurred-eval loading-blink" style="background:linear-gradient(135deg,#3498db,#2980b9);border:none;">📋 Cover Letter</button>`;
        }
        return html;
    }
}

function updateJobCardEvalInPlace(link, score, reason, selected_cv, cover_letter) {
    const card = document.querySelector(`.job-card[data-url="${CSS.escape(link)}"]`);
    if (!card) return;
    
    const evalMetaSpan = card.querySelector('.eval-meta-container');
    if (evalMetaSpan) {
        const job = {
            link: link,
            eval_score: score,
            eval_reason: reason || '',
            selected_cv: selected_cv || '',
            cover_letter: cover_letter || ''
        };
        const status = card.getAttribute('data-status') || 'Unseen';
        evalMetaSpan.innerHTML = buildEvalHtml(job, status);
        
        // Smooth highlight pulse animation
        card.style.transition = 'box-shadow 0.4s ease, border-color 0.4s ease';
        card.style.boxShadow = '0 0 20px rgba(108, 92, 231, 0.7)';
        card.style.borderColor = '#a29bfe';
        setTimeout(() => {
            card.style.boxShadow = '';
            card.style.borderColor = '';
        }, 2500);
    }
}

function setupEvalTerminal() {
    if (window._evalEventSource) {
        try { window._evalEventSource.close(); } catch(e) {}
    }
    const evalEventSource = new EventSource("/api/eval_stream");
    window._evalEventSource = evalEventSource;
    const evalTerminal = document.getElementById("evalTerminalOutput");
    
    evalEventSource.onmessage = function (event) {
        const data = event.data;
        if (!data || data.trim() === ": keepalive") return;

        // Structured update events are consumed by the card updater. Keep
        // their JSON out of the terminal and show only a concise status line.
        let evalUpdate = null;
        if (data.includes("EVAL_UPDATE:")) {
            const marker = 'EVAL_UPDATE:';
            const markerIndex = data.indexOf(marker);
            const payload = data.slice(markerIndex + marker.length).trim();
            try {
                evalUpdate = JSON.parse(payload);
                if (evalUpdate && evalUpdate.link) {
                    updateJobCardEvalInPlace(
                        evalUpdate.link,
                        evalUpdate.eval_score,
                        evalUpdate.eval_reason,
                        evalUpdate.selected_cv,
                        evalUpdate.cover_letter
                    );
                }
            } catch (error) {
                console.warn('Could not parse evaluator update:', error);
            }
        }
        
        if (evalTerminal && evalTerminal.innerHTML === "Waiting for jobs to evaluate...") {
            evalTerminal.innerHTML = "";
        }
        
        if (evalTerminal) {
            // Keep evaluator/LLM text as text; preserve the server's line
            // breaks without allowing model output to become HTML.
            const displayData = evalUpdate
                ? `✅ Evaluation complete: ${parseInt(evalUpdate.eval_score, 10) || 0}/100`
                : data;
            evalTerminal.innerHTML += esc(displayData).replace(/&lt;br&gt;/g, '<br>') + "<br>";
            evalTerminal.parentElement.scrollTop = evalTerminal.parentElement.scrollHeight;
        }
    };
    
    evalEventSource.onerror = function () {
        console.log("Evaluator stream notice: auto-reconnecting if disconnected...");
    };
}
if (typeof EVALUATOR_ENABLED !== 'undefined' && EVALUATOR_ENABLED) {
    setupEvalTerminal();
}

function toggleEvaluator() {
    fetch('/api/toggle_evaluator', { method: 'POST' })
        .then(res => res.json())
        .then(data => updateEvalButton(data.state));
}

function evaluateAllUnseen() {
    const btn = document.getElementById('batchEvalBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerText = "⏳ Queuing...";
    }
    
    // Open terminal logs wrapper so user sees live output
    const wrapper = document.getElementById('evalTerminalOutputWrapper');
    if (wrapper) wrapper.style.display = 'block';
    
    fetch('/api/evaluate_all_unseen', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
        if (btn) {
            btn.disabled = false;
            if (data.queued_count > 0) {
                btn.innerText = `⚡ Running (${data.queued_count} queued)`;
            } else {
                btn.innerText = `⚡ 0 queued (others < threshold)`;
            }
            setTimeout(() => { btn.innerText = "⚡ Evaluate All Unseen"; }, 4000);
        }
        updateEvalButton('RUNNING');
    })
    .catch(err => {
        console.error('Batch eval error:', err);
        if (btn) {
            btn.disabled = false;
            btn.innerText = "⚡ Evaluate All Unseen";
        }
    });
}

function updateEvalButton(state) {
    const btn = document.getElementById('toggleEvalBtn');
    if (!btn) return;
    if (state === 'RUNNING') {
        btn.style.backgroundColor = '#27ae60';
        btn.innerText = 'Eval: ON';
    } else {
        btn.style.backgroundColor = '#f39c12';
        btn.innerText = 'Eval: OFF';
    }
}

function syncEvaluatorState() {
    if (typeof EVALUATOR_ENABLED === 'undefined' || !EVALUATOR_ENABLED) return;
    fetch('/api/get_evaluator_state')
        .then(res => res.json())
        .then(data => updateEvalButton(data.state));
}

function evaluateJob(btn, link) {
    if (typeof EVALUATOR_ENABLED !== 'undefined' && !EVALUATOR_ENABLED) {
        alert('AI Evaluation is disabled. Set enable_evaluator: true in config.yml to use this feature.');
        return;
    }
    if (btn.disabled) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = "⏳ Evaluating...";
    btn.disabled = true;
    
    // Open terminal logs wrapper so user can see what Gemini is doing
    const wrapper = document.getElementById('evalTerminalOutputWrapper');
    if (wrapper) wrapper.style.display = 'block';

    fetch('/api/evaluate_job', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link })
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            alert("Failed to queue evaluation.");
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    })
    .catch(() => { 
        alert("Failed to evaluate job due to network error."); 
        btn.innerHTML = originalText; 
        btn.disabled = false; 
    });
}

// ── Export CSV ───────────────────────────────────────────────────────────────

function exportFilteredJobsToCSV() {
    // Build the same query params as current filters but ask for all results (large limit)
    const params = buildQueryParams(1, 9999);
    fetch('/api/jobs?' + params)
    .then(r => r.json())
    .then(data => {
        const links = data.jobs.map(j => j.link);
        if (!links.length) { alert("No jobs to export!"); return; }
        return fetch('/api/export_csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ links })
        });
    })
    .then(response => {
        if (!response || !response.ok) throw new Error("Export failed");
        let filename = "JobFinder_Report.csv";
        const disposition = response.headers.get('Content-Disposition');
        if (disposition && disposition.indexOf('filename=') !== -1) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
            if (matches && matches[1]) filename = matches[1].replace(/['"]/g, '');
        }
        return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    })
    .catch(err => { console.error("Export error:", err); alert("An error occurred while exporting."); });
}

// ══════════════════════════════════════════════════════════════════════════════
// ── Server-side filter & render engine ───────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

const state = {
    search: '',
    status: 'Unseen',
    sort: 'date-desc',
    platforms: [],
    keywords: [],
    negKeywords: [],
    descTags: [],
    page: 1,
    pageSize: window.PAGE_SIZE || 20,
    isLoading: false,
    hasMore: true,
    totalCount: 0,
};

// Build URLSearchParams from current state
function buildQueryParams(page, pageSize) {
    const p = new URLSearchParams();
    if (state.search) p.set('search', state.search);
    if (state.status) p.set('status', state.status);
    if (state.sort) p.set('sort', state.sort);
    p.set('page', page || state.page);
    p.set('page_size', pageSize || state.pageSize);
    state.platforms.forEach(v => p.append('platform', v));
    state.keywords.forEach(v => p.append('keyword', v));
    state.negKeywords.forEach(v => p.append('neg_keyword', v));
    state.descTags.forEach(v => p.append('desc_tag', v));
    return p.toString();
}

let fetchAbort = null;

function fetchJobs(reset = true) {
    if (fetchAbort) fetchAbort.abort();
    fetchAbort = new AbortController();

    if (reset) {
        state.page = 1;
        state.hasMore = true;
        hideSentinel();
    }

    state.isLoading = true;

    if (reset) {
        showSkeletons();
    } else {
        document.getElementById('loadingMore').style.display = 'block';
    }

    const params = buildQueryParams(state.page, state.pageSize);

    fetch('/api/jobs?' + params, { signal: fetchAbort.signal })
    .then(r => r.json())
    .then(data => {
        state.isLoading = false;
        state.totalCount = data.total;
        state.hasMore = data.has_more;

        hideSkeletons();
        document.getElementById('loadingMore').style.display = 'none';

        const container = document.getElementById('jobsContainer');

        if (reset) container.innerHTML = '';

        data.jobs.forEach(job => {
            container.appendChild(buildCard(job));
        });

        updateCountDisplay();
        updateActiveChips();
        updateResetBtn();

        if (state.hasMore) {
            showSentinel();
        } else {
            hideSentinel();
        }
    })
    .catch(err => {
        if (err.name === 'AbortError') return;
        state.isLoading = false;
        hideSkeletons();
        document.getElementById('loadingMore').style.display = 'none';
        console.error('Failed to fetch jobs:', err);
    });
}

// Load the next page (called by IntersectionObserver)
function loadNextPage() {
    if (state.isLoading || !state.hasMore) return;
    state.page += 1;
    fetchJobs(false);
}

// ── Card builder (JS equivalent of job_card.html) ───────────────────────────

function buildCard(job) {
    const posKws = (job.keywords || '').split(',').map(s => s.trim()).filter(Boolean);
    const negKws = (job.negative_keywords || '').split(',').map(s => s.trim()).filter(Boolean);
    const descTags = (job.description_tags || '').split(',').map(s => s.trim()).filter(Boolean);
    const negDescTags = (job.neg_description_tags || '').split(',').map(s => s.trim()).filter(Boolean);
    const status = job.status || 'Unseen';
    const isSpecial = posKws.length > (window.SPECIAL_THRESHOLD || 3);
    const cardId = 'card-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    const descId = 'desc-' + cardId;

    const div = document.createElement('div');
    div.className = `job-card status-${status.toLowerCase()}${isSpecial ? ' special-offer' : ''}`;
    div.setAttribute('data-status', status);
    div.setAttribute('data-url', job.link || '');
    div.setAttribute('data-date', job.date_of_release || '');

    // ── Keyword score and badges
    const kwScore = (job.keyword_score !== undefined && job.keyword_score !== null && job.keyword_score !== '') ? parseInt(job.keyword_score) : 0;
    const minThreshold = window.EVALUATOR_MIN_SCORE || 5;
    const scoreBadgeClass = kwScore >= minThreshold ? 'kw-score-high' : (kwScore > 0 ? 'kw-score-med' : 'kw-score-low');

    let kwHtml = `<span class="count-badge ${scoreBadgeClass}" title="Keyword Match Score: ${kwScore} (Auto-evaluation minimum threshold is ${minThreshold})">🔑 ${kwScore >= 0 ? '+' : ''}${kwScore}</span> `;
    if (posKws.length > 0) kwHtml += `<span class="count-badge pos-count" title="Positive Keywords (${posKws.length})">${posKws.length}</span> `;
    posKws.forEach(kw => { kwHtml += `<span class="keyword-badge">${esc(kw)}</span>`; });
    if (negKws.length > 0) kwHtml += `<span class="count-badge neg-count" title="Negative Keywords (${negKws.length})">${negKws.length}</span> `;
    negKws.forEach(kw => { kwHtml += `<span class="keyword-badge negative-badge">${esc(kw)}</span>`; });

    // ── Desc tag badges
    let descTagHtml = '';
    if (descTags.length > 0 || negDescTags.length > 0) {
        descTagHtml = `<div class="job-meta desc-tag-row"><span class="meta-item" style="color:#7f8c8d;font-size:0.85em;">🔍 `;
        if (descTags.length) descTagHtml += `<span class="count-badge pos-count" title="Positive Description Tags">${descTags.length}</span> `;
        descTags.forEach(t => { descTagHtml += `<span class="keyword-badge" style="background-color:transparent;border:1px solid #bdc3c7;color:#7f8c8d;font-size:0.9em;padding:2px 6px;margin-left:4px;">${esc(t)}</span>`; });
        if (negDescTags.length) descTagHtml += `<span class="count-badge neg-count" title="Negative Description Tags">${negDescTags.length}</span> `;
        negDescTags.forEach(t => { descTagHtml += `<span class="keyword-badge negative-badge" style="background-color:transparent;font-size:0.9em;padding:2px 6px;margin-left:4px;">${esc(t)}</span>`; });
        descTagHtml += `</span></div>`;
    }

    // ── CV select options
    const cvTypes = window.CV_TYPES || [];
    let cvOptions = `<option value="" ${!job.cv_type ? 'selected' : ''} disabled>CV…</option>`;
    if (job.cv_type && !cvTypes.includes(job.cv_type)) {
        cvOptions += `<option value="${esc(job.cv_type)}" selected>${esc(job.cv_type)} ★</option>`;
    }
    cvTypes.forEach(cv => { cvOptions += `<option value="${esc(cv)}" ${job.cv_type === cv ? 'selected' : ''}>${esc(cv)}</option>`; });

    // ── Status buttons: New(Unseen) / Postpone(Later) / Issue / Skipped / Applied / Interview
    const statusBtns = [
        { s: 'Unseen',    e: '🆕', cls: 'btn-unseen',    t: 'New' },
        { s: 'Later',     e: '⏳', cls: 'btn-later',     t: 'Postpone' },
        { s: 'Issue',     e: '⚠️', cls: 'btn-issue',     t: 'Issue' },
        { s: 'Skipped',   e: '❌', cls: 'btn-skipped',   t: 'Skipped' },
        { s: 'Applied',   e: '✅', cls: 'btn-applied',   t: 'Applied' },
        { s: 'Interview', e: '🎯', cls: 'btn-interview', t: 'Interview' },
    ].map(({ s, e, cls, t }) =>
        `<button class="status-btn ${cls}${status === s ? ' active' : ''}" onclick="changeStatus(this,'${esc(job.link)}','${s}')" title="${t}">${e}</button>`
    ).join('');

    div.innerHTML = `
        <h2 class="job-title"><a href="${esc(job.link)}" target="_blank" class="title-link">${esc(job.title)}</a></h2>
        <div class="job-meta">
            <span class="meta-item eval-meta-container">${buildEvalHtml(job, status)}</span>
            <span class="meta-item"><span class="icon">🏢</span> <span class="company-name">${esc(job.company || 'Unknown')}</span></span>
            ${job.platform ? `<span class="meta-item"><span class="icon">🌐</span> <span class="platform-name">${esc(job.platform)}</span></span>` : ''}
            <span class="meta-item"><span class="icon">📅</span> <span class="date-text" title="${esc(job.date_of_release)}">${timeago(job.discovered_at || job.date_of_release)}</span></span>
            ${kwHtml ? `<span class="meta-item">${kwHtml}</span>` : ''}
            <span class="meta-item cv-selector-wrapper">
                <select class="cv-select" onchange="changeCvType(this,'${esc(job.link)}')" title="Select CV">${cvOptions}</select>
            </span>
        </div>
        ${descTagHtml}
        <div class="desc-footer">
            <button class="toggle-desc-btn" onclick="toggleDescription('${descId}',this)" title="Show/Hide Description">📄 Desc</button>
            <button class="note-btn" data-note-link="${esc(job.link)}" data-note="${esc(job.note || '')}" onclick="openNoteModal('${esc(job.link)}')" title="View/Edit Note">📝 Note</button>
            <button class="copy-btn" onclick="copyToClipboard('${descId}',this)" title="Copy Description">📋</button>
            <span class="footer-spacer"></span>
            <div class="status-btn-group">${statusBtns}</div>
            <button class="clear-btn" onclick="deleteJob(this,'${esc(job.link)}')" title="Delete Job">🗑️</button>
        </div>
        <div class="job-description" id="${descId}" style="display:none;">${job.description || ''}</div>
    `;

    return div;
}

// ── Count display ─────────────────────────────────────────────────────────────

function updateCountDisplay() {
    const el = document.getElementById('jobCountDisplay');
    if (!el) return;
    const loaded = document.querySelectorAll('#jobsContainer .job-card').length;
    el.textContent = `Showing ${loaded} of ${state.totalCount} offers`;
}

// ── Status tabs ───────────────────────────────────────────────────────────────

function setStatusTab(btn) {
    document.querySelectorAll('.status-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    state.status = btn.getAttribute('data-status') || '';
    fetchJobs(true);
}

function refreshStatusCounts() {
    fetch('/api/filter_options')
    .then(r => r.json())
    .then(opts => {
        const counts = opts.status_counts || {};
        const total = Object.values(counts).reduce((a, b) => a + b, 0);
        const el = document.getElementById('tabCount-all');
        if (el) el.textContent = total ? `(${total})` : '';
        ['Unseen', 'Later', 'Issue', 'Skipped', 'Applied', 'Interview'].forEach(s => {
            const c = document.getElementById(`tabCount-${s}`);
            if (c) c.textContent = counts[s] ? `(${counts[s]})` : '';
        });
    });
}

// ── Advanced filter dropdowns ─────────────────────────────────────────────────

function toggleFilterDropdown(id) {
    const el = document.getElementById(id);
    const isOpen = el.style.display !== 'none';
    // Close all
    document.querySelectorAll('.filter-dropdown').forEach(d => d.style.display = 'none');
    if (!isOpen) el.style.display = 'block';
}

document.addEventListener('click', e => {
    if (!e.target.closest('.filter-dropdown-wrap')) {
        document.querySelectorAll('.filter-dropdown').forEach(d => d.style.display = 'none');
    }
});

function filterDropdownSearch(input, dropId) {
    const val = input.value.toLowerCase();
    const list = document.getElementById(dropId + 'List');
    if (!list) return;
    list.querySelectorAll('label').forEach(label => {
        label.style.display = label.textContent.toLowerCase().includes(val) ? '' : 'none';
    });
}

function buildDropdownList(listId, items, stateArray, labelFn, onChange) {
    const list = document.getElementById(listId);
    if (!list) return;
    list.innerHTML = '';
    items.forEach(item => {
        const label = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = item;
        cb.checked = stateArray.includes(item);
        cb.style.marginRight = '8px';
        cb.onchange = () => { onChange(item, cb.checked); fetchJobs(true); updatePillLabel(); };
        label.appendChild(cb);
        label.appendChild(document.createTextNode(labelFn ? labelFn(item) : item));
        list.appendChild(label);
    });
}

function updatePillLabel() {
    const pairs = [
        { labelId: 'platformPillLabel', arr: state.platforms, def: 'Platform' },
        { labelId: 'keywordPillLabel', arr: state.keywords, def: 'Keyword' },
        { labelId: 'negKwPillLabel', arr: state.negKeywords, def: '⚠ Neg. Keyword' },
    ];
    pairs.forEach(({ labelId, arr, def }) => {
        const el = document.getElementById(labelId);
        if (!el) return;
        el.textContent = arr.length > 0 ? `${def} (${arr.length})` : def;
        const btn = el.closest('.filter-pill-btn');
        if (btn) btn.classList.toggle('active', arr.length > 0);
    });
}

function loadFilterOptions() {
    fetch('/api/filter_options')
    .then(r => r.json())
    .then(opts => {
        buildDropdownList('platformDropList', opts.platforms, state.platforms, null,
            (v, checked) => { if (checked) state.platforms.push(v); else state.platforms = state.platforms.filter(x => x !== v); });
        buildDropdownList('keywordDropList', opts.keywords, state.keywords, null,
            (v, checked) => { if (checked) state.keywords.push(v); else state.keywords = state.keywords.filter(x => x !== v); });
        buildDropdownList('negKwDropList', opts.neg_keywords, state.negKeywords, null,
            (v, checked) => { if (checked) state.negKeywords.push(v); else state.negKeywords = state.negKeywords.filter(x => x !== v); });

        // Populate tab counts
        const counts = opts.status_counts || {};
        const total = Object.values(counts).reduce((a, b) => a + b, 0);
        const elAll = document.getElementById('tabCount-all');
        if (elAll) elAll.textContent = total ? `(${total})` : '';
        ['Unseen', 'Later', 'Issue', 'Skipped', 'Applied', 'Interview'].forEach(s => {
            const c = document.getElementById(`tabCount-${s}`);
            if (c) c.textContent = counts[s] ? `(${counts[s]})` : '';
        });
    });
}

// ── Active chips ──────────────────────────────────────────────────────────────

function updateActiveChips() {
    const container = document.getElementById('activeChips');
    if (!container) return;
    container.innerHTML = '';

    const addChip = (label, onRemove) => {
        const chip = document.createElement('span');
        chip.className = 'active-chip';
        chip.innerHTML = `${esc(label)} <button onclick="(${onRemove.toString()})(); fetchJobs(true); updateActiveChips(); updateResetBtn();">×</button>`;
        container.appendChild(chip);
    };

    if (state.search) addChip(`Search: "${state.search}"`, () => { state.search = ''; document.getElementById('searchInput').value = ''; });
    state.platforms.forEach(v => addChip(`Platform: ${v}`, () => { state.platforms = state.platforms.filter(x => x !== v); updatePillLabel(); }));
    state.keywords.forEach(v => addChip(`Keyword: ${v}`, () => { state.keywords = state.keywords.filter(x => x !== v); updatePillLabel(); }));
    state.negKeywords.forEach(v => addChip(`⚠ Neg: ${v}`, () => { state.negKeywords = state.negKeywords.filter(x => x !== v); updatePillLabel(); }));
}

function updateResetBtn() {
    const btn = document.getElementById('resetFiltersBtn');
    if (!btn) return;
    const hasFilters = state.search || state.platforms.length || state.keywords.length || state.negKeywords.length;
    btn.style.display = hasFilters ? 'inline-flex' : 'none';
}

function resetAllFilters() {
    state.search = '';
    state.platforms = [];
    state.keywords = [];
    state.negKeywords = [];
    state.descTags = [];
    document.getElementById('searchInput').value = '';
    updatePillLabel();
    // Uncheck all dropdown checkboxes
    document.querySelectorAll('.filter-dropdown-list input[type=checkbox]').forEach(cb => cb.checked = false);
    fetchJobs(true);
}

function clearSearch() {
    state.search = '';
    document.getElementById('searchInput').value = '';
    document.getElementById('searchClearBtn').style.display = 'none';
    fetchJobs(true);
}

// ── Skeleton loaders ──────────────────────────────────────────────────────────

function showSkeletons() {
    const container = document.getElementById('jobsContainer');
    container.innerHTML = '';
    for (let i = 0; i < 3; i++) {
        const sk = document.createElement('div');
        sk.className = 'skeleton-card';
        container.appendChild(sk);
    }
}

function hideSkeletons() {
    document.querySelectorAll('.skeleton-card').forEach(el => el.remove());
}

// ── IntersectionObserver for infinite scroll ──────────────────────────────────

function showSentinel() {
    const el = document.getElementById('scrollSentinel');
    if (el) el.style.visibility = 'visible';
}
function hideSentinel() {
    const el = document.getElementById('scrollSentinel');
    if (el) el.style.visibility = 'hidden';
}

// ── Scraper: prepend newest job ───────────────────────────────────────────────

function prependLatestJob() {
    fetch('/api/jobs?sort=date-desc&page=1&page_size=1')
    .then(r => r.json())
    .then(data => {
        if (!data.jobs || !data.jobs.length) return;
        const job = data.jobs[0];
        // Don't prepend if it's already in the DOM
        if (document.querySelector(`[data-url="${CSS.escape(job.link)}"]`)) return;
        const card = buildCard(job);
        card.style.opacity = '0';
        card.style.transform = 'translateY(-10px)';
        card.style.transition = 'opacity 0.4s, transform 0.4s';
        const container = document.getElementById('jobsContainer');
        container.prepend(card);
        requestAnimationFrame(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        });
        state.totalCount += 1;
        updateCountDisplay();
        refreshStatusCounts();
    })
    .catch(err => console.error('Failed to fetch latest job:', err));
}

// ── Debounce search input ─────────────────────────────────────────────────────

let searchTimeout;
function onSearchInput() {
    const val = document.getElementById('searchInput').value;
    document.getElementById('searchClearBtn').style.display = val ? 'flex' : 'none';
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        state.search = val;
        fetchJobs(true);
    }, 300);
}

function onFilterChange() {
    state.sort = document.getElementById('sortSelect').value;
    fetchJobs(true);
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    state.pageSize = window.PAGE_SIZE || 20;

    // Wire search input
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.addEventListener('input', onSearchInput);

    // IntersectionObserver for infinite scroll
    const sentinel = document.getElementById('scrollSentinel');
    if (sentinel && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && !state.isLoading && state.hasMore) {
                loadNextPage();
            }
        }, { rootMargin: '200px' });
        observer.observe(sentinel);
    }

    // Load filter options (platforms, keywords, neg keywords)
    loadFilterOptions();

    // Initial job fetch
    fetchJobs(true);

    // Sync evaluator button state
    syncEvaluatorState();
});
