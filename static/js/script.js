function toggleDescription(elementId, btn) {
    const desc = document.getElementById(elementId);
    if (desc.style.display === 'none' || desc.style.display === '') {
        desc.style.display = 'block';
        btn.innerText = '▲ Hide Description';
    } else {
        desc.style.display = 'none';
        btn.innerText = '▼ Show Description';
    }
}

function copyToClipboard(elementId, btn) {
    const text = document.getElementById(elementId).innerText;
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerText;
        btn.innerText = "Copied!";
        setTimeout(() => btn.innerText = originalText, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
    });
}

function changeStatus(btn, link, newStatus) {
    const card = btn.closest('.job-card');
    
    if (btn.disabled) return;
    
    const originalText = btn.innerText;
    btn.innerText = "Updating...";
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
        if(data.success) {
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
            
            btn.innerText = newStatus;
            filterJobs(); // update counts and visibility if filtered
        } else {
            alert("Failed to update status.");
            btn.innerText = originalText;
        }
    })
    .catch(error => {
        console.error("Error changing status:", error);
        alert("Failed to update status due to network error.");
        btn.innerText = originalText;
    })
    .finally(() => {
        btn.disabled = false;
    });
}

function deleteJob(btn, link) {
    if(!confirm("Are you sure you want to permanently delete this job offer? (Note: If it's still live on the website, it might be scraped again next time.)")) return;
    
    const card = btn.closest('.job-card');
    btn.disabled = true;
    btn.innerText = "Deleting...";
    
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
        if(data.success) {
            card.remove();
            // Update global array so filters keep working correctly
            window.jobCards = window.jobCards.filter(c => c !== card);
            filterJobs(); // Update counts
        } else {
            alert("Failed to delete job.");
            btn.innerText = "🗑️ Delete";
            btn.disabled = false;
        }
    })
    .catch(error => {
        console.error("Error deleting job:", error);
        alert("Failed to delete job due to network error.");
        btn.innerText = "🗑️ Delete";
        btn.disabled = false;
    });
}

