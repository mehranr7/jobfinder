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
    const text = document.getElementById(elementId).innerText;
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerText;
        btn.innerText = "✅";
        setTimeout(() => btn.innerText = originalText, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
    });
}

function changeStatus(btn, link, newStatus) {
    const card = btn.closest('.job-card');

    if (btn.disabled) return;

    const originalText = btn.innerText;
    btn.innerText = "⏳";
    btn.disabled = true;

    fetch('/api/change_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link,
            status: newStatus
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update UI
                const group = btn.closest('.status-btn-group');
                if (group) {
                    group.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
                }
                btn.classList.add('active');

                card.setAttribute('data-status', newStatus);
                // remove old status classes
                card.className = card.className.replace(/\bstatus-[a-z]+\b/g, '').trim();
                card.classList.add('status-' + newStatus.toLowerCase());

                let emoji = "👀";
                if (newStatus === "Applied") emoji = "✅";
                if (newStatus === "Skipped") emoji = "⏭️";
                btn.innerText = emoji;
                btn.disabled = false;

                filterJobs(); // update counts and visibility if filtered
            } else {
                alert("Failed to update status.");
                btn.innerText = originalText;
                btn.disabled = false;
            }
        })
        .catch(error => {
            console.error("Error changing status:", error);
            alert("Failed to update status due to network error.");
            btn.innerText = originalText;
            btn.disabled = false;
        });
}

function changeCV(selectElement, link) {
    const cvType = selectElement.value;
    const wrapper = selectElement.closest('.cv-selector-wrapper');
    const originalBorder = selectElement.style.borderColor;

    selectElement.disabled = true;

    fetch('/api/change_cv', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link,
            cv_type: cvType
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                selectElement.style.borderColor = 'var(--success)';
                setTimeout(() => {
                    selectElement.style.borderColor = originalBorder;
                }, 2000);
                selectElement.disabled = false;
            } else {
                alert("Failed to update CV.");
                selectElement.disabled = false;
            }
        })
        .catch(error => {
            console.error("Error changing CV:", error);
            alert("Failed to update CV due to network error.");
            selectElement.disabled = false;
        });
}

function changeAppState(selectElement, link) {
    const appState = selectElement.value;
    const originalBorder = selectElement.style.borderColor;
    
    selectElement.disabled = true;
    
    fetch('/api/change_app_state', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link,
            app_state: appState
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            selectElement.style.borderColor = 'var(--success)';
            setTimeout(() => {
                selectElement.style.borderColor = originalBorder;
            }, 2000);
            selectElement.disabled = false;
        } else {
            alert("Failed to update State.");
            selectElement.disabled = false;
        }
    })
    .catch(error => {
        console.error("Error changing state:", error);
        alert("Failed to update state due to network error.");
        selectElement.disabled = false;
    });
}

function openNoteModal(link) {
    // Find the button to get the note data
    const noteBtn = document.querySelector(`button[onclick="openNoteModal('${link}')"]`);
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
    
    // Replace escaped newlines with actual newlines
    let letter = btn.getAttribute('data-letter') || "";
    letter = letter.replace(/\\n/g, '\n');
    
    navigator.clipboard.writeText(letter).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = "✅ Copied!";
        btn.disabled = true;
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        alert("Failed to copy Cover Letter to clipboard.");
    });
}

function saveNote() {
    const link = document.getElementById('noteJobLink').value;
    const note = document.getElementById('noteTextarea').value;
    
    fetch('/api/save_note', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link,
            note: note
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            // Update the data-note attribute on the button so it persists without refresh
            const noteBtn = document.querySelector(`button[onclick="openNoteModal('${link}')"]`);
            if (noteBtn) {
                noteBtn.setAttribute('data-note', note);
                noteBtn.style.color = 'var(--success)';
                setTimeout(() => noteBtn.style.color = '', 2000);
            }
            closeNoteModal();
        } else {
            alert("Failed to save note.");
        }
    })
    .catch(error => {
        console.error("Error saving note:", error);
        alert("Failed to save note due to network error.");
    });
}

function deleteJob(btn, link) {
    if (!confirm("Are you sure you want to permanently delete this job offer? (Note: If it's still live on the website, it might be scraped again next time.)")) return;

    const card = btn.closest('.job-card');
    btn.disabled = true;
    btn.innerText = "⏳";

    fetch('/api/delete_job', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                card.remove();
                // Update global array so filters keep working correctly
                window.jobCards = window.jobCards.filter(c => c !== card);
                filterJobs(); // Update counts
            } else {
                alert("Failed to delete job.");
                btn.innerText = "🗑️";
                btn.disabled = false;
            }
        })
        .catch(error => {
            console.error("Error deleting job:", error);
            alert("Failed to delete job due to network error.");
            btn.innerText = "🗑️";
            btn.disabled = false;
        });
}

