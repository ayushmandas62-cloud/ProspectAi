/* =============================================
   ProspectAI — Dashboard Application Logic
   ============================================= */

const API = '';

// ── State ────────────────────────────────────
let currentView = 'dashboard';
let selectedNiche = 'dental';
let currentLeadId = null;
let allLeads = [];

// ── DOM Ready ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSearch();
    initFilters();
    initExport();
    initModal();
    loadStats();
    loadLeads();
    checkApiStatus();
});

// ── Navigation ───────────────────────────────
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            switchView(view);
        });
    });

    document.getElementById('findLeadsBtn').addEventListener('click', () => switchView('search'));
}

function switchView(view) {
    currentView = view;

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`[data-view="${view}"]`).classList.add('active');

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`${view}View`).classList.add('active');

    const titles = { dashboard: 'Dashboard', search: 'Find Leads', leads: 'All Leads' };
    const subs = { dashboard: 'Welcome back, CodeSlayer', search: 'Discover new prospects', leads: 'Your complete lead database' };
    document.getElementById('pageTitle').textContent = titles[view] || 'Dashboard';
    document.getElementById('pageSubtitle').textContent = subs[view] || '';

    if (view === 'leads') loadAllLeads();
    if (view === 'dashboard') { loadStats(); loadLeads(); }
}

// ── API Status Check ─────────────────────────
async function checkApiStatus() {
    try {
        const res = await fetch(`${API}/api/status`);
        const data = await res.json();
        const badge = document.getElementById('apiStatusBadge');
        const dot = badge.querySelector('.status-dot');
        const text = badge.querySelector('.status-text');

        if (data.demo_mode) {
            dot.className = 'status-dot demo';
            text.textContent = 'Demo Mode';
        } else {
            dot.className = 'status-dot live';
            text.textContent = 'Live APIs';
        }
    } catch {
        const badge = document.getElementById('apiStatusBadge');
        badge.querySelector('.status-text').textContent = 'Offline';
    }
}

// ── Load Stats ───────────────────────────────
async function loadStats() {
    try {
        const res = await fetch(`${API}/api/stats`);
        const stats = await res.json();
        animateNumber('statTotal', stats.total);
        animateNumber('statHot', stats.hot);
        animateNumber('statWarm', stats.warm);
        animateNumber('statEmail', stats.with_email);
        animateNumber('statToday', stats.today);
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const duration = 600;
    const start = performance.now();

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(current + (target - current) * ease);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ── Load Leads (Dashboard) ───────────────────
async function loadLeads(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const res = await fetch(`${API}/api/leads?${params}`);
        const data = await res.json();
        allLeads = data.leads || [];
        renderLeadsTable('leadsTableBody', allLeads.slice(0, 20));
    } catch (e) {
        console.error('Failed to load leads:', e);
    }
}

// ── Load All Leads ───────────────────────────
async function loadAllLeads(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const res = await fetch(`${API}/api/leads?${params}`);
        const data = await res.json();
        renderLeadsTable('allLeadsBody', data.leads || []);
    } catch (e) {
        console.error('Failed to load all leads:', e);
    }
}