function filterJobs() {
    const searchInput = document.getElementById('searchInput');
    const textFilter = searchInput ? searchInput.value.toLowerCase() : "";
    
    const selectedKws = Array.from(document.querySelectorAll('.kw-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedNegKws = Array.from(document.querySelectorAll('.neg-kw-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedDescTags = Array.from(document.querySelectorAll('.desc-tag-checkbox:checked')).map(cb => cb.value.toLowerCase());
    const selectedNegDescTags = Array.from(document.querySelectorAll('.neg-desc-tag-checkbox:checked')).map(cb => cb.value.toLowerCase());
    
    const kwTitle = document.getElementById('keywordSelectTitle');
    if (kwTitle) kwTitle.innerText = selectedKws.length > 0 ? `${selectedKws.length} Selected` : 'All Keywords';
    
    const negKwTitle = document.getElementById('negKeywordSelectTitle');
    if (negKwTitle) negKwTitle.innerText = selectedNegKws.length > 0 ? `${selectedNegKws.length} Selected` : 'All Negative Keywords';

    const descTagTitle = document.getElementById('descTagSelectTitle');
    if (descTagTitle) descTagTitle.innerText = selectedDescTags.length > 0 ? `${selectedDescTags.length} Selected` : 'All Description Tags';

    const negDescTagTitle = document.getElementById('negDescTagSelectTitle');
    if (negDescTagTitle) negDescTagTitle.innerText = selectedNegDescTags.length > 0 ? `${selectedNegDescTags.length} Selected` : 'All Neg Desc Tags';
    
    const statusSelect = document.getElementById('statusFilter');
    const statusFilter = statusSelect ? statusSelect.value : "";
    
    let visibleCount = 0;
    
    window.jobCards.forEach(card => {
        const title = card.getAttribute('data-title');
        const kws = card.getAttribute('data-keyword').toLowerCase();
        const status = card.getAttribute('data-status') || "Unseen";
        
        const posKwsList = card.getAttribute('data-pos-keyword').split(',').map(s => s.trim());
        const negKwsList = card.getAttribute('data-neg-keyword').split(',').map(s => s.trim());
        const descTagsList = (card.getAttribute('data-desc-tags') || "").split(',').map(s => s.trim());
        const negDescTagsList = (card.getAttribute('data-neg-desc-tags') || "").split(',').map(s => s.trim());
        
        let matchesText = title.includes(textFilter) || kws.includes(textFilter);
        let matchesKeyword = selectedKws.length === 0 || selectedKws.some(kw => posKwsList.includes(kw));
        // Show jobs that HAVE at least one of the selected negative keywords
        let matchesNegKeyword = selectedNegKws.length === 0 || selectedNegKws.some(kw => negKwsList.includes(kw));
        let matchesDescTag = selectedDescTags.length === 0 || selectedDescTags.some(tag => descTagsList.includes(tag));
        let matchesNegDescTag = selectedNegDescTags.length === 0 || selectedNegDescTags.some(tag => negDescTagsList.includes(tag));
        
        let matchesStatus = true;
        if (statusFilter && statusFilter !== "") {
            matchesStatus = (status === statusFilter);
        }
        
        if (matchesText && matchesKeyword && matchesNegKeyword && matchesDescTag && matchesNegDescTag && matchesStatus) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    document.getElementById('jobCountDisplay').innerText = `Total Offers: ${visibleCount}`;
}

function clearSearch() {
    document.getElementById('searchInput').value = '';
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

function clearStatus() {
    document.getElementById('statusFilter').value = '';
    filterJobs();
}

function sortJobs() {
    const sortSelect = document.getElementById('sortSelect');
    if(!sortSelect) return;
    const sortValue = sortSelect.value;
    const container = document.querySelector('.jobs-container');
    
    let sortedCards = [...window.jobCards];
    
    if (sortValue === "date-asc") {
        sortedCards.sort((a, b) => new Date(a.getAttribute('data-date')) - new Date(b.getAttribute('data-date')));
    } else if (sortValue === "date-desc") {
        sortedCards.sort((a, b) => new Date(b.getAttribute('data-date')) - new Date(a.getAttribute('data-date')));
    } else if (sortValue === "title-asc") {
        sortedCards.sort((a, b) => a.getAttribute('data-title').localeCompare(b.getAttribute('data-title')));
    } else if (sortValue === "title-desc") {
        sortedCards.sort((a, b) => b.getAttribute('data-title').localeCompare(a.getAttribute('data-title')));
    } else if (sortValue === "keyword-asc") {
        sortedCards.sort((a, b) => a.getAttribute('data-keyword').localeCompare(b.getAttribute('data-keyword')));
    }
    
    sortedCards.forEach(card => container.appendChild(card));
}

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
            termOut.innerHTML += event.data + '\n';
            termWrapper.scrollTop = termWrapper.scrollHeight;
            
            // If a new job was matched, fetch the updated job list and total count
            if (event.data.includes("NEW Match")) {
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

function toggleTerminal() {
    const wrapper = document.getElementById('terminalOutputWrapper');
    const btn = document.getElementById('terminalToggleBtn');
    if (wrapper.style.display === 'none') {
        wrapper.style.display = 'block';
        btn.innerText = '▼';
    } else {
        wrapper.style.display = 'none';
        btn.innerText = '▲';
    }
}

function populateDropdowns() {
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
    if(negKeywordDropdown) {
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
            if(t.trim()) descTags.add(t.trim().toLowerCase());
        });
    });

    const descTagDropdown = document.getElementById('descTagDropdown');
    if(descTagDropdown) {
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
            if(t.trim()) negDescTags.add(t.trim().toLowerCase());
        });
    });

    const negDescTagDropdown = document.getElementById('negDescTagDropdown');
    if(negDescTagDropdown) {
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
    
    populateDropdowns();
    
    filterJobs(); // Initial count
    sortJobs();   // Initial sort based on default value
});
