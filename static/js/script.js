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
    const textFilter = document.getElementById('filterInput').value.toLowerCase();
    const keywordFilter = document.getElementById('keywordFilter').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    
    let visibleCount = 0;
    
    window.jobCards.forEach(card => {
        const title = card.getAttribute('data-title');
        const kws = card.getAttribute('data-keyword').toLowerCase();
        const isDone = card.classList.contains('done');
        
        let matchesText = title.includes(textFilter);
        let matchesKeyword = keywordFilter === "" || kws.includes(keywordFilter);
        
        let matchesStatus = true;
        if (statusFilter === 'done') matchesStatus = isDone;
        if (statusFilter === 'todo') matchesStatus = !isDone;
        
        if (matchesText && matchesKeyword && matchesStatus) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    document.getElementById('jobCountDisplay').innerText = `Total Offers: ${visibleCount}`;
}

document.addEventListener('DOMContentLoaded', () => {
    window.jobCards = Array.from(document.querySelectorAll('.job-card'));
    filterJobs(); // Initial count
});