// ── Render Leads Table ───────────────────────
function renderLeadsTable(tbodyId, leads) {
    const tbody = document.getElementById(tbodyId);
    if (!leads.length) {
        tbody.innerHTML = `
            <tr class="empty-state">
                <td colspan="6">
                    <div class="empty-content">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                        <p>No leads found. Click <strong>"Find Leads"</strong> to start!</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = leads.map(lead => {
        const scoreClass = lead.score_label || 'cold';
        const scoreEmoji = { hot: '🔥', warm: '🟡', cold: '🔵' }[scoreClass] || '🔵';
        const nicheIcons = { dental: '🦷', law: '⚖️', realestate: '🏠' };

        return `
        <tr onclick="openLeadModal(${lead.id})" style="cursor:pointer">
            <td>
                <div class="lead-name">${escHtml(lead.business_name)}</div>
                <div class="lead-niche">${nicheIcons[lead.niche] || '📋'} ${lead.niche || 'Unknown'}</div>
            </td>
            <td>
                <div class="lead-email">${lead.email ? escHtml(lead.email) : '<span style="color:var(--text-muted)">No email</span>'}</div>
                <div class="lead-phone">${lead.phone ? escHtml(lead.phone) : ''}</div>
            </td>
            <td>${escHtml(lead.city || '')}${lead.state ? ', ' + escHtml(lead.state) : ''}</td>
            <td>${lead.rating ? '⭐ ' + lead.rating : '-'}</td>
            <td>
                <span class="score-number">${lead.score}</span>
                <span class="badge badge-${scoreClass}">${scoreEmoji} ${scoreClass.toUpperCase()}</span>
            </td>
            <td>
                <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openLeadModal(${lead.id})">View</button>
            </td>
        </tr>`;
    }).join('');
}

// ── Search ───────────────────────────────────
function initSearch() {
    // Niche selector
    document.querySelectorAll('.niche-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.niche-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedNiche = btn.dataset.niche;
        });
    });

    // Location chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.getElementById('searchLocation').value = chip.dataset.location;
        });
    });

    // Start search — use arrow function to prevent MouseEvent being passed as useDemo
    document.getElementById('startSearchBtn').addEventListener('click', () => startSearch());
}

async function startSearch(useDemo = false) {
    const location = document.getElementById('searchLocation').value.trim();
    const maxResults = parseInt(document.getElementById('searchMaxResults').value) || 15;

    if (!location) {
        showSearchError('Please enter a location.');
        return;
    }

    const progressEl = document.getElementById('searchProgress');
    const resultsEl = document.getElementById('searchResults');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');

    // Hide any previous errors
    hideSearchError();
    progressEl.classList.remove('hidden');
    resultsEl.classList.add('hidden');

    // Animate progress
    progressFill.style.width = '20%';
    progressText.textContent = useDemo
        ? `Generating demo leads for ${selectedNiche} in ${location}...`
        : `Searching Google Maps for ${selectedNiche} businesses in ${location}...`;

    setTimeout(() => {
        progressFill.style.width = '50%';
        progressText.textContent = useDemo ? 'Building lead profiles...' : 'Scraping business websites for contact info...';
    }, 1500);

    setTimeout(() => {
        progressFill.style.width = '75%';
        progressText.textContent = 'Scoring and ranking leads...';
    }, 3000);

    try {
        const res = await fetch(`${API}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                niche: selectedNiche,
                location: location,
                max_results: maxResults,
                use_demo: useDemo
            })
        });

        const data = await res.json();

        progressFill.style.width = '100%';

        setTimeout(() => {
            progressEl.classList.add('hidden');

            if (data.error) {
                showSearchError(data.error, data.can_use_demo);
                return;
            }

            const leads = data.results || [];
            const sourceTag = data.source === 'demo' ? ' (Demo Data)' : '';
            document.getElementById('resultsTitle').textContent = `Found ${leads.length} Leads in ${location}${sourceTag}`;
            document.getElementById('resultsCount').textContent = leads.length;
            renderLeadsTable('searchResultsBody', leads);
            resultsEl.classList.remove('hidden');

            // Refresh dashboard stats
            loadStats();
        }, 500);

    } catch (e) {
        progressEl.classList.add('hidden');
        showSearchError('Search failed. Is the backend running?', true);
        console.error(e);
    }
}

function showSearchError(message, canUseDemo = false) {
    // Remove existing error toast if any
    hideSearchError();

    const errorDiv = document.createElement('div');
    errorDiv.id = 'searchErrorToast';
    errorDiv.style.cssText = `
        background: linear-gradient(135deg, rgba(255,59,48,0.15), rgba(255,59,48,0.05));
        border: 1px solid rgba(255,59,48,0.3);
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0;
        color: #ff6b6b;
        font-size: 0.9rem;
        line-height: 1.6;
        animation: fadeSlideIn 0.3s ease;
    `;

    let html = `<div style="display:flex;align-items:flex-start;gap:12px;">
        <span style="font-size:1.4rem;margin-top:2px;">&#9888;</span>
        <div style="flex:1">
            <strong style="color:#ff8a8a;display:block;margin-bottom:6px;">Search Error</strong>
            <span style="color:#ccc;">${escHtml(message)}</span>`;

    if (canUseDemo) {
        html += `<div style="margin-top:14px;">
            <button onclick="startSearch(true)" style="
                background: linear-gradient(135deg, var(--accent), var(--accent-secondary));
                border: none; color: #fff; padding: 10px 24px;
                border-radius: 8px; cursor: pointer; font-weight: 600;
                font-size: 0.85rem; transition: transform 0.2s;
            " onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform='scale(1)'">
                Use Demo Data Instead
            </button>
            <span style="color:#888;margin-left:12px;font-size:0.8rem;">Try with realistic sample data</span>
        </div>`;
    }
    html += `</div></div>`;
    errorDiv.innerHTML = html;

    // Insert after the search progress/results area
    const searchPanel = document.querySelector('#searchView .search-panel') || document.getElementById('searchView');
    searchPanel.appendChild(errorDiv);
}

