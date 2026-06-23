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

function toggleDone(btn, link) {
    const card = btn.closest('.job-card');
    const isCurrentlyDone = card.classList.contains('done');
    const newStatus = !isCurrentlyDone;
    
    btn.disabled = true;
    btn.innerText = "Updating...";
    
    fetch('/api/toggle_done', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            link: link,
            is_done: newStatus
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            if(newStatus) {
                card.classList.add('done');
                btn.innerText = "Undo Done";
            } else {
                card.classList.remove('done');
                btn.innerText = "✓ Mark as Done";
            }
            filterJobs(); // update counts and visibility if filtered
        } else {
            alert("Failed to update status.");
            btn.innerText = isCurrentlyDone ? "Undo Done" : "✓ Mark as Done";
        }
    })
    .catch(error => {
        console.error("Error toggling done status:", error);
        alert("Failed to update status due to network error.");
        btn.innerText = isCurrentlyDone ? "Undo Done" : "✓ Mark as Done";
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
    
    const kwTitle = document.getElementById('keywordSelectTitle');
    if (kwTitle) kwTitle.innerText = selectedKws.length > 0 ? `${selectedKws.length} Selected` : 'All Keywords';
    
    const negKwTitle = document.getElementById('negKeywordSelectTitle');
    if (negKwTitle) negKwTitle.innerText = selectedNegKws.length > 0 ? `${selectedNegKws.length} Selected` : 'All Negative Keywords';
    
    const statusSelect = document.getElementById('statusFilter');
    const statusFilter = statusSelect ? statusSelect.value : "";
    
    let visibleCount = 0;
    
    window.jobCards.forEach(card => {
        const title = card.getAttribute('data-title');
        const kws = card.getAttribute('data-keyword').toLowerCase();
        const isDone = card.classList.contains('done');
        
        const posKwsList = card.getAttribute('data-pos-keyword').split(',').map(s => s.trim());
        const negKwsList = card.getAttribute('data-neg-keyword').split(',').map(s => s.trim());
        
        let matchesText = title.includes(textFilter) || kws.includes(textFilter);
        let matchesKeyword = selectedKws.length === 0 || selectedKws.some(kw => posKwsList.includes(kw));
        // If negative keywords are selected, show jobs that DO NOT have ANY of the selected negative keywords
        let matchesNegKeyword = selectedNegKws.length === 0 || !selectedNegKws.some(kw => negKwsList.includes(kw));
        
        let matchesStatus = true;
        if (statusFilter === 'done') matchesStatus = isDone;
        if (statusFilter === 'undone') matchesStatus = !isDone;
        
        if (matchesText && matchesKeyword && matchesNegKeyword && matchesStatus) {
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
    const term = document.getElementById('terminalContainer');
    const termOut = document.getElementById('terminalOutput');
    const termWrapper = document.getElementById('terminalOutputWrapper');

    btn.disabled = true;
    btn.innerText = "Running...";
    term.style.display = 'block';
    termOut.innerHTML = 'Starting scraper...\n';

    const source = new EventSource('/api/run_scraper');

    source.onmessage = function (event) {
        if (event.data === "DONE") {
            source.close();
            btn.disabled = false;
            btn.innerText = "🔄 Refresh to see new jobs";
            btn.onclick = () => location.reload();
            termOut.innerHTML += '\nScraper finished. Please refresh the page to see new jobs.\n';
        } else {
            termOut.innerHTML += event.data + '\n';
            termWrapper.scrollTop = termWrapper.scrollHeight;
        }
    };

    source.onerror = function (event) {
        source.close();
        btn.disabled = false;
        btn.innerText = "🚀 Run Scraper";
        termOut.innerHTML += '\nError connecting to scraper stream.\n';
    };
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

document.addEventListener('DOMContentLoaded', () => {
    window.jobCards = Array.from(document.querySelectorAll('.job-card'));
    window.originalJobCards = [...window.jobCards];
    
    // Populate the keyword dropdowns
    const keywords = new Set();
    const negKeywords = new Set();
    
    const posBadges = document.querySelectorAll('.keyword-badge:not(.negative-badge)');
    posBadges.forEach(b => keywords.add(b.innerText.trim().toLowerCase()));
    
    const negBadges = document.querySelectorAll('.negative-badge');
    negBadges.forEach(b => negKeywords.add(b.innerText.trim().toLowerCase()));
    
    const keywordDropdown = document.getElementById('keywordDropdown');
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

    const negKeywordDropdown = document.getElementById('negKeywordDropdown');
    if(negKeywordDropdown) {
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
    
    filterJobs(); // Initial count
    sortJobs();   // Initial sort based on default value
});