function filterJobs() {
    const searchInput = document.getElementById('searchInput');
    const textFilter = searchInput ? searchInput.value.toLowerCase() : "";

    const selectedKws = Array.from(document.querySelectorAll('.kw-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedNegKws = Array.from(document.querySelectorAll('.neg-kw-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedCompanies = Array.from(document.querySelectorAll('.company-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedPlatforms = Array.from(document.querySelectorAll('.platform-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedDescTags = Array.from(document.querySelectorAll('.desc-tag-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedNegDescTags = Array.from(document.querySelectorAll('.neg-desc-tag-checkbox:checked')).map(cb => cb.value.toLowerCase());

    const kwTitle = document.getElementById('keywordSelectTitle');
    if (kwTitle) kwTitle.innerText = selectedKws.length > 0 ? `${selectedKws.length} Selected` : 'All Keywords';

    const companyTitle = document.getElementById('companySelectTitle');
    if (companyTitle) companyTitle.innerText = selectedCompanies.length > 0 ? `${selectedCompanies.length} Selected` : 'All Companies';

    const platformTitle = document.getElementById('platformSelectTitle');
    if (platformTitle) platformTitle.innerText = selectedPlatforms.length > 0 ? `${selectedPlatforms.length} Selected` : 'All Platforms';

    const negKwTitle = document.getElementById('negKeywordSelectTitle');
    if (negKwTitle) negKwTitle.innerText = selectedNegKws.length > 0 ? `${selectedNegKws.length} Selected` : 'All Negative Keywords';

    const descTagTitle = document.getElementById('descTagSelectTitle');
    if (descTagTitle) descTagTitle.innerText = selectedDescTags.length > 0 ? `${selectedDescTags.length} Selected` : 'All Description Tags';

    const negDescTagTitle = document.getElementById('negDescTagSelectTitle');
    if (negDescTagTitle) negDescTagTitle.innerText = selectedNegDescTags.length > 0 ? `${selectedNegDescTags.length} Selected` : 'All Neg Desc Tags';

    const statusSelect = document.getElementById('statusFilter');
    const statusFilter = statusSelect ? statusSelect.value : "";

    window.filteredCards = window.jobCards.filter(card => {
        const title = card.getAttribute('data-title');
        const kws = card.getAttribute('data-keyword').toLowerCase();
        const company = (card.getAttribute('data-company') || "").toLowerCase();
        const platform = (card.getAttribute('data-platform') || "").toLowerCase();
        const status = card.getAttribute('data-status') || "Unseen";

        const posKwsList = card.getAttribute('data-pos-keyword').split(',').map(s => s.trim());
        const negKwsList = card.getAttribute('data-neg-keyword').split(',').map(s => s.trim());
        const descTagsList = (card.getAttribute('data-desc-tags') || "").split(',').map(s => s.trim());
        const negDescTagsList = (card.getAttribute('data-neg-desc-tags') || "").split(',').map(s => s.trim());

        let matchesText = title.includes(textFilter) || kws.includes(textFilter) || company.includes(textFilter) || platform.includes(textFilter);
        let matchesKeyword = selectedKws.length === 0 || selectedKws.some(kw => posKwsList.includes(kw));
        let matchesCompany = selectedCompanies.length === 0 || selectedCompanies.includes(company);
        let matchesPlatform = selectedPlatforms.length === 0 || selectedPlatforms.includes(platform);
        let matchesNegKeyword = selectedNegKws.length === 0 || selectedNegKws.some(kw => negKwsList.includes(kw));
        let matchesDescTag = selectedDescTags.length === 0 || selectedDescTags.some(tag => descTagsList.includes(tag));
        let matchesNegDescTag = selectedNegDescTags.length === 0 || selectedNegDescTags.some(tag => negDescTagsList.includes(tag));

        let matchesStatus = true;
        if (statusFilter && statusFilter !== "") {
            matchesStatus = (status === statusFilter);
        }

        return matchesText && matchesKeyword && matchesCompany && matchesPlatform && matchesNegKeyword && matchesDescTag && matchesNegDescTag && matchesStatus;
    });

    applySortAndRender(true);
}

function applySortAndRender(resetPagination) {
    const sortSelect = document.getElementById('sortSelect');
    const sortValue = sortSelect ? sortSelect.value : "date-desc";

    if (sortValue === "date-asc") {
        window.filteredCards.sort((a, b) => {
            const da = new Date(a.getAttribute('data-date')).getTime();
            const db = new Date(b.getAttribute('data-date')).getTime();
            if (isNaN(da) && isNaN(db)) return 0;
            if (isNaN(da)) return 1;
            if (isNaN(db)) return -1;
            return da - db;
        });
    } else if (sortValue === "date-desc") {
        window.filteredCards.sort((a, b) => {
            const da = new Date(a.getAttribute('data-date')).getTime();
            const db = new Date(b.getAttribute('data-date')).getTime();
            if (isNaN(da) && isNaN(db)) return 0;
            if (isNaN(da)) return 1;
            if (isNaN(db)) return -1;
            return db - da;
        });
    } else if (sortValue === "title-asc") {
        window.filteredCards.sort((a, b) => a.getAttribute('data-title').localeCompare(b.getAttribute('data-title')));
    } else if (sortValue === "title-desc") {
        window.filteredCards.sort((a, b) => b.getAttribute('data-title').localeCompare(a.getAttribute('data-title')));
    } else if (sortValue === "keyword-asc") {
        window.filteredCards.sort((a, b) => a.getAttribute('data-keyword').localeCompare(b.getAttribute('data-keyword')));
    }

    if (resetPagination) {
        window.currentVisibleCount = window.PAGE_SIZE || 20;
    }
    renderCards();
}

function renderCards() {
    const container = document.querySelector('.jobs-container');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    const countDisplay = document.getElementById('jobCountDisplay');

    // Hide all initially
    window.jobCards.forEach(card => card.style.display = 'none');

    // Show only the visible slice
    const visibleCards = window.filteredCards.slice(0, window.currentVisibleCount);

    visibleCards.forEach(card => {
        container.appendChild(card); // guarantees DOM order matches sort
        card.style.display = 'block';
    });

    // Update Load More button
    if (window.filteredCards.length > window.currentVisibleCount) {
        if (loadMoreBtn) loadMoreBtn.style.display = 'inline-block';
    } else {
        if (loadMoreBtn) loadMoreBtn.style.display = 'none';
    }

    // Update counter
    const showing = Math.min(window.currentVisibleCount, window.filteredCards.length);
    if (countDisplay) {
        countDisplay.innerText = `Showing ${showing} of ${window.filteredCards.length} Offers`;
    }
}

function loadMoreJobs() {
    window.currentVisibleCount += (window.PAGE_SIZE || 20);
    renderCards();
}

function sortJobs() {
    applySortAndRender(true);
}

function clearSearch() {
    document.getElementById('searchInput').value = '';
    filterJobs();
}

function clearCompany() {
    document.querySelectorAll('.company-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearPlatform() {
    document.querySelectorAll('.platform-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearKeyword() {
    document.querySelectorAll('.kw-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearNegativeKeyword() {
    document.querySelectorAll('.neg-kw-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearDescTag() {
    document.querySelectorAll('.desc-tag-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearNegDescTag() {
    document.querySelectorAll('.neg-desc-tag-checkbox').forEach(cb => cb.checked = false);
    filterJobs();
}

function clearStatus() {
    document.getElementById('statusFilter').value = '';
    filterJobs();
}

function toggleDropdown(id) {
    const el = document.getElementById(id);
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.multi-select')) {
        document.querySelectorAll('.dropdown-content').forEach(d => d.style.display = 'none');
    }
});

function runScraper() {
    const btn = document.getElementById('runScraperBtn');
    const pauseBtn = document.getElementById('pauseScraperBtn');
    const resumeBtn = document.getElementById('resumeScraperBtn');
    const stopBtn = document.getElementById('stopScraperBtn');

    const term = document.getElementById('terminalContainer');
    const termOut = document.getElementById('terminalOutput');
    const termWrapper = document.getElementById('terminalOutputWrapper');

    btn.disabled = true;
    btn.innerText = "Running...";
    btn.style.display = 'none'; // hide run button
    pauseBtn.style.display = 'inline-block';
    resumeBtn.style.display = 'none';
    stopBtn.style.display = 'inline-block';

    term.style.display = 'block';
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
            // Don't print internal signals to the UI terminal
            if (!event.data.includes("-> UI_RELOAD")) {
                termOut.innerHTML += event.data + '\n';
                termWrapper.scrollTop = termWrapper.scrollHeight;
            }

            // If a new job was safely saved to DB, fetch the updated job list and total count
            if (event.data.includes("-> UI_RELOAD")) {
                fetchLatestJobs();
            }
        }
    };

    source.onerror = function (event) {
        source.close();
        resetButtons();
        termOut.innerHTML += '\nError connecting to scraper stream.\n';
    };
}

function pauseScraper() {
    fetch('/api/pause_scraper', { method: 'POST' })
        .then(() => {
            document.getElementById('pauseScraperBtn').style.display = 'none';
            document.getElementById('resumeScraperBtn').style.display = 'inline-block';
        });
}

function resumeScraper() {
    fetch('/api/resume_scraper', { method: 'POST' })
        .then(() => {
            document.getElementById('resumeScraperBtn').style.display = 'none';
            document.getElementById('pauseScraperBtn').style.display = 'inline-block';
        });
}

function stopScraper() {
    fetch('/api/stop_scraper', { method: 'POST' })
        .then(() => {
            document.getElementById('pauseScraperBtn').style.display = 'none';
            document.getElementById('resumeScraperBtn').style.display = 'none';
            // Stop button can stay visible until the stream formally closes
        });
}

function fetchLatestJobs() {
    fetch('/api/get_job_cards')
        .then(response => response.text())
        .then(html => {
            const container = document.querySelector('.jobs-container');
            container.innerHTML = html;

            // Re-initialize jobCards list so filters keep working
            window.jobCards = Array.from(document.querySelectorAll('.job-card'));

            // Re-populate dropdowns with new tags from newly added jobs
            populateDropdowns();

            // Re-apply filters and sorting
            filterJobs();
            sortJobs();

            // Update total job count (which is handled in filterJobs, but just to be sure)
        })
        .catch(err => console.error("Error fetching latest jobs:", err));
}

function toggleTerminal(wrapperId) {
    const wrapper = document.getElementById(wrapperId);
    if (wrapper.style.display === "none") {
        wrapper.style.display = "block";
    } else {
        wrapper.style.display = "none";
    }
}

// --- EVALUATOR TERMINAL ---
function setupEvalTerminal() {
    const evalEventSource = new EventSource("/api/eval_stream");
    const evalTerminal = document.getElementById("evalTerminalOutput");
    
    evalEventSource.onmessage = function (event) {
        if (evalTerminal.innerHTML === "Waiting for jobs to evaluate...") {
            evalTerminal.innerHTML = "";
        }
        evalTerminal.innerHTML += event.data + "<br>";
        evalTerminal.parentElement.scrollTop = evalTerminal.parentElement.scrollHeight;

        if (event.data.includes("-> Score:")) {
            fetchLatestJobs();
        }
    };
    
    evalEventSource.onerror = function() {
        console.log("Evaluator stream disconnected. Reconnecting in 5s...");
        evalEventSource.close();
        setTimeout(setupEvalTerminal, 5000);
    };
}
setupEvalTerminal();

function pauseEvaluator() {
    fetch('/api/pause_evaluator', { method: 'POST' })
        .then(() => {
            document.getElementById('pauseEvalBtn').style.display = 'none';
            document.getElementById('resumeEvalBtn').style.display = 'inline-block';
        });
}

function resumeEvaluator() {
    fetch('/api/resume_evaluator', { method: 'POST' })
        .then(() => {
            document.getElementById('resumeEvalBtn').style.display = 'none';
            document.getElementById('pauseEvalBtn').style.display = 'inline-block';
        });
}

function evaluateJob(btn, link) {
    if (btn.disabled) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = "⏳ Evaluating...";
    btn.disabled = true;

    fetch('/api/evaluate_job', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            // Let the SSE terminal handle the refresh once evaluation is fully complete
            // We just leave the button in the loading state for now
        } else {
            alert("Failed to queue evaluation.");
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    })
    .catch(error => {
        console.error("Error evaluating job:", error);
        alert("Failed to evaluate job due to network error.");
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

function exportFilteredJobsToCSV() {
    if (!window.filteredCards || window.filteredCards.length === 0) {
        alert("No jobs to export! Please adjust your filters.");
        return;
    }
    
    // Extract the exact URLs of all currently filtered jobs
    const links = window.filteredCards.map(card => card.getAttribute('data-url'));
    
    fetch('/api/export_csv', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ links: links })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Failed to export CSV from server.");
        }
        // Extract filename from headers if possible, otherwise use a fallback
        let filename = "JobFinder_Report.csv";
        const disposition = response.headers.get('Content-Disposition');
        if (disposition && disposition.indexOf('filename=') !== -1) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
            if (matches != null && matches[1]) { 
                filename = matches[1].replace(/['"]/g, '');
            }
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
    .catch(err => {
        console.error("Export error:", err);
        alert("An error occurred while exporting the report.");
    });
}

// --- SCRAPER TERMINAL ---
function populateDropdowns() {
    // Populate Company dropdown
    const companies = new Set();
    const platforms = new Set();
    window.jobCards.forEach(card => {
        const comp = card.getAttribute('data-company');
        if (comp && comp.trim()) companies.add(comp.trim().toLowerCase());
        
        const plat = card.getAttribute('data-platform');
        if (plat && plat.trim()) platforms.add(plat.trim().toLowerCase());
    });

    const companyDropdown = document.getElementById('companyDropdown');
    if (companyDropdown) {
        companyDropdown.innerHTML = '';
        Array.from(companies).sort().forEach(comp => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = comp;
            checkbox.className = 'company-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            
            const displayComp = comp.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            label.appendChild(document.createTextNode(displayComp));
            companyDropdown.appendChild(label);
        });
    }

    const platformDropdown = document.getElementById('platformDropdown');
    if (platformDropdown) {
        platformDropdown.innerHTML = '';
        Array.from(platforms).sort().forEach(plat => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = plat;
            checkbox.className = 'platform-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            
            const displayPlat = plat.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            label.appendChild(document.createTextNode(displayPlat));
            platformDropdown.appendChild(label);
        });
    }

    // Populate the keyword dropdowns
    const keywords = new Set();
    const negKeywords = new Set();

    const posBadges = document.querySelectorAll('.keyword-badge:not(.negative-badge)');
    posBadges.forEach(b => keywords.add(b.innerText.trim().toLowerCase()));

    const negBadges = document.querySelectorAll('.negative-badge');
    negBadges.forEach(b => negKeywords.add(b.innerText.trim().toLowerCase()));

    const keywordDropdown = document.getElementById('keywordDropdown');
    if (keywordDropdown) {
        keywordDropdown.innerHTML = '';
        Array.from(keywords).sort().forEach(kw => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = kw;
            checkbox.className = 'kw-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(kw.charAt(0).toUpperCase() + kw.slice(1)));
            keywordDropdown.appendChild(label);
        });
    }

    const negKeywordDropdown = document.getElementById('negKeywordDropdown');
    if (negKeywordDropdown) {
        negKeywordDropdown.innerHTML = '';
        Array.from(negKeywords).sort().forEach(kw => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = kw;
            checkbox.className = 'neg-kw-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(kw.charAt(0).toUpperCase() + kw.slice(1)));
            negKeywordDropdown.appendChild(label);
        });
    }

    // Populate Description Tags dropdown
    const descTags = new Set();
    window.jobCards.forEach(card => {
        const tags = (card.getAttribute('data-desc-tags') || "").split(',');
        tags.forEach(t => {
            if (t.trim()) descTags.add(t.trim().toLowerCase());
        });
    });

    const descTagDropdown = document.getElementById('descTagDropdown');
    if (descTagDropdown) {
        descTagDropdown.innerHTML = '';
        Array.from(descTags).sort().forEach(tag => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = tag;
            checkbox.className = 'desc-tag-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(tag.charAt(0).toUpperCase() + tag.slice(1)));
            descTagDropdown.appendChild(label);
        });
    }

    // Populate Negative Description Tags dropdown
    const negDescTags = new Set();
    window.jobCards.forEach(card => {
        const tags = (card.getAttribute('data-neg-desc-tags') || "").split(',');
        tags.forEach(t => {
            if (t.trim()) negDescTags.add(t.trim().toLowerCase());
        });
    });

    const negDescTagDropdown = document.getElementById('negDescTagDropdown');
    if (negDescTagDropdown) {
        negDescTagDropdown.innerHTML = '';
        Array.from(negDescTags).sort().forEach(tag => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.marginBottom = '5px';
            label.style.cursor = 'pointer';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = tag;
            checkbox.className = 'neg-desc-tag-checkbox';
            checkbox.style.marginRight = '8px';
            checkbox.onchange = filterJobs;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(tag.charAt(0).toUpperCase() + tag.slice(1)));
            negDescTagDropdown.appendChild(label);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.jobCards = Array.from(document.querySelectorAll('.job-card'));
    window.originalJobCards = [...window.jobCards];
    window.filteredCards = [...window.jobCards];
    window.currentVisibleCount = window.PAGE_SIZE || 20;

    populateDropdowns();

    // Initial filter, sort, and render
    filterJobs();
});