function hideSearchError() {
    const existing = document.getElementById('searchErrorToast');
    if (existing) existing.remove();
}

// ── Filters ──────────────────────────────────
function initFilters() {
    // Dashboard filters
    document.getElementById('filterNiche').addEventListener('change', (e) => {
        const filters = {};
        if (e.target.value) filters.niche = e.target.value;
        const scoreVal = document.getElementById('filterScore').value;
        if (scoreVal) filters.score_label = scoreVal;
        loadLeads(filters);
    });
    document.getElementById('filterScore').addEventListener('change', (e) => {
        const filters = {};
        if (e.target.value) filters.score_label = e.target.value;
        const nicheVal = document.getElementById('filterNiche').value;
        if (nicheVal) filters.niche = nicheVal;
        loadLeads(filters);
    });

    // All Leads filters
    document.getElementById('allFilterNiche').addEventListener('change', (e) => {
        const filters = {};
        if (e.target.value) filters.niche = e.target.value;
        const scoreVal = document.getElementById('allFilterScore').value;
        if (scoreVal) filters.score_label = scoreVal;
        loadAllLeads(filters);
    });
    document.getElementById('allFilterScore').addEventListener('change', (e) => {
        const filters = {};
        if (e.target.value) filters.score_label = e.target.value;
        const nicheVal = document.getElementById('allFilterNiche').value;
        if (nicheVal) filters.niche = nicheVal;
        loadAllLeads(filters);
    });

    // Clear All
    document.getElementById('clearAllBtn').addEventListener('click', async () => {
        if (!confirm('Delete ALL leads? This cannot be undone.')) return;
        await fetch(`${API}/api/leads/clear`, { method: 'POST' });
        loadAllLeads();
        loadStats();
    });
}

// ── Export ────────────────────────────────────
function initExport() {
    document.getElementById('exportBtn').addEventListener('click', () => {
        window.open(`${API}/api/export/csv`, '_blank');
    });
}

// ── Lead Modal ───────────────────────────────
function initModal() {
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('leadModal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });
    document.getElementById('modalEnrichBtn').addEventListener('click', enrichCurrentLead);
    document.getElementById('modalDeleteBtn').addEventListener('click', deleteCurrentLead);
}

async function openLeadModal(leadId) {
    currentLeadId = leadId;
    try {
        const res = await fetch(`${API}/api/leads/${leadId}`);
        const lead = await res.json();
        renderModal(lead);
        document.getElementById('leadModal').classList.remove('hidden');
    } catch (e) {
        console.error('Failed to load lead:', e);
    }
}

function renderModal(lead) {
    document.getElementById('modalTitle').textContent = lead.business_name;
    const scoreClass = lead.score_label || 'cold';
    const scoreEmoji = { hot: '🔥', warm: '🟡', cold: '🔵' }[scoreClass] || '🔵';

    const body = document.getElementById('modalBody');
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-item detail-full" style="text-align:center; padding-bottom:8px;">
                <span class="score-number" style="font-size:2rem">${lead.score}</span>
                <span class="badge badge-${scoreClass}" style="font-size:0.85rem;padding:6px 16px">${scoreEmoji} ${scoreClass.toUpperCase()}</span>
            </div>

            <div class="detail-divider"></div>

            <div class="detail-item">
                <label>Owner / Contact</label>
                <span>${lead.owner_name || '—'}</span>
            </div>
            <div class="detail-item">
                <label>Niche</label>
                <span>${lead.niche || '—'}</span>
            </div>
            <div class="detail-item">
                <label>Email</label>
                <span>${lead.email ? `<a href="mailto:${escHtml(lead.email)}">${escHtml(lead.email)}</a>` : '—'}</span>
            </div>
            <div class="detail-item">
                <label>Phone</label>
                <span>${lead.phone ? `<a href="tel:${escHtml(lead.phone)}">${escHtml(lead.phone)}</a>` : '—'}</span>
            </div>
            <div class="detail-item detail-full">
                <label>Website</label>
                <span>${lead.website ? `<a href="${escHtml(lead.website)}" target="_blank">${escHtml(lead.website)}</a>` : '—'}</span>
            </div>
            <div class="detail-item detail-full">
                <label>Address</label>
                <span>${lead.address || '—'}, ${lead.city || ''} ${lead.state || ''} ${lead.country || ''}</span>
            </div>

            <div class="detail-divider"></div>

            <div class="detail-item">
                <label>Rating</label>
                <span>${lead.rating ? '⭐ ' + lead.rating + ' (' + lead.review_count + ' reviews)' : '—'}</span>
            </div>
            <div class="detail-item">
                <label>Source</label>
                <span>${lead.source || '—'}</span>
            </div>

            <div class="detail-item">
                <label>Has Chatbot</label>
                <span>${lead.has_chatbot ? '✅ Yes' : '❌ No'}</span>
            </div>
            <div class="detail-item">
                <label>Has Booking</label>
                <span>${lead.has_booking ? '✅ Yes' : '❌ No'}</span>
            </div>
            <div class="detail-item">
                <label>Mobile Friendly</label>
                <span>${lead.is_mobile_friendly ? '✅ Yes' : '❌ No'}</span>
            </div>
            <div class="detail-item">
                <label>Enriched</label>
                <span>${lead.enriched ? '✅ AI Enriched' : '🔄 Not yet'}</span>
            </div>

            ${(lead.facebook || lead.instagram || lead.twitter || lead.linkedin) ? `
            <div class="detail-divider"></div>
            <div class="detail-item detail-full">
                <label>Social Media</label>
                <div class="social-row">
                    ${lead.facebook ? `<a class="social-link" href="${escHtml(lead.facebook)}" target="_blank">📘 Facebook</a>` : ''}
                    ${lead.instagram ? `<a class="social-link" href="${escHtml(lead.instagram)}" target="_blank">📸 Instagram</a>` : ''}
                    ${lead.twitter ? `<a class="social-link" href="${escHtml(lead.twitter)}" target="_blank">🐦 Twitter</a>` : ''}
                    ${lead.linkedin ? `<a class="social-link" href="${escHtml(lead.linkedin)}" target="_blank">💼 LinkedIn</a>` : ''}
                </div>
            </div>` : ''}

            ${lead.google_maps_url ? `
            <div class="detail-item detail-full">
                <label>Google Maps</label>
                <span><a href="${escHtml(lead.google_maps_url)}" target="_blank">Open in Google Maps ↗</a></span>
            </div>` : ''}
        </div>
    `;
}

function closeModal() {
    document.getElementById('leadModal').classList.add('hidden');
    currentLeadId = null;
}

async function enrichCurrentLead() {
    if (!currentLeadId) return;
    const btn = document.getElementById('modalEnrichBtn');
    btn.textContent = '⏳ Enriching...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API}/api/enrich/${currentLeadId}`, { method: 'POST' });
        const data = await res.json();
        if (data.error) {
            alert('Enrichment error: ' + data.error);
        } else {
            renderModal(data.lead);
            loadStats();
        }
    } catch (e) {
        alert('Enrichment failed. Check your Gemini API key.');
    }

    btn.textContent = '🤖 Enrich with AI';
    btn.disabled = false;
}

async function deleteCurrentLead() {
    if (!currentLeadId) return;
    if (!confirm('Delete this lead?')) return;

    await fetch(`${API}/api/leads/${currentLeadId}`, { method: 'DELETE' });
    closeModal();
    loadStats();
    loadLeads();
    if (currentView === 'leads') loadAllLeads();
}

// ── Utilities ────────────────────────────────
function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
