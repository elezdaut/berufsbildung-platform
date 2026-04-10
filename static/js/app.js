/* ============================================================
   BerufsbildungGlobal - Main Application JavaScript
   ============================================================ */

const API = {
    async fetch(url, options = {}) {
        try {
            const res = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                ...options
            });
            if (!res.ok && res.status >= 500) {
                showToast('Gabim serveri. Provo përsëri.', 'error');
                return { error: 'Server error' };
            }
            return res.json();
        } catch (e) {
            showToast('Gabim rrjeti. Kontrollo lidhjen.', 'error');
            return { error: 'Network error' };
        }
    },
    get: (url) => API.fetch(url),
    post: (url, data) => API.fetch(url, { method: 'POST', body: JSON.stringify(data) }),
    put: (url, data) => API.fetch(url, { method: 'PUT', body: JSON.stringify(data) }),
};

// ============================================================
// AUTH STATE
// ============================================================
let currentUser = null;

async function checkAuth() {
    const data = await API.get('/api/auth/me');
    if (data.authenticated) {
        currentUser = data.user;
        updateNavForUser();
    } else {
        currentUser = null;
        updateNavForGuest();
    }
    return currentUser;
}

function updateNavForUser() {
    const authNav = document.getElementById('auth-nav');
    if (authNav) {
        authNav.innerHTML = `
            <div style="position:relative; display:inline-flex;" id="notif-bell">
                <button onclick="toggleNotifications()" class="btn btn-ghost btn-sm" style="font-size:1.2rem; position:relative;">
                    🔔<span id="notif-badge" style="display:none; position:absolute; top:-2px; right:-2px; background:var(--accent); color:white; font-size:0.65rem; width:18px; height:18px; border-radius:50%; align-items:center; justify-content:center;"></span>
                </button>
                <div id="notif-dropdown" style="display:none; position:absolute; top:100%; right:0; width:350px; max-height:400px; overflow-y:auto; background:var(--white); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow-lg); z-index:100;"></div>
            </div>
            <span style="color: var(--text-light); font-size: 0.9rem;">Mirësevjen, <strong>${currentUser.full_name}</strong></span>
            <a href="/dashboard" class="btn btn-primary btn-sm">Dashboard</a>
            <button onclick="logout()" class="btn btn-ghost btn-sm">Dil</button>
        `;
        loadNotifications();
    }

    // Show chat link in nav
    const chatLink = document.getElementById('nav-chat-link');
    if (chatLink) chatLink.style.display = '';

    // Start polling chat unread count
    updateChatUnreadBadge();
    setInterval(updateChatUnreadBadge, 15000);
}

async function updateChatUnreadBadge() {
    const data = await API.get('/api/chat/unread');
    if (data.error) return;
    const badge = document.getElementById('nav-chat-unread');
    if (badge) {
        if (data.unread > 0) {
            badge.textContent = data.unread > 99 ? '99+' : data.unread;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

function updateNavForGuest() {
    const authNav = document.getElementById('auth-nav');
    if (authNav) {
        authNav.innerHTML = `
            <a href="/login" class="btn btn-outline btn-sm">Hyr</a>
            <a href="/register" class="btn btn-primary btn-sm">Regjistrohu</a>
        `;
    }
}

async function logout() {
    await API.post('/api/auth/logout');
    currentUser = null;
    window.location.href = '/';
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ============================================================
// MODAL
// ============================================================
function openModal(title, content) {
    let overlay = document.querySelector('.modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `<div class="modal"><div class="modal-header"><h2></h2><button class="modal-close" onclick="closeModal()">&times;</button></div><div class="modal-body"></div></div>`;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    }
    overlay.querySelector('h2').textContent = title;
    overlay.querySelector('.modal-body').innerHTML = content;
    requestAnimationFrame(() => overlay.classList.add('active'));
}

function closeModal() {
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) overlay.classList.remove('active');
}

// ============================================================
// INDEX PAGE - Load Stats & Positions
// ============================================================
async function loadIndexPage() {
    await checkAuth();
    loadStats();
    loadFeaturedPositions();
}

async function loadStats() {
    const stats = await API.get('/api/stats');
    const el = document.getElementById('hero-stats');
    if (el) {
        el.innerHTML = `
            <div class="hero-stat"><span class="hero-stat-number">${stats.total_professions}</span><span class="hero-stat-label">Profesione</span></div>
            <div class="hero-stat"><span class="hero-stat-number">${stats.total_positions}</span><span class="hero-stat-label">Pozicione të hapura</span></div>
            <div class="hero-stat"><span class="hero-stat-number">${stats.total_companies}</span><span class="hero-stat-label">Kompani partnere</span></div>
            <div class="hero-stat"><span class="hero-stat-number">${stats.total_students}</span><span class="hero-stat-label">Nxënës</span></div>
        `;
    }
}

async function loadFeaturedPositions() {
    const data = await API.get('/api/positions?per_page=6');
    const el = document.getElementById('featured-positions');
    if (!el) return;
    const positions = data.positions || data;
    el.innerHTML = positions.slice(0, 6).map(p => createPositionCard(p)).join('');
}

function createPositionCard(p) {
    const initials = p.company_name.split(' ').map(w => w[0]).join('').substring(0, 2);
    const salaryText = p.salary_monthly ? `${Number(p.salary_monthly).toLocaleString()} MKD/muaj` : 'Negociueshëm';

    return `
        <div class="position-card" onclick="showPositionDetail(${p.id})">
            <div class="position-header">
                <div class="position-company">
                    <div class="position-company-logo">${initials}</div>
                    <div>
                        <div style="font-weight:600; font-size:0.9rem;">${p.company_name}</div>
                        <div style="font-size:0.8rem; color:var(--text-light);">${p.industry || ''}</div>
                    </div>
                </div>
                <span class="badge badge-${p.qualification_type === 'EFZ' ? 'efz' : 'eba'}">${p.qualification_type} · ${p.duration_years} vjet</span>
            </div>
            <div class="position-title">${p.title}</div>
            <p style="font-size:0.9rem; color:var(--text-light); margin-bottom:0.75rem;">${(p.description || '').substring(0, 120)}...</p>
            <div class="position-meta">
                <span class="position-meta-item">📍 ${p.city || 'N/A'}</span>
                <span class="position-meta-item">📅 ${p.start_date || 'TBD'}</span>
                <span class="position-meta-item">👥 ${p.positions_available - (p.positions_filled || 0)} vende</span>
            </div>
            <div class="position-tags">
                <span class="tag">${p.profession_name}</span>
                <span class="tag">${p.category}</span>
            </div>
            <div style="margin-top:0.75rem; display:flex; justify-content:space-between; align-items:center;">
                <span class="position-salary">${salaryText}</span>
                <div style="display:flex; gap:0.5rem; align-items:center;">
                    <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); toggleFavorite(${p.id}, this)" title="Ruaj" style="font-size:1.1rem;">♡</button>
                    <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); applyToPosition(${p.id})">Apliko</button>
                </div>
            </div>
        </div>
    `;
}

// ============================================================
// POSITIONS PAGE
// ============================================================
async function loadPositionsPage() {
    await checkAuth();
    loadFilters();
    loadAllPositions();
}

async function loadFilters() {
    const [categories, cities] = await Promise.all([
        API.get('/api/professions/categories'),
        API.get('/api/cities')
    ]);

    const catEl = document.getElementById('filter-category');
    const cityEl = document.getElementById('filter-city');

    if (catEl) {
        catEl.innerHTML = '<option value="">Të gjitha kategoritë</option>' +
            categories.map(c => `<option value="${c}">${c}</option>`).join('');
    }
    if (cityEl) {
        cityEl.innerHTML = '<option value="">Të gjitha qytetet</option>' +
            cities.map(c => `<option value="${c}">${c}</option>`).join('');
    }
}

let currentPage = 1;
let currentSort = 'newest';

async function loadAllPositions(page) {
    if (page) currentPage = page;
    const search = document.getElementById('search-input')?.value || '';
    const category = document.getElementById('filter-category')?.value || '';
    const city = document.getElementById('filter-city')?.value || '';
    const sort = document.getElementById('sort-select')?.value || currentSort;
    currentSort = sort;

    let url = `/api/positions?search=${encodeURIComponent(search)}&page=${currentPage}&per_page=12&sort=${sort}`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const data = await API.get(url);
    const positions = data.positions || [];
    const el = document.getElementById('positions-list');
    if (!el) return;

    if (positions.length === 0) {
        el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><p>Nuk u gjetën pozicione. Provo filtra të tjerë.</p></div>';
        document.getElementById('positions-count').textContent = '0 pozicione';
        const pag = document.getElementById('pagination');
        if (pag) pag.innerHTML = '';
        return;
    }

    el.innerHTML = positions.map(p => createPositionCard(p)).join('');
    document.getElementById('positions-count').textContent = `${data.total} pozicione të gjetura (faqja ${data.page}/${data.total_pages})`;

    // Render pagination
    const pagEl = document.getElementById('pagination');
    if (pagEl && data.total_pages > 1) {
        let pagHTML = '';
        if (data.page > 1) pagHTML += `<button class="btn btn-outline btn-sm" onclick="loadAllPositions(${data.page - 1})">← Para</button>`;
        const start = Math.max(1, data.page - 2);
        const end = Math.min(data.total_pages, data.page + 2);
        for (let i = start; i <= end; i++) {
            pagHTML += `<button class="btn ${i === data.page ? 'btn-primary' : 'btn-outline'} btn-sm" onclick="loadAllPositions(${i})">${i}</button>`;
        }
        if (data.page < data.total_pages) pagHTML += `<button class="btn btn-outline btn-sm" onclick="loadAllPositions(${data.page + 1})">Tjetra →</button>`;
        pagEl.innerHTML = pagHTML;
    } else if (pagEl) {
        pagEl.innerHTML = '';
    }
}

function searchPositions() {
    currentPage = 1;
    loadAllPositions();
}

// ============================================================
// POSITION DETAIL
// ============================================================
async function showPositionDetail(positionId) {
    const p = await API.get(`/api/positions/${positionId}`);

    const weekDays = [];
    for (let i = 0; i < (p.company_days_per_week || 3); i++) {
        weekDays.push(`<div class="week-day week-day-company">${['Hë','Ma','Më','En','Pr'][i]}<span class="week-day-label">Kompani</span></div>`);
    }
    for (let i = 0; i < (p.school_days_per_week || 2); i++) {
        weekDays.push(`<div class="week-day week-day-school">${['Hë','Ma','Më','En','Pr'][p.company_days_per_week + i]}<span class="week-day-label">Shkollë</span></div>`);
    }

    const content = `
        <div style="margin-bottom:1.5rem;">
            <h3 style="font-size:1.2rem; margin-bottom:0.5rem;">${p.title}</h3>
            <p style="color:var(--text-light);">${p.company_name} · ${p.city}</p>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1.5rem;">
            <div class="card" style="padding:1rem;">
                <strong style="font-size:0.85rem; color:var(--text-light);">Profesioni</strong>
                <p>${p.profession_name}</p>
            </div>
            <div class="card" style="padding:1rem;">
                <strong style="font-size:0.85rem; color:var(--text-light);">Kohëzgjatja</strong>
                <p>${p.duration_years} vjet (${p.qualification_type})</p>
            </div>
            <div class="card" style="padding:1rem;">
                <strong style="font-size:0.85rem; color:var(--text-light);">Rroga mujore</strong>
                <p style="color:var(--secondary); font-weight:700;">${p.salary_monthly ? Number(p.salary_monthly).toLocaleString() + ' MKD' : 'Negociueshëm'}</p>
            </div>
            <div class="card" style="padding:1rem;">
                <strong style="font-size:0.85rem; color:var(--text-light);">Fillimi</strong>
                <p>${p.start_date || 'TBD'}</p>
            </div>
        </div>

        <h4 style="margin-bottom:0.5rem;">Orari javor</h4>
        <div class="week-schedule">${weekDays.join('')}</div>

        <h4 style="margin:1rem 0 0.5rem;">Përshkrimi</h4>
        <p style="color:var(--text-light); margin-bottom:1rem;">${p.description || ''}</p>

        <h4 style="margin-bottom:0.5rem;">Kërkesat</h4>
        <p style="color:var(--text-light); margin-bottom:1rem;">${p.requirements || ''}</p>

        <h4 style="margin-bottom:0.5rem;">Rreth kompanisë ${p.company_verified ? '<span style="color:var(--secondary); font-size:0.8rem;">✓ Verifikuar</span>' : ''}</h4>
        <p style="color:var(--text-light); margin-bottom:1rem;">${p.company_description || ''}</p>

        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
            ${p.company_user_id ? `<button class="btn btn-outline btn-sm" onclick="closeModal(); showCompanyProfile(${p.company_user_id})">👁 Profili i kompanisë</button>` : ''}
            ${p.website ? `<a href="${p.website}" target="_blank" class="btn btn-outline btn-sm">🌐 Websiti</a>` : ''}
            <button class="btn btn-primary" onclick="closeModal(); applyToPosition(${p.id})">Apliko tani</button>
        </div>
    `;

    openModal('Detajet e pozicionit', content);
}

async function applyToPosition(positionId) {
    if (!currentUser) {
        showToast('Duhet të hysh në llogari për të aplikuar', 'warning');
        window.location.href = '/login';
        return;
    }
    if (currentUser.role !== 'student') {
        showToast('Vetëm nxënësit mund të aplikojnë', 'error');
        return;
    }

    const content = `
        <form id="apply-form">
            <div class="form-group">
                <label>Letra motivuese</label>
                <textarea class="form-control" id="cover-letter" rows="5"
                    placeholder="Shkruaj pse je i/e interesuar për këtë pozicion..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Dërgo aplikimin</button>
        </form>
    `;

    openModal('Apliko për pozicion', content);

    document.getElementById('apply-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const coverLetter = document.getElementById('cover-letter').value;
        const result = await API.post('/api/applications', {
            position_id: positionId,
            cover_letter: coverLetter
        });

        if (result.success) {
            closeModal();
            showToast('Aplikimi u dërgua me sukses!', 'success');
        } else {
            showToast(result.error || 'Gabim gjatë aplikimit', 'error');
        }
    });
}

// ============================================================
// PROFESSIONS PAGE
// ============================================================
async function loadProfessionsPage() {
    await checkAuth();
    const [professions, categories] = await Promise.all([
        API.get('/api/professions'),
        API.get('/api/professions/categories')
    ]);

    renderCategoryFilter(categories);
    renderProfessions(professions);
}

function renderCategoryFilter(categories) {
    const el = document.getElementById('profession-categories');
    if (!el) return;

    el.innerHTML = `
        <button class="btn btn-primary btn-sm" onclick="filterProfessions('')">Të gjitha</button>
        ${categories.map(c => `<button class="btn btn-outline btn-sm" onclick="filterProfessions('${c}')">${c}</button>`).join('')}
    `;
}

async function filterProfessions(category) {
    const professions = await API.get(`/api/professions${category ? '?category=' + encodeURIComponent(category) : ''}`);
    renderProfessions(professions);
}

function renderProfessions(professions) {
    const el = document.getElementById('professions-list');
    if (!el) return;

    el.innerHTML = professions.map(p => {
        const skills = JSON.parse(p.skills_required || '[]');
        const desc = (p.description || '').substring(0, 100);
        return `
            <div class="card" style="cursor:pointer;" onclick="showProfessionDetail(${p.id})">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem;">
                    <div style="min-width:0; flex:1;">
                        <div class="card-title" style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${p.name_sq}</div>
                        <div class="card-subtitle" style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${p.name_en} · ${p.category}</div>
                    </div>
                    <span class="badge badge-${p.qualification_type === 'EFZ' ? 'efz' : 'eba'}">${p.qualification_type} · ${p.duration_years}v</span>
                </div>
                <p style="font-size:0.85rem; color:var(--text-light); margin:0.5rem 0; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${desc}${desc.length >= 100 ? '...' : ''}</p>
                <div class="week-schedule" style="margin:0.5rem 0;">
                    ${Array(p.company_days_per_week).fill('<div class="week-day week-day-company">K</div>').join('')}
                    ${Array(p.school_days_per_week).fill('<div class="week-day week-day-school">Sh</div>').join('')}
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:0.15rem; margin-top:0.5rem; max-height:52px; overflow:hidden;">
                    ${skills.slice(0, 3).map(s => `<span class="tag">${s}</span>`).join('')}
                    ${skills.length > 3 ? `<span class="tag">+${skills.length - 3}</span>` : ''}
                </div>
                ${p.salary_year1 ? `<div style="margin-top:0.5rem; font-size:0.8rem; color:var(--text-light); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">💰 ${Number(p.salary_year1).toLocaleString()} - ${Number(p.salary_year3 || p.salary_year2 || p.salary_year1).toLocaleString()} MKD/muaj</div>` : ''}
                <button class="btn btn-outline btn-sm" style="margin-top:0.5rem; font-size:0.75rem;" onclick="event.stopPropagation(); toggleCompare(${p.id}, '${p.name_sq.replace(/'/g, "\\'")}')">⚖ Krahaso</button>
            </div>
        `;
    }).join('');
}

async function showProfessionDetail(professionId) {
    const data = await API.get(`/api/professions/${professionId}`);
    const p = data.profession;
    const modules = data.curriculum;
    const positions = data.positions;
    const skills = JSON.parse(p.skills_required || '[]');

    // Group modules by year
    const byYear = {};
    modules.forEach(m => {
        if (!byYear[m.year]) byYear[m.year] = [];
        byYear[m.year].push(m);
    });

    const typeIcons = { theory: '📚', practical: '🔧', inter_company: '🏭' };
    const typeNames = { theory: 'Teori', practical: 'Praktikë', inter_company: 'Kurs ndërkompanish' };

    const content = `
        <div style="margin-bottom:1.5rem;">
            <span class="badge badge-${p.qualification_type === 'EFZ' ? 'efz' : 'eba'}" style="margin-bottom:0.5rem;">${p.qualification_type} · ${p.duration_years} vjet</span>
            <h3>${p.name_sq}</h3>
            <p style="color:var(--text-light);">${p.name_en} · ${p.category}</p>
        </div>

        <p style="margin-bottom:1rem;">${p.description}</p>

        <h4>Orari javor</h4>
        <div class="week-schedule" style="margin-bottom:1.5rem;">
            ${Array(p.company_days_per_week).fill(0).map((_, i) => `<div class="week-day week-day-company">${['Hë','Ma','Më','En','Pr'][i]}<span class="week-day-label">Kompani</span></div>`).join('')}
            ${Array(p.school_days_per_week).fill(0).map((_, i) => `<div class="week-day week-day-school">${['Hë','Ma','Më','En','Pr'][p.company_days_per_week + i]}<span class="week-day-label">Shkollë</span></div>`).join('')}
        </div>

        <h4>Aftësitë e kërkuara</h4>
        <div style="display:flex; flex-wrap:wrap; gap:0.25rem; margin:0.5rem 0 1.5rem;">
            ${skills.map(s => `<span class="tag">${s}</span>`).join('')}
        </div>

        ${Object.keys(byYear).length > 0 ? `
            <h4 style="margin-bottom:1rem;">Kurrikula</h4>
            ${Object.entries(byYear).map(([year, mods]) => `
                <div class="curriculum-year">
                    <h3>Viti ${year}</h3>
                    ${mods.map(m => `
                        <div class="module-item module-type-${m.module_type}">
                            <div class="module-type-icon">${typeIcons[m.module_type]}</div>
                            <div style="flex:1;">
                                <div style="font-weight:600; font-size:0.9rem;">${m.module_name}</div>
                                <div style="font-size:0.8rem; color:var(--text-light);">${m.description || ''}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-size:0.85rem; font-weight:600;">${m.hours}h</div>
                                <div style="font-size:0.75rem; color:var(--text-light);">${typeNames[m.module_type]}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `).join('')}
        ` : ''}

        ${positions.length > 0 ? `
            <h4 style="margin:1.5rem 0 0.75rem;">Pozicione të hapura (${positions.length})</h4>
            ${positions.map(pos => `
                <div class="card" style="margin-bottom:0.5rem; padding:1rem; cursor:pointer;" onclick="closeModal(); showPositionDetail(${pos.id})">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong>${pos.title}</strong>
                            <div style="font-size:0.85rem; color:var(--text-light);">${pos.company_name} · ${pos.city}</div>
                        </div>
                        <span class="btn btn-primary btn-sm">Shiko</span>
                    </div>
                </div>
            `).join('')}
        ` : '<p style="color:var(--text-light); margin-top:1rem;">Aktualisht nuk ka pozicione të hapura për këtë profesion.</p>'}
    `;

    openModal(p.name_sq, content);
}

// ============================================================
// LOGIN PAGE
// ============================================================
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    const result = await API.post('/api/auth/login', { email, password });

    if (result.success) {
        showToast('Hyrja u bë me sukses!', 'success');
        setTimeout(() => window.location.href = '/dashboard', 500);
    } else {
        showToast(result.error || 'Gabim gjatë hyrjes', 'error');
    }
}

// ============================================================
// REGISTER PAGE
// ============================================================
let selectedRole = 'student';

function selectRole(role, e) {
    selectedRole = role;
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    if (e && e.target) e.target.classList.add('active');

    const extraFields = document.getElementById('extra-fields');
    if (role === 'company') {
        extraFields.innerHTML = `
            <div class="form-group"><label>Emri i kompanisë</label><input class="form-control" id="reg-company-name" required></div>
            <div class="form-group"><label>Industria</label><input class="form-control" id="reg-industry"></div>
        `;
    } else if (role === 'school') {
        extraFields.innerHTML = `
            <div class="form-group"><label>Emri i shkollës</label><input class="form-control" id="reg-school-name" required></div>
        `;
    } else {
        extraFields.innerHTML = '';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const data = {
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        full_name: document.getElementById('reg-name').value,
        phone: document.getElementById('reg-phone')?.value || '',
        city: document.getElementById('reg-city')?.value || '',
        role: selectedRole,
    };

    if (selectedRole === 'company') data.company_name = document.getElementById('reg-company-name')?.value;
    if (selectedRole === 'school') data.school_name = document.getElementById('reg-school-name')?.value;

    const result = await API.post('/api/auth/register', data);

    if (result.success) {
        showToast('Regjistrimi u bë me sukses!', 'success');
        setTimeout(() => window.location.href = '/dashboard', 500);
    } else {
        showToast(result.error || 'Gabim gjatë regjistrimit', 'error');
    }
}

// ============================================================
// DASHBOARD
// ============================================================
async function loadDashboard() {
    const user = await checkAuth();
    if (!user) {
        window.location.href = '/login';
        return;
    }

    const data = await API.get('/api/dashboard');
    const main = document.getElementById('dashboard-content');
    if (!main) return;

    if (data.role === 'student') {
        renderStudentDashboard(main, data);
    } else if (data.role === 'company') {
        renderCompanyDashboard(main, data);
    } else if (data.role === 'school') {
        renderSchoolDashboard(main, data);
    } else if (data.role === 'government') {
        renderGovernmentDashboard(main);
    }
}

function renderStudentDashboard(el, data) {
    const apps = data.applications || [];
    const contracts = data.contracts || [];

    el.innerHTML = `
        <div class="dashboard-header">
            <h1>Dashboard i Nxënësit</h1>
            <p>Mirësevjen, ${currentUser.full_name}!</p>
        </div>

        <div class="stat-cards">
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--primary-light); color:var(--primary);">📄</div>
                <div class="stat-card-value">${apps.length}</div>
                <div class="stat-card-label">Aplikime të dërguara</div>
            </div>
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--secondary-light); color:var(--secondary);">✓</div>
                <div class="stat-card-value">${contracts.length}</div>
                <div class="stat-card-label">Kontrata aktive</div>
            </div>
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--warning-light); color:#92400e;">⏳</div>
                <div class="stat-card-value">${apps.filter(a => a.status === 'pending').length}</div>
                <div class="stat-card-label">Në pritje</div>
            </div>
            <div class="stat-card" style="cursor:pointer;" onclick="showCertificates()">
                <div class="stat-card-icon" style="background:#dbeafe; color:#1e40af;">🎓</div>
                <div class="stat-card-value">0</div>
                <div class="stat-card-label">Certifikata</div>
            </div>
        </div>

        <!-- Recommendations -->
        <div id="recommendations-section" style="margin-bottom:1.5rem;"></div>

        <!-- Contracts -->
        ${contracts.length > 0 ? `
        <div style="margin-bottom:1.5rem;">
            <h3 style="margin-bottom:1rem;">Kontratat aktive</h3>
            <div class="grid grid-2">
                ${contracts.map(c => `
                    <div class="card" style="border-left:4px solid var(--secondary);">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <div class="card-title">${c.profession_name}</div>
                                <div class="card-subtitle">${c.company_name}</div>
                            </div>
                            <span class="badge badge-secondary">Aktive</span>
                        </div>
                        <div class="position-meta" style="margin-top:0.5rem;">
                            <span class="position-meta-item">📅 ${c.start_date} — ${c.end_date}</span>
                        </div>
                        <div style="display:flex; gap:0.5rem; margin-top:0.75rem;">
                            <button class="btn btn-primary btn-sm" onclick="showProgress(${c.id})">Progresi</button>
                            <a href="/api/contracts/${c.id}/pdf" target="_blank" class="btn btn-outline btn-sm">📄 Kontrata PDF</a>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>` : ''}

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem;">
            <div>
                <h3 style="margin-bottom:1rem;">Aplikimet e fundit</h3>
                ${apps.length === 0 ? '<p style="color:var(--text-light);">Nuk keni aplikime ende. <a href="/positions">Gjej pozicione</a></p>' :
                apps.map(a => `
                    <div class="card" style="margin-bottom:0.75rem; padding:1rem; cursor:pointer;" onclick="showApplicationTimeline(${a.id}, '${(a.title||'').replace(/'/g, "\\'")}')">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="min-width:0; flex:1;">
                                <strong>${a.title}</strong>
                                <div style="font-size:0.85rem; color:var(--text-light);">${a.company_name}</div>
                            </div>
                            <span class="badge ${getStatusBadge(a.status)}">${getStatusText(a.status)}</span>
                        </div>
                        <div style="font-size:0.75rem; color:var(--primary); margin-top:0.25rem;">Kliko për historikun →</div>
                    </div>
                `).join('')}
            </div>
            <div>
                <h3 style="margin-bottom:1rem;">Veprime të shpejta</h3>
                <a href="/positions" class="card" style="display:block; margin-bottom:0.75rem; padding:1rem;">
                    <strong>🔍 Kërko pozicione</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Gjej apprenticeship të reja</p>
                </a>
                <a href="/professions" class="card" style="display:block; margin-bottom:0.75rem; padding:1rem;">
                    <strong>📚 Eksploro profesionet</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Mëso rreth profesioneve të ndryshme</p>
                </a>
                <div class="card" style="margin-bottom:0.75rem; padding:1rem; cursor:pointer;" onclick="showEditStudentProfile()">
                    <strong>👤 Ndrysho profilin</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Përditëso aftësitë, interesat, bio</p>
                </div>
            </div>
        </div>
    `;

    // Load recommendations
    loadRecommendations();

    // Load actual certificate count
    API.get('/api/certificates').then(certs => {
        if (Array.isArray(certs)) {
            const certCards = el.querySelectorAll('.stat-card');
            if (certCards[3]) certCards[3].querySelector('.stat-card-value').textContent = certs.length;
        }
    });
}

async function loadRecommendations() {
    const recs = await API.get('/api/recommendations');
    const el = document.getElementById('recommendations-section');
    if (!el || recs.length === 0) return;

    el.innerHTML = `
        <h3 style="margin-bottom:1rem;">Rekomandime për ty</h3>
        <div style="display:flex; gap:1rem; overflow-x:auto; padding-bottom:0.5rem;">
            ${recs.map(p => `
                <div class="card" style="min-width:280px; cursor:pointer;" onclick="showPositionDetail(${p.id})">
                    <div style="font-weight:600; font-size:0.95rem;">${p.title}</div>
                    <div style="font-size:0.85rem; color:var(--text-light);">${p.company_name} · ${p.city || ''}</div>
                    <div style="margin-top:0.5rem;"><span class="badge badge-${p.qualification_type === 'EFZ' ? 'efz' : 'eba'}">${p.qualification_type}</span> <span class="tag">${p.profession_name}</span></div>
                    ${p.salary_monthly ? `<div style="margin-top:0.5rem; color:var(--secondary); font-weight:700;">${Number(p.salary_monthly).toLocaleString()} MKD/muaj</div>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

function renderCompanyDashboard(el, data) {
    const positions = data.positions || [];

    el.innerHTML = `
        <div class="dashboard-header">
            <h1>Dashboard i Kompanisë</h1>
            <p>${data.profile?.company_name || currentUser.full_name}</p>
        </div>

        <div class="stat-cards">
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--primary-light); color:var(--primary);">📋</div>
                <div class="stat-card-value">${positions.length}</div>
                <div class="stat-card-label">Pozicione të postuara</div>
            </div>
            <div class="stat-card" style="cursor:pointer;" onclick="showCompanyApplications()">
                <div class="stat-card-icon" style="background:var(--warning-light); color:#92400e;">📨</div>
                <div class="stat-card-value">${data.applications_received || 0}</div>
                <div class="stat-card-label">Aplikime në pritje</div>
            </div>
            <div class="stat-card" style="cursor:pointer;" onclick="showContracts()">
                <div class="stat-card-icon" style="background:var(--secondary-light); color:var(--secondary);">👨‍🎓</div>
                <div class="stat-card-value">${data.active_apprentices || 0}</div>
                <div class="stat-card-label">Nxënës aktivë</div>
            </div>
        </div>

        ${data.applications_received > 0 ? `
        <div style="background:var(--warning-light); border:1px solid #fcd34d; border-radius:var(--radius); padding:1rem; margin-bottom:1.5rem; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong>📨 Keni ${data.applications_received} aplikime në pritje!</strong>
                <p style="font-size:0.85rem; color:#92400e;">Shqyrtoni aplikimet dhe pranoni kandidatët e duhur.</p>
            </div>
            <button class="btn btn-warning btn-sm" onclick="showCompanyApplications()">Shiko aplikimet</button>
        </div>` : ''}

        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <h3>Pozicionet tuaja</h3>
            <div style="display:flex; gap:0.5rem;">
                <button class="btn btn-outline btn-sm" onclick="showEditCompanyProfile()">Ndrysho profilin</button>
                <button class="btn btn-primary" onclick="showCreatePositionForm()">+ Krijo pozicion të ri</button>
            </div>
        </div>

        ${positions.length === 0 ? '<div class="empty-state"><p>Nuk keni pozicione ende. Krijoni pozicionin tuaj të parë!</p></div>' :
        `<div class="grid grid-2">
            ${positions.map(p => `
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div class="card-title">${p.title}</div>
                            <div class="card-subtitle">${p.profession_name}</div>
                        </div>
                        <span class="badge ${p.is_active ? 'badge-secondary' : 'badge-danger'}">${p.is_active ? 'Aktiv' : 'Joaktiv'}</span>
                    </div>
                    <div class="position-meta" style="margin-top:0.75rem;">
                        <span class="position-meta-item">👥 ${p.positions_available - (p.positions_filled || 0)} vende</span>
                        <span class="position-meta-item">📅 ${p.start_date || 'TBD'}</span>
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

async function renderSchoolDashboard(el, data) {
    const stats = await API.get('/api/stats');

    el.innerHTML = `
        <div class="dashboard-header">
            <h1>Dashboard i Shkollës</h1>
            <p>${data.profile?.school_name || currentUser.full_name}</p>
        </div>

        <div class="stat-cards">
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--primary-light); color:var(--primary);">👨‍🎓</div>
                <div class="stat-card-value">${stats.total_students || 0}</div>
                <div class="stat-card-label">Nxënës në sistem</div>
            </div>
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--secondary-light); color:var(--secondary);">📋</div>
                <div class="stat-card-value">${stats.total_positions || 0}</div>
                <div class="stat-card-label">Pozicione të hapura</div>
            </div>
            <div class="stat-card">
                <div class="stat-card-icon" style="background:var(--warning-light); color:#92400e;">📚</div>
                <div class="stat-card-value">${stats.total_professions || 0}</div>
                <div class="stat-card-label">Profesione</div>
            </div>
            <div class="stat-card">
                <div class="stat-card-icon" style="background:#dbeafe; color:#1e40af;">🎓</div>
                <div class="stat-card-value">${stats.total_certificates || 0}</div>
                <div class="stat-card-label">Certifikata</div>
            </div>
        </div>

        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card">
                <h3 style="margin-bottom:1rem;">Veprime të shpejta</h3>
                <a href="/positions" class="card" style="display:block; margin-bottom:0.75rem; padding:1rem; text-decoration:none;">
                    <strong>🔍 Shiko pozicionet</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Pozicionet e hapura për nxënësit</p>
                </a>
                <a href="/professions" class="card" style="display:block; margin-bottom:0.75rem; padding:1rem; text-decoration:none;">
                    <strong>📚 Profesionet</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Katalogu i profesioneve</p>
                </a>
                <a href="/chat" class="card" style="display:block; margin-bottom:0.75rem; padding:1rem;">
                    <strong>💬 Chat</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">Komuniko me kompanite dhe nxënësit</p>
                </a>
            </div>
            <div class="card">
                <h3 style="margin-bottom:1rem;">Rreth Sistemit Dual</h3>
                <p style="color:var(--text-light); margin-bottom:1rem;">BerufsbildungGlobal replikon sistemin zviceran të arsimit profesional dual.</p>
                <div style="padding:0.75rem; background:var(--bg); border-radius:var(--radius-sm); margin-bottom:0.5rem;">
                    <strong style="font-size:0.85rem;">Modeli javor:</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">3 ditë kompani + 2 ditë shkollë</p>
                </div>
                <div style="padding:0.75rem; background:var(--bg); border-radius:var(--radius-sm); margin-bottom:0.5rem;">
                    <strong style="font-size:0.85rem;">Kualifikimet:</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">EFZ (3-4 vjet) dhe EBA (2 vjet)</p>
                </div>
                <div style="padding:0.75rem; background:var(--bg); border-radius:var(--radius-sm);">
                    <strong style="font-size:0.85rem;">Korniza:</strong>
                    <p style="font-size:0.85rem; color:var(--text-light);">NQF/EQF niveli 3-5</p>
                </div>
            </div>
        </div>
    `;
}

async function showCreatePositionForm() {
    const professions = await API.get('/api/professions');

    const content = `
        <form id="create-position-form">
            <div class="form-group">
                <label>Profesioni</label>
                <select class="form-control" id="pos-profession" required>
                    <option value="">Zgjidh profesionin</option>
                    ${professions.map(p => `<option value="${p.id}">${p.name_sq} (${p.qualification_type} · ${p.duration_years} vjet)</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label>Titulli i pozicionit</label>
                <input class="form-control" id="pos-title" required placeholder="p.sh. Praktikant IT - Zhvillim Web">
            </div>
            <div class="form-group">
                <label>Përshkrimi</label>
                <textarea class="form-control" id="pos-description" placeholder="Përshkruaj pozicionin..."></textarea>
            </div>
            <div class="form-group">
                <label>Kërkesat</label>
                <input class="form-control" id="pos-requirements" placeholder="p.sh. Nxënës i shkollës së mesme">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                <div class="form-group">
                    <label>Numri i vendeve</label>
                    <input class="form-control" type="number" id="pos-slots" value="1" min="1">
                </div>
                <div class="form-group">
                    <label>Rroga mujore (MKD)</label>
                    <input class="form-control" type="number" id="pos-salary" placeholder="7000">
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                <div class="form-group">
                    <label>Data e fillimit</label>
                    <input class="form-control" type="date" id="pos-start">
                </div>
                <div class="form-group">
                    <label>Qyteti</label>
                    <input class="form-control" id="pos-city" placeholder="p.sh. Shkup">
                </div>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Publiko pozicionin</button>
        </form>
    `;

    openModal('Krijo pozicion të ri', content);

    document.getElementById('create-position-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const result = await API.post('/api/positions', {
            profession_id: parseInt(document.getElementById('pos-profession').value),
            title: document.getElementById('pos-title').value,
            description: document.getElementById('pos-description').value,
            requirements: document.getElementById('pos-requirements').value,
            positions_available: parseInt(document.getElementById('pos-slots').value),
            salary_monthly: parseFloat(document.getElementById('pos-salary').value) || null,
            start_date: document.getElementById('pos-start').value || null,
            city: document.getElementById('pos-city').value,
        });

        if (result.success) {
            closeModal();
            showToast('Pozicioni u krijua me sukses!', 'success');
            loadDashboard();
        } else {
            showToast(result.error || 'Gabim', 'error');
        }
    });
}

// ============================================================
// NOTIFICATIONS
// ============================================================
async function loadNotifications() {
    if (!currentUser) return;
    const data = await API.get('/api/notifications');
    const badge = document.getElementById('notif-badge');
    if (badge && data.unread_count > 0) {
        badge.style.display = 'flex';
        badge.textContent = data.unread_count;
    }
    window._notifications = data.notifications || [];
}

function toggleNotifications() {
    const dd = document.getElementById('notif-dropdown');
    if (!dd) return;
    const isVisible = dd.style.display !== 'none';
    dd.style.display = isVisible ? 'none' : 'block';

    if (!isVisible) {
        const notifs = window._notifications || [];
        dd.innerHTML = `
            <div style="padding:0.75rem 1rem; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:0.9rem;">Njoftimet</strong>
                <button class="btn btn-ghost btn-sm" onclick="markAllRead()" style="font-size:0.8rem;">Lexo te gjitha</button>
            </div>
            ${notifs.length === 0 ? '<div style="padding:2rem; text-align:center; color:var(--text-light);">Asnje njoftim</div>' :
            notifs.map(n => `
                <div style="padding:0.75rem 1rem; border-bottom:1px solid var(--border); background:${n.is_read ? 'transparent' : 'var(--primary-light)'}; cursor:pointer;" onclick="markNotifRead(${n.id})">
                    <div style="font-weight:${n.is_read ? '400' : '600'}; font-size:0.9rem;">${n.title}</div>
                    <div style="font-size:0.8rem; color:var(--text-light);">${n.message || ''}</div>
                    <div style="font-size:0.75rem; color:var(--text-light); margin-top:0.25rem;">${timeAgo(n.created_at)}</div>
                </div>
            `).join('')}
        `;
    }
}

async function markAllRead() {
    await API.post('/api/notifications/read-all');
    const badge = document.getElementById('notif-badge');
    if (badge) badge.style.display = 'none';
    window._notifications = (window._notifications || []).map(n => ({...n, is_read: 1}));
    toggleNotifications(); toggleNotifications(); // refresh
}

async function markNotifRead(id) {
    await API.put(`/api/notifications/${id}/read`);
    loadNotifications();
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'tani';
    if (diff < 3600) return `${Math.floor(diff/60)} min më parë`;
    if (diff < 86400) return `${Math.floor(diff/3600)} orë më parë`;
    return `${Math.floor(diff/86400)} ditë më parë`;
}

// ============================================================
// PROFILE EDITING
// ============================================================
async function showEditStudentProfile() {
    const data = await API.get('/api/dashboard');
    const p = data.profile || {};

    const interests = JSON.parse(p.interests || '[]');
    const skills = JSON.parse(p.skills || '[]');
    const languages = JSON.parse(p.languages || '[]');

    const content = `
        <form id="edit-profile-form">
            <div class="form-group"><label>Bio</label><textarea class="form-control" id="ep-bio" rows="3">${p.bio || ''}</textarea></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                <div class="form-group"><label>Data e lindjes</label><input type="date" class="form-control" id="ep-dob" value="${p.date_of_birth || ''}"></div>
                <div class="form-group"><label>GPA</label><input type="number" step="0.1" class="form-control" id="ep-gpa" value="${p.gpa || ''}" min="1" max="5"></div>
            </div>
            <div class="form-group"><label>Niveli arsimor</label><input class="form-control" id="ep-edu" value="${p.education_level || ''}"></div>
            <div class="form-group"><label>Shkolla</label><input class="form-control" id="ep-school" value="${p.school_name || ''}"></div>
            <div class="form-group"><label>Interesat (ndarë me presje)</label><input class="form-control" id="ep-interests" value="${interests.join(', ')}"></div>
            <div class="form-group"><label>Aftësitë (ndarë me presje)</label><input class="form-control" id="ep-skills" value="${skills.join(', ')}"></div>
            <div class="form-group"><label>Gjuhët (ndarë me presje)</label><input class="form-control" id="ep-langs" value="${languages.join(', ')}"></div>
            <button type="submit" class="btn btn-primary btn-block">Ruaj ndryshimet</button>
        </form>
    `;
    openModal('Ndrysho profilin', content);

    document.getElementById('edit-profile-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const toArr = v => v.split(',').map(s => s.trim()).filter(Boolean);
        const result = await API.put('/api/profile', {
            bio: document.getElementById('ep-bio').value,
            date_of_birth: document.getElementById('ep-dob').value,
            gpa: parseFloat(document.getElementById('ep-gpa').value) || null,
            education_level: document.getElementById('ep-edu').value,
            school_name: document.getElementById('ep-school').value,
            interests: toArr(document.getElementById('ep-interests').value),
            skills: toArr(document.getElementById('ep-skills').value),
            languages: toArr(document.getElementById('ep-langs').value),
        });
        if (result.success) { closeModal(); showToast('Profili u përditësua!', 'success'); loadDashboard(); }
    });
}

async function showEditCompanyProfile() {
    const data = await API.get('/api/dashboard');
    const p = data.profile || {};

    const content = `
        <form id="edit-company-form">
            <div class="form-group"><label>Emri i kompanisë</label><input class="form-control" id="ec-name" value="${p.company_name || ''}"></div>
            <div class="form-group"><label>Industria</label><input class="form-control" id="ec-industry" value="${p.industry || ''}"></div>
            <div class="form-group"><label>Madhësia</label>
                <select class="form-control" id="ec-size">
                    ${['1-10','11-50','51-200','201-500','500+'].map(s => `<option value="${s}" ${p.company_size===s?'selected':''}>${s} punonjës</option>`).join('')}
                </select>
            </div>
            <div class="form-group"><label>Përshkrimi</label><textarea class="form-control" id="ec-desc" rows="3">${p.description || ''}</textarea></div>
            <div class="form-group"><label>Website</label><input class="form-control" id="ec-web" value="${p.website || ''}"></div>
            <div class="form-group"><label>Adresa</label><input class="form-control" id="ec-addr" value="${p.address || ''}"></div>
            <button type="submit" class="btn btn-primary btn-block">Ruaj ndryshimet</button>
        </form>
    `;
    openModal('Ndrysho profilin e kompanisë', content);

    document.getElementById('edit-company-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const result = await API.put('/api/profile', {
            company_name: document.getElementById('ec-name').value,
            industry: document.getElementById('ec-industry').value,
            company_size: document.getElementById('ec-size').value,
            description: document.getElementById('ec-desc').value,
            website: document.getElementById('ec-web').value,
            address: document.getElementById('ec-addr').value,
        });
        if (result.success) { closeModal(); showToast('Profili u përditësua!', 'success'); loadDashboard(); }
    });
}

// ============================================================
// APPLICATION MANAGEMENT (Company)
// ============================================================
async function showCompanyApplications() {
    const apps = await API.get('/api/applications');
    const el = document.getElementById('dashboard-content');

    el.innerHTML = `
        <div class="dashboard-header">
            <h1>Aplikimet e marra</h1>
            <p>Menaxho aplikimet nga nxënësit</p>
        </div>
        ${apps.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📭</div><p>Nuk ka aplikime ende.</p></div>' :
        `<div class="grid grid-2">
            ${apps.map(a => `
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.75rem;">
                        <div>
                            <div class="card-title">${a.student_name || 'Nxënës'}</div>
                            <div class="card-subtitle">${a.title} · ${a.profession_name}</div>
                        </div>
                        <span class="badge ${getStatusBadge(a.status)}">${getStatusText(a.status)}</span>
                    </div>
                    ${a.school_name ? `<div style="font-size:0.85rem; color:var(--text-light); margin-bottom:0.5rem;">🏫 ${a.school_name}</div>` : ''}
                    <div style="font-size:0.85rem; color:var(--text-light); margin-bottom:0.75rem;">📅 Aplikuar: ${a.applied_at || ''}</div>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-outline btn-sm" onclick="viewStudentProfile(${a.id})">Shiko profilin</button>
                        ${a.status === 'pending' || a.status === 'interview' ? `
                            <button class="btn btn-secondary btn-sm" onclick="acceptApplication(${a.id})">Prano</button>
                            <button class="btn btn-danger btn-sm" onclick="rejectApplication(${a.id})">Refuzo</button>
                        ` : ''}
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

async function viewStudentProfile(appId) {
    const s = await API.get(`/api/applications/${appId}/student`);
    if (s.error) { showToast(s.error, 'error'); return; }

    const interests = JSON.parse(s.interests || '[]');
    const skills = JSON.parse(s.skills || '[]');
    const languages = JSON.parse(s.languages || '[]');

    const content = `
        <div style="text-align:center; margin-bottom:1.5rem;">
            <div style="width:80px; height:80px; border-radius:50%; background:var(--primary-light); color:var(--primary); display:flex; align-items:center; justify-content:center; font-size:2rem; font-weight:700; margin:0 auto 0.75rem;">
                ${(s.full_name || '?')[0]}
            </div>
            <h3>${s.full_name}</h3>
            <p style="color:var(--text-light);">${s.email} · ${s.phone || ''} · ${s.city || ''}</p>
        </div>
        ${s.bio ? `<p style="margin-bottom:1rem;">${s.bio}</p>` : ''}
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">Shkolla</strong><p style="font-size:0.9rem;">${s.school_name || 'N/A'}</p></div>
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">GPA</strong><p style="font-size:0.9rem;">${s.gpa || 'N/A'}</p></div>
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">Niveli</strong><p style="font-size:0.9rem;">${s.education_level || 'N/A'}</p></div>
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">Datëlindja</strong><p style="font-size:0.9rem;">${s.date_of_birth || 'N/A'}</p></div>
        </div>
        ${skills.length ? `<div style="margin-bottom:0.75rem;"><strong style="font-size:0.85rem;">Aftësitë:</strong><div style="margin-top:0.25rem;">${skills.map(s=>`<span class="tag">${s}</span>`).join(' ')}</div></div>` : ''}
        ${interests.length ? `<div style="margin-bottom:0.75rem;"><strong style="font-size:0.85rem;">Interesat:</strong><div style="margin-top:0.25rem;">${interests.map(i=>`<span class="tag">${i}</span>`).join(' ')}</div></div>` : ''}
        ${languages.length ? `<div><strong style="font-size:0.85rem;">Gjuhët:</strong><div style="margin-top:0.25rem;">${languages.map(l=>`<span class="badge badge-primary" style="margin:0.1rem;">${l}</span>`).join(' ')}</div></div>` : ''}
    `;
    openModal('Profili i nxënësit', content);
}

async function acceptApplication(appId) {
    if (!confirm('A jeni i sigurt që doni ta pranoni këtë aplikim? Do të krijohet kontratë automatikisht.')) return;
    const result = await API.post(`/api/applications/${appId}/accept`);
    if (result.success) {
        showToast(result.message, 'success');
        showCompanyApplications();
    } else {
        showToast(result.error || 'Gabim', 'error');
    }
}

async function rejectApplication(appId) {
    if (!confirm('A jeni i sigurt që doni ta refuzoni këtë aplikim?')) return;
    const result = await API.post(`/api/applications/${appId}/reject`);
    if (result.success) {
        showToast('Aplikimi u refuzua', 'info');
        showCompanyApplications();
    } else {
        showToast(result.error || 'Gabim', 'error');
    }
}

// ============================================================
// CONTRACTS & PROGRESS
// ============================================================
async function showContracts() {
    const contracts = await API.get('/api/contracts');
    const el = document.getElementById('dashboard-content');
    const isCompany = currentUser.role === 'company';

    el.innerHTML = `
        <div class="dashboard-header">
            <h1>Kontratat</h1>
            <p>${isCompany ? 'Nxënësit tuaj aktivë' : 'Kontratat tuaja të apprenticeship-it'}</p>
        </div>
        ${contracts.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📜</div><p>Nuk ka kontrata ende.</p></div>' :
        `<div class="grid grid-2">
            ${contracts.map(c => `
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.75rem;">
                        <div>
                            <div class="card-title">${c.profession_name}</div>
                            <div class="card-subtitle">${isCompany ? c.student_name : c.company_name}</div>
                        </div>
                        <span class="badge ${c.status === 'active' ? 'badge-secondary' : c.status === 'completed' ? 'badge-primary' : 'badge-danger'}">
                            ${c.status === 'active' ? 'Aktive' : c.status === 'completed' ? 'Përfunduar' : c.status}
                        </span>
                    </div>
                    <div class="position-meta">
                        <span class="position-meta-item">📅 ${c.start_date} — ${c.end_date}</span>
                        <span class="position-meta-item">⏱ ${c.duration_years} vjet</span>
                        ${c.salary_monthly ? `<span class="position-meta-item">💰 ${Number(c.salary_monthly).toLocaleString()} MKD</span>` : ''}
                    </div>
                    <div style="margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
                        <button class="btn btn-primary btn-sm" onclick="showProgress(${c.id})">Progresi</button>
                        <a href="/api/contracts/${c.id}/pdf" target="_blank" class="btn btn-outline btn-sm">📄 PDF</a>
                        ${c.status === 'active' && isCompany ? `<button class="btn btn-secondary btn-sm" onclick="generateCertificate(${c.id})">Certifikatë</button>` : ''}
                        ${c.status === 'active' && isCompany ? `<button class="btn btn-danger btn-sm" onclick="terminateContract(${c.id})">Termino</button>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

async function showProgress(contractId) {
    const data = await API.get(`/api/contracts/${contractId}/progress`);
    const isCompany = currentUser.role === 'company';

    const typeIcons = { theory: '📚', practical: '🔧', inter_company: '🏭' };
    const statusColors = { not_started: '#9ca3af', in_progress: '#f59e0b', completed: '#059669', failed: '#dc2626' };
    const statusText = { not_started: 'Jo filluar', in_progress: 'Në progres', completed: 'Përfunduar', failed: 'Dështuar' };

    // Group by year
    const byYear = {};
    (data.progress || []).forEach(p => {
        if (!byYear[p.year]) byYear[p.year] = [];
        byYear[p.year].push(p);
    });

    const content = `
        <div style="margin-bottom:1.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                <strong>${data.completed_modules}/${data.total_modules} module përfunduara</strong>
                <span style="font-weight:700; color:var(--primary);">${data.completion_percent}%</span>
            </div>
            <div class="progress-bar"><div class="progress-bar-fill" style="width:${data.completion_percent}%"></div></div>
        </div>

        ${Object.entries(byYear).map(([year, modules]) => `
            <div class="curriculum-year">
                <h3>Viti ${year}</h3>
                ${modules.map(m => `
                    <div class="module-item module-type-${m.module_type}" style="cursor:${isCompany ? 'pointer' : 'default'};" ${isCompany ? `onclick="editProgress(${m.id}, '${m.module_name.replace(/'/g, "\\'")}', '${m.status}', ${m.grade || 'null'})"` : ''}>
                        <div class="module-type-icon">${typeIcons[m.module_type] || '📄'}</div>
                        <div style="flex:1;">
                            <div style="font-weight:600; font-size:0.9rem;">${m.module_name}</div>
                            <div style="font-size:0.8rem; color:var(--text-light);">${m.module_desc || ''}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:0.8rem; font-weight:600; color:${statusColors[m.status]}">${statusText[m.status]}</div>
                            ${m.grade ? `<div style="font-size:0.85rem; font-weight:700; color:var(--primary);">Nota: ${m.grade}</div>` : ''}
                            <div style="font-size:0.75rem; color:var(--text-light);">${m.hours}h</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('')}

        ${isCompany ? '<p style="font-size:0.8rem; color:var(--text-light); margin-top:1rem;">Kliko mbi një modul për ta vlerësuar.</p>' : ''}
    `;

    openModal('Progresi i Apprenticeship-it', content);
}

async function editProgress(progressId, moduleName, currentStatus, currentGrade) {
    const content = `
        <form id="progress-form">
            <h4 style="margin-bottom:1rem;">${moduleName}</h4>
            <div class="form-group">
                <label>Statusi</label>
                <select class="form-control" id="prog-status">
                    <option value="not_started" ${currentStatus==='not_started'?'selected':''}>Jo filluar</option>
                    <option value="in_progress" ${currentStatus==='in_progress'?'selected':''}>Në progres</option>
                    <option value="completed" ${currentStatus==='completed'?'selected':''}>Përfunduar</option>
                    <option value="failed" ${currentStatus==='failed'?'selected':''}>Dështuar</option>
                </select>
            </div>
            <div class="form-group">
                <label>Nota (1-6)</label>
                <input type="number" class="form-control" id="prog-grade" min="1" max="6" step="0.1" value="${currentGrade || ''}">
            </div>
            <div class="form-group">
                <label>Shënime</label>
                <textarea class="form-control" id="prog-notes" rows="2"></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Ruaj</button>
        </form>
    `;
    openModal('Vlerëso modulin', content);

    document.getElementById('progress-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const result = await API.put(`/api/progress/${progressId}`, {
            status: document.getElementById('prog-status').value,
            grade: parseFloat(document.getElementById('prog-grade').value) || null,
            completion_date: new Date().toISOString().split('T')[0],
            evaluator_notes: document.getElementById('prog-notes').value,
        });
        if (result.success) { closeModal(); showToast('Moduli u vlerësua!', 'success'); }
    });
}

async function generateCertificate(contractId) {
    if (!confirm('A jeni i sigurt? Kjo kërkon që të gjitha modulet të jenë përfunduara.')) return;
    const result = await API.post(`/api/contracts/${contractId}/certificate`);
    if (result.success) {
        showToast(`Certifikata u krijua! Nr: ${result.certificate_number}`, 'success');
        showContracts();
    } else {
        showToast(result.error || 'Gabim', 'error');
    }
}

async function showCertificates() {
    const certs = await API.get('/api/certificates');
    const el = document.getElementById('dashboard-content');

    el.innerHTML = `
        <div class="dashboard-header"><h1>Certifikatat</h1><p>Diplomat tuaja profesionale</p></div>
        ${certs.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">🎓</div><p>Nuk keni certifikata ende. Përfundo apprenticeship-in për të marrë certifikatën.</p></div>' :
        `<div class="grid grid-2">
            ${certs.map(c => `
                <div class="card" style="border-left:4px solid var(--secondary);">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div class="card-title">🎓 ${c.profession_name}</div>
                            <div class="card-subtitle">${c.company_name}</div>
                        </div>
                        <span class="badge badge-efz">${c.certificate_type}</span>
                    </div>
                    <div style="margin-top:1rem; display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
                        <div><strong style="font-size:0.8rem; color:var(--text-light);">Nr. Certifikatës</strong><p style="font-size:0.9rem;">${c.certificate_number}</p></div>
                        <div><strong style="font-size:0.8rem; color:var(--text-light);">Nota finale</strong><p style="font-size:0.9rem; font-weight:700; color:var(--secondary);">${c.final_grade}</p></div>
                        <div><strong style="font-size:0.8rem; color:var(--text-light);">Data</strong><p style="font-size:0.9rem;">${c.issue_date}</p></div>
                        <div><strong style="font-size:0.8rem; color:var(--text-light);">NQF/EQF</strong><p style="font-size:0.9rem;">Niveli ${c.nqf_level}</p></div>
                    </div>
                    ${c.is_verified ? '<div style="margin-top:0.75rem; color:var(--secondary); font-size:0.85rem; font-weight:600;">✓ E verifikuar</div>' : ''}
                    <a href="/api/certificates/${c.id}/pdf" target="_blank" class="btn btn-primary btn-sm" style="margin-top:0.75rem; display:inline-block;">📥 Shkarko PDF</a>
                </div>
            `).join('')}
        </div>`}
    `;
}

// ============================================================
// FEATURE 1: i18n / MULTI-LANGUAGE
// ============================================================
let currentLang = localStorage.getItem('lang') || 'sq';
let translations = {};

async function loadTranslations(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    translations = await API.get(`/api/translations?lang=${lang}`);
    API.post('/api/translations', { lang });
    updateLanguageUI();
}

function t(key) { return translations[key] || key; }

function updateLanguageUI() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (translations[key]) el.textContent = translations[key];
    });
    // Update lang selector
    const sel = document.getElementById('lang-selector');
    if (sel) sel.value = currentLang;
}

function renderLanguageSelector() {
    return `<select id="lang-selector" onchange="loadTranslations(this.value)" class="form-control" style="width:auto; padding:0.3rem 0.5rem; font-size:0.8rem;">
        <option value="sq" ${currentLang==='sq'?'selected':''}>Shqip</option>
        <option value="mk" ${currentLang==='mk'?'selected':''}>Македонски</option>
        <option value="en" ${currentLang==='en'?'selected':''}>English</option>
    </select>`;
}

// ============================================================
// FEATURE 3: MESSAGING / CHAT
// ============================================================
async function showMessages() {
    const data = await API.get('/api/messages');
    const el = document.getElementById('dashboard-content');

    // Group by conversation
    const convos = {};
    (data.messages || []).forEach(m => {
        if (!convos[m.other_id]) convos[m.other_id] = { name: m.other_name, id: m.other_id, messages: [], unread: 0 };
        convos[m.other_id].messages.push(m);
        if (!m.is_read && m.receiver_id === currentUser.id) convos[m.other_id].unread++;
    });

    el.innerHTML = `
        <div class="dashboard-header"><h1>Mesazhet</h1><p>Komuniko me kompanite dhe nxenesit</p></div>
        ${Object.keys(convos).length === 0 ? '<div class="empty-state"><div class="empty-state-icon">💬</div><p>Nuk keni mesazhe ende.</p></div>' :
        `<div class="grid grid-2">
            ${Object.values(convos).map(c => `
                <div class="card" style="cursor:pointer;" onclick="showConversation(${c.id}, '${c.name.replace(/'/g, "\\'")}')">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div class="card-title">${c.name}</div>
                            <div class="card-subtitle" style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.messages[0]?.body || ''}</div>
                        </div>
                        ${c.unread > 0 ? `<span class="badge badge-danger">${c.unread}</span>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

async function showConversation(otherId, otherName) {
    const data = await API.get(`/api/messages/conversation/${otherId}`);

    const content = `
        <div style="max-height:300px; overflow-y:auto; margin-bottom:1rem; padding:0.5rem;" id="chat-messages">
            ${(data.messages || []).map(m => `
                <div style="margin-bottom:0.75rem; text-align:${m.sender_id === currentUser.id ? 'right' : 'left'};">
                    <div style="display:inline-block; max-width:80%; padding:0.5rem 0.75rem; border-radius:var(--radius-sm);
                        background:${m.sender_id === currentUser.id ? 'var(--primary)' : 'var(--bg)'};
                        color:${m.sender_id === currentUser.id ? 'white' : 'var(--text)'};">
                        <div style="font-size:0.9rem;">${m.body}</div>
                        <div style="font-size:0.7rem; opacity:0.7; margin-top:0.25rem;">${timeAgo(m.created_at)}</div>
                    </div>
                </div>
            `).join('')}
            ${data.messages.length === 0 ? '<p style="text-align:center; color:var(--text-light);">Filloni biseden...</p>' : ''}
        </div>
        <form id="chat-form" style="display:flex; gap:0.5rem;">
            <input class="form-control" id="chat-input" placeholder="Shkruaj mesazh..." required style="flex:1;">
            <button type="submit" class="btn btn-primary">Dergo</button>
        </form>
    `;

    openModal(`Chat me ${otherName}`, content);

    // Scroll to bottom
    const chatBox = document.getElementById('chat-messages');
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

    document.getElementById('chat-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = document.getElementById('chat-input').value;
        if (!body.trim()) return;
        await API.post('/api/messages', { receiver_id: otherId, body });
        document.getElementById('chat-input').value = '';
        // Refresh conversation
        closeModal();
        showConversation(otherId, otherName);
    });
}

async function startChat(userId, userName) {
    window.location.href = `/chat?with=${userId}`;
}

// ============================================================
// FEATURE 4: SCHEDULE / CALENDAR
// ============================================================
async function showSchedule() {
    const events = await API.get('/api/schedule');
    const contracts = await API.get('/api/contracts');
    const el = document.getElementById('dashboard-content');

    const days = ['E Hene', 'E Marte', 'E Merkure', 'E Enjte', 'E Premte'];
    const typeColors = { company: 'var(--secondary)', school: 'var(--primary)', exam: 'var(--accent)', inter_company: 'var(--warning)', other: 'var(--text-light)' };
    const typeBg = { company: 'var(--secondary-light)', school: 'var(--primary-light)', exam: 'var(--accent-light)', inter_company: 'var(--warning-light)', other: 'var(--bg)' };

    el.innerHTML = `
        <div class="dashboard-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><h1>Orari Javor</h1><p>Orari yt i apprenticeship-it</p></div>
                ${contracts.length > 0 ? `<button class="btn btn-primary btn-sm" onclick="autoGenerateSchedule(${contracts[0].id})">Gjenero orar automatik</button>` : ''}
            </div>
        </div>

        ${events.length === 0 ? `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <p>Nuk keni orar ende.${contracts.length > 0 ? ' Klikoni "Gjenero orar automatik" per te krijuar orarin javor.' : ' Filloni nje apprenticeship per te pasur orar.'}</p>
            </div>
        ` : `
            <div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:0.75rem;">
                ${days.map((day, i) => {
                    const dayEvents = events.filter(e => e.day_of_week === i);
                    return `
                        <div>
                            <div style="text-align:center; font-weight:700; padding:0.75rem; background:var(--bg); border-radius:var(--radius-sm) var(--radius-sm) 0 0; border-bottom:2px solid var(--primary);">${day}</div>
                            <div style="min-height:200px; background:var(--white); border:1px solid var(--border); border-radius:0 0 var(--radius-sm) var(--radius-sm); padding:0.5rem;">
                                ${dayEvents.length === 0 ? '<p style="text-align:center; color:var(--text-light); font-size:0.8rem; padding:1rem;">Lire</p>' :
                                dayEvents.map(e => `
                                    <div style="padding:0.5rem; margin-bottom:0.5rem; border-radius:var(--radius-sm); background:${typeBg[e.event_type] || typeBg.other}; border-left:3px solid ${typeColors[e.event_type] || typeColors.other};">
                                        <div style="font-weight:600; font-size:0.8rem; color:${typeColors[e.event_type] || typeColors.other};">${e.title}</div>
                                        <div style="font-size:0.75rem; color:var(--text-light);">${e.start_time || ''} - ${e.end_time || ''}</div>
                                        ${e.location ? `<div style="font-size:0.7rem; color:var(--text-light);">📍 ${e.location}</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>`;
                }).join('')}
            </div>
            <div style="display:flex; gap:1rem; margin-top:1rem; flex-wrap:wrap;">
                <span style="display:flex; align-items:center; gap:0.25rem; font-size:0.8rem;"><span style="width:12px; height:12px; border-radius:2px; background:var(--secondary-light); border:1px solid var(--secondary);"></span> Kompani</span>
                <span style="display:flex; align-items:center; gap:0.25rem; font-size:0.8rem;"><span style="width:12px; height:12px; border-radius:2px; background:var(--primary-light); border:1px solid var(--primary);"></span> Shkolle</span>
                <span style="display:flex; align-items:center; gap:0.25rem; font-size:0.8rem;"><span style="width:12px; height:12px; border-radius:2px; background:var(--accent-light); border:1px solid var(--accent);"></span> Provim</span>
            </div>
        `}
    `;
}

async function autoGenerateSchedule(contractId) {
    const result = await API.post(`/api/schedule/auto-generate/${contractId}`);
    if (result.success) { showToast(result.message, 'success'); showSchedule(); }
    else showToast(result.error || 'Gabim', 'error');
}

// ============================================================
// FEATURE 5: REVIEWS
// ============================================================
async function showReviewForm(contractId, reviewedId, reviewType) {
    const content = `
        <form id="review-form">
            <div class="form-group">
                <label>Vleresimi (1-5 yje)</label>
                <div id="star-rating" style="font-size:2rem; cursor:pointer;">
                    ${[1,2,3,4,5].map(i => `<span onclick="document.getElementById('review-rating').value=${i}; document.querySelectorAll('#star-rating span').forEach((s,j)=>s.style.color=j<${i}?'#f59e0b':'#d1d5db')" style="color:#d1d5db;">&#9733;</span>`).join('')}
                </div>
                <input type="hidden" id="review-rating" value="5">
            </div>
            <div class="form-group">
                <label>Komenti juaj</label>
                <textarea class="form-control" id="review-text" rows="3" placeholder="Shkruani pervojen tuaj..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Dergo vleresimin</button>
        </form>
    `;
    openModal('Lini nje vleresim', content);

    document.getElementById('review-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const result = await API.post('/api/reviews', {
            reviewed_id: reviewedId, review_type: reviewType, contract_id: contractId,
            rating: parseInt(document.getElementById('review-rating').value),
            review_text: document.getElementById('review-text').value,
        });
        if (result.success) { closeModal(); showToast('Vleresimi u dergua!', 'success'); }
        else showToast(result.error || 'Gabim', 'error');
    });
}

// ============================================================
// FEATURE 6: GOVERNMENT DASHBOARD
// ============================================================
async function renderGovernmentDashboard(el) {
    const data = await API.get('/api/admin/dashboard');

    const makeBar = (items, maxVal) => items.map(item => {
        const pct = maxVal > 0 ? (item.count / maxVal * 100) : 0;
        const label = item.city || item.category || item.status || item.company_name || '';
        return `<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
            <span style="width:120px; font-size:0.8rem; text-align:right;">${label}</span>
            <div style="flex:1; background:var(--border); border-radius:4px; height:24px;">
                <div style="width:${pct}%; background:linear-gradient(90deg, var(--primary), var(--secondary)); height:100%; border-radius:4px; min-width:30px; display:flex; align-items:center; justify-content:flex-end; padding-right:6px;">
                    <span style="font-size:0.75rem; color:white; font-weight:600;">${item.count}</span>
                </div>
            </div>
        </div>`;
    }).join('');

    el.innerHTML = `
        <div class="dashboard-header">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
                <div><h1>Dashboard i Qeverise</h1><p>Statistika kombetare te arsimit profesional</p></div>
                <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                    <a href="/api/admin/export/positions" class="btn btn-outline btn-sm" target="_blank">📥 Eksporto Pozicione</a>
                    <a href="/api/admin/export/contracts" class="btn btn-outline btn-sm" target="_blank">📥 Eksporto Kontrata</a>
                    <a href="/api/admin/export/students" class="btn btn-outline btn-sm" target="_blank">📥 Eksporto Nxënës</a>
                </div>
            </div>
        </div>

        <div class="stat-cards">
            <div class="stat-card"><div class="stat-card-icon" style="background:var(--primary-light); color:var(--primary);">👥</div><div class="stat-card-value">${data.total_users}</div><div class="stat-card-label">Perdorues total</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:var(--secondary-light); color:var(--secondary);">👨‍🎓</div><div class="stat-card-value">${data.total_students}</div><div class="stat-card-label">Nxenes</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:var(--warning-light); color:#92400e;">🏢</div><div class="stat-card-value">${data.total_companies}</div><div class="stat-card-label">Kompani</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:#dbeafe; color:#1e40af;">📋</div><div class="stat-card-value">${data.total_positions}</div><div class="stat-card-label">Pozicione</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:var(--accent-light); color:var(--accent);">📄</div><div class="stat-card-value">${data.total_applications}</div><div class="stat-card-label">Aplikime</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:var(--secondary-light); color:var(--secondary);">📜</div><div class="stat-card-value">${data.active_contracts}</div><div class="stat-card-label">Kontrata aktive</div></div>
            <div class="stat-card"><div class="stat-card-icon" style="background:#dbeafe; color:#1e40af;">🎓</div><div class="stat-card-value">${data.total_certificates}</div><div class="stat-card-label">Certifikata</div></div>
        </div>

        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card"><h3 style="margin-bottom:1rem;">Pozicione sipas qytetit</h3>${makeBar(data.positions_by_city, Math.max(...data.positions_by_city.map(x=>x.count),1))}</div>
            <div class="card"><h3 style="margin-bottom:1rem;">Pozicione sipas kategorise</h3>${makeBar(data.positions_by_category, Math.max(...data.positions_by_category.map(x=>x.count),1))}</div>
            <div class="card"><h3 style="margin-bottom:1rem;">Aplikime sipas statusit</h3>${makeBar(data.applications_by_status, Math.max(...(data.applications_by_status||[]).map(x=>x.count),1))}</div>
            <div class="card">
                <h3 style="margin-bottom:1rem;">Kompanite</h3>
                ${data.companies_ranked.map(c => `
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:0.5rem 0; border-bottom:1px solid var(--border);">
                        <div>
                            <strong style="font-size:0.9rem;">${c.company_name}</strong>
                            <span style="font-size:0.75rem; color:var(--text-light); margin-left:0.5rem;">${c.positions} pozicione</span>
                        </div>
                        <div style="display:flex; gap:0.25rem; align-items:center;">
                            ${c.is_verified ? '<span class="badge badge-secondary" style="font-size:0.7rem;">✓ Verifikuar</span>' :
                            `<button class="btn btn-primary btn-sm" style="font-size:0.7rem; padding:0.2rem 0.5rem;" onclick="verifyCompany(${c.id})">Verifiko</button>`}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// ============================================================
// FEATURE 7: EXAMS
// ============================================================
async function showExam(moduleId) {
    const exams = await API.get(`/api/exams/module/${moduleId}`);
    if (exams.length === 0) { showToast('Nuk ka provime per kete modul', 'info'); return; }

    const exam = exams[0];
    const data = await API.get(`/api/exams/${exam.id}`);

    const content = `
        <div style="margin-bottom:1rem;">
            <h3>${data.exam.title}</h3>
            <p style="color:var(--text-light);">${data.exam.description || ''} | Koha: ${data.exam.duration_minutes} min | Kalimi: ${data.exam.pass_grade}/6</p>
        </div>
        <form id="exam-form">
            ${data.questions.map((q, i) => `
                <div class="card" style="margin-bottom:1rem; padding:1rem;">
                    <div style="font-weight:600; margin-bottom:0.5rem;">${i+1}. ${q.question_text}</div>
                    ${q.question_type === 'multiple_choice' ? `
                        ${JSON.parse(q.options || '[]').map((opt, j) => `
                            <label style="display:block; padding:0.4rem; cursor:pointer; border-radius:var(--radius-sm);">
                                <input type="radio" name="q_${q.id}" value="${j}" style="margin-right:0.5rem;"> ${opt}
                            </label>
                        `).join('')}
                    ` : `
                        <textarea class="form-control" name="q_${q.id}" rows="3" placeholder="Shkruani pergjigjen..."></textarea>
                    `}
                </div>
            `).join('')}
            <button type="submit" class="btn btn-primary btn-block btn-lg">Dergo provimin</button>
        </form>
    `;
    openModal('Provim', content);

    document.getElementById('exam-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const answers = {};
        data.questions.forEach(q => {
            if (q.question_type === 'multiple_choice') {
                const checked = document.querySelector(`input[name="q_${q.id}"]:checked`);
                answers[q.id] = checked ? checked.value : '';
            } else {
                const ta = document.querySelector(`textarea[name="q_${q.id}"]`);
                answers[q.id] = ta ? ta.value : '';
            }
        });

        const result = await API.post(`/api/exams/${exam.id}/submit`, { answers });
        closeModal();

        const resultContent = `
            <div style="text-align:center; padding:1rem;">
                <div style="font-size:4rem; margin-bottom:1rem;">${result.passed ? '🎉' : '😔'}</div>
                <h3 style="color:${result.passed ? 'var(--secondary)' : 'var(--accent)'};">${result.passed ? 'Kalove!' : 'Nuk kalove'}</h3>
                <div style="font-size:2rem; font-weight:700; margin:1rem 0;">${result.score} / 6</div>
                <p style="color:var(--text-light);">Pike: ${result.earned_points} / ${result.total_points}</p>
            </div>
        `;
        openModal('Rezultati', resultContent);
    });
}

// ============================================================
// FEATURE 8: FILE UPLOADS
// ============================================================
async function showUploads() {
    const files = await API.get('/api/uploads');
    const el = document.getElementById('dashboard-content');

    const catNames = { cv: 'CV', diploma: 'Diplome', letter: 'Leter', certificate: 'Certifikate', other: 'Tjeter' };
    const catIcons = { cv: '📄', diploma: '🎓', letter: '✉️', certificate: '📜', other: '📎' };

    el.innerHTML = `
        <div class="dashboard-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><h1>Dokumentet e mia</h1><p>CV, diploma, letra rekomandimi</p></div>
                <button class="btn btn-primary" onclick="showUploadForm()">+ Ngarko dokument</button>
            </div>
        </div>
        ${files.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📁</div><p>Nuk keni dokumente. Ngarkoni CV-ne ose diplomen tuaj.</p></div>' :
        `<div class="grid grid-3">
            ${files.map(f => `
                <div class="card">
                    <div style="font-size:2rem; text-align:center; margin-bottom:0.5rem;">${catIcons[f.category] || '📎'}</div>
                    <div class="card-title" style="text-align:center; font-size:0.9rem;">${f.original_name}</div>
                    <div style="text-align:center; margin:0.5rem 0;">
                        <span class="badge badge-primary">${catNames[f.category] || f.category}</span>
                        <span style="font-size:0.75rem; color:var(--text-light); margin-left:0.5rem;">${(f.file_size / 1024).toFixed(0)} KB</span>
                    </div>
                    <div style="display:flex; gap:0.5rem; justify-content:center;">
                        <a href="/api/uploads/${f.file_name}" target="_blank" class="btn btn-outline btn-sm">Shiko</a>
                        <button class="btn btn-danger btn-sm" onclick="deleteFile(${f.id})">Fshij</button>
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

function showUploadForm() {
    const content = `
        <form id="upload-form" enctype="multipart/form-data">
            <div class="form-group">
                <label>Kategoria</label>
                <select class="form-control" id="upload-cat">
                    <option value="cv">CV</option>
                    <option value="diploma">Diplome</option>
                    <option value="letter">Leter rekomandimi</option>
                    <option value="certificate">Certifikate</option>
                    <option value="other">Tjeter</option>
                </select>
            </div>
            <div class="form-group">
                <label>Skedari (PDF, DOC, JPG, PNG - max 10MB)</label>
                <input type="file" class="form-control" id="upload-file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" required>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Ngarko</button>
        </form>
    `;
    openModal('Ngarko dokument', content);

    document.getElementById('upload-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('file', document.getElementById('upload-file').files[0]);
        formData.append('category', document.getElementById('upload-cat').value);

        const res = await fetch('/api/uploads', { method: 'POST', body: formData });
        const result = await res.json();

        if (result.success) { closeModal(); showToast('Dokumenti u ngarkua!', 'success'); showUploads(); }
        else showToast(result.error || 'Gabim', 'error');
    });
}

async function deleteFile(fileId) {
    if (!confirm('Fshij kete dokument?')) return;
    await API.fetch(`/api/uploads/${fileId}`, { method: 'DELETE' });
    showToast('Dokumenti u fshi', 'info');
    showUploads();
}

// ============================================================
// FEATURE 9: MENTORING
// ============================================================
async function showMentoring(contractId) {
    const data = await API.get(`/api/mentorships/${contractId}`);
    const isCompany = currentUser.role === 'company';

    if (!data.mentorship && isCompany) {
        // Assign mentor form
        const content = `
            <form id="mentor-form">
                <p style="margin-bottom:1rem;">Nuk ka mentor te caktuar per kete kontrate.</p>
                <div class="form-group"><label>Emri i mentorit</label><input class="form-control" id="mentor-name" value="${currentUser.full_name}"></div>
                <div class="form-group"><label>Roli</label><input class="form-control" id="mentor-role" value="Mentor"></div>
                <button type="submit" class="btn btn-primary btn-block">Cakto si mentor</button>
            </form>
        `;
        openModal('Cakto Mentor', content);
        document.getElementById('mentor-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await API.post('/api/mentorships', {
                contract_id: contractId,
                mentor_name: document.getElementById('mentor-name').value,
                mentor_role: document.getElementById('mentor-role').value,
            });
            closeModal(); showToast('Mentori u caktua!', 'success');
        });
        return;
    }

    const m = data.mentorship;
    const fb = data.feedback || [];

    const content = `
        <div style="margin-bottom:1.5rem; display:flex; align-items:center; gap:1rem;">
            <div style="width:50px; height:50px; background:var(--primary-light); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.5rem;">👨‍🏫</div>
            <div>
                <div style="font-weight:700;">${m ? m.mentor_name || m.mentor_full_name : 'Pa mentor'}</div>
                <div style="font-size:0.85rem; color:var(--text-light);">${m ? m.mentor_role : ''}</div>
            </div>
        </div>

        ${isCompany ? `
            <form id="feedback-form" style="margin-bottom:1.5rem; padding:1rem; background:var(--bg); border-radius:var(--radius);">
                <h4 style="margin-bottom:0.75rem;">Shto feedback javor</h4>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem;">
                    <div class="form-group"><label>Java nr.</label><input type="number" class="form-control" id="fb-week" min="1" value="${fb.length + 1}"></div>
                    <div class="form-group"><label>Vleresimi (1-5)</label><input type="number" class="form-control" id="fb-rating" min="1" max="5" value="4"></div>
                </div>
                <div class="form-group"><label>Feedback</label><textarea class="form-control" id="fb-text" rows="2" placeholder="Si performoi nxenesi kete jave?"></textarea></div>
                <div class="form-group"><label>Fushat per permiresim</label><input class="form-control" id="fb-improve" placeholder="p.sh. Komunikimi, puntualiteti"></div>
                <button type="submit" class="btn btn-primary btn-sm">Ruaj feedback</button>
            </form>
        ` : ''}

        <h4 style="margin-bottom:0.75rem;">Historiku i feedback-ut</h4>
        ${fb.length === 0 ? '<p style="color:var(--text-light);">Nuk ka feedback ende.</p>' :
        fb.map(f => `
            <div class="card" style="margin-bottom:0.5rem; padding:0.75rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>Java ${f.week_number}</strong>
                    <span>${'⭐'.repeat(f.rating || 0)}</span>
                </div>
                <p style="font-size:0.9rem; margin-top:0.25rem;">${f.feedback_text}</p>
                ${f.areas_of_improvement ? `<p style="font-size:0.8rem; color:var(--text-light);">Permiresim: ${f.areas_of_improvement}</p>` : ''}
            </div>
        `).join('')}
    `;
    openModal('Mentorimi', content);

    if (isCompany && m) {
        document.getElementById('feedback-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await API.post(`/api/mentorships/${m.id}/feedback`, {
                week_number: parseInt(document.getElementById('fb-week').value),
                feedback_text: document.getElementById('fb-text').value,
                areas_of_improvement: document.getElementById('fb-improve').value,
                rating: parseInt(document.getElementById('fb-rating').value),
            });
            closeModal(); showToast('Feedback u ruajt!', 'success');
        });
    }
}

// ============================================================
// UPDATE DASHBOARD SIDEBAR for new features
// ============================================================
function updateDashboardSidebar() {
    const roleNav = document.getElementById('sidebar-role-nav');
    if (!roleNav || !currentUser) return;

    if (currentUser.role === 'student') {
        roleNav.innerHTML = `
            <li><a href="#" onclick="loadDashboard(); return false;">📊 Pamja</a></li>
            <li><a href="#" onclick="showFavorites(); return false;">♥ Të ruajturat</a></li>
            <li><a href="#" onclick="showContracts(); return false;">📜 Kontratat</a></li>
            <li><a href="#" onclick="showSchedule(); return false;">📅 Orari</a></li>
            <li><a href="/chat">💬 Chat</a></li>
            <li><a href="#" onclick="showUploads(); return false;">📁 Dokumentet</a></li>
            <li><a href="#" onclick="showCertificates(); return false;">🎓 Certifikatat</a></li>
            <li><a href="#" onclick="showEditStudentProfile(); return false;">👤 Profili</a></li>
            <li><a href="#" onclick="showChangePassword(); return false;">🔑 Fjalëkalimi</a></li>
        `;
    } else if (currentUser.role === 'company') {
        roleNav.innerHTML = `
            <li><a href="#" onclick="loadDashboard(); return false;">📊 Pamja</a></li>
            <li><a href="#" onclick="showCompanyApplications(); return false;">📨 Aplikimet</a></li>
            <li><a href="#" onclick="showContracts(); return false;">👨‍🎓 Nxenesit</a></li>
            <li><a href="/chat">💬 Chat</a></li>
            <li><a href="#" onclick="showEditCompanyProfile(); return false;">🏢 Profili</a></li>
            <li><a href="#" onclick="showChangePassword(); return false;">🔑 Fjalëkalimi</a></li>
        `;
    } else if (currentUser.role === 'school') {
        roleNav.innerHTML = `
            <li><a href="#" onclick="loadDashboard(); return false;">📊 Pamja</a></li>
            <li><a href="/chat">💬 Chat</a></li>
            <li><a href="/positions">📋 Pozicionet</a></li>
            <li><a href="/professions">📚 Profesionet</a></li>
        `;
    } else if (currentUser.role === 'government') {
        roleNav.innerHTML = `
            <li><a href="#" onclick="renderGovernmentDashboard(document.getElementById('dashboard-content')); return false;">📊 Statistikat</a></li>
            <li><a href="/positions">📋 Pozicionet</a></li>
            <li><a href="/professions">📚 Profesionet</a></li>
        `;
    }
}

// ============================================================
// CONTRACT TERMINATION
// ============================================================
async function terminateContract(contractId) {
    const reason = prompt('Arsyeja e terminimit (opsionale):');
    if (reason === null) return; // cancelled
    const result = await API.post(`/api/contracts/${contractId}/terminate`, { reason });
    if (result.success) {
        showToast(result.message, 'info');
        showContracts();
    } else {
        showToast(result.error || 'Gabim', 'error');
    }
}

// ============================================================
// COMPANY VERIFICATION (Government)
// ============================================================
async function verifyCompany(companyId) {
    if (!confirm('A jeni i sigurt që doni ta verifikoni këtë kompani?')) return;
    const result = await API.post(`/api/admin/verify-company/${companyId}`);
    if (result.success) {
        showToast(result.message, 'success');
        renderGovernmentDashboard(document.getElementById('dashboard-content'));
    } else {
        showToast(result.error || 'Gabim', 'error');
    }
}

// ============================================================
// FAVORITES
// ============================================================
async function toggleFavorite(positionId, btn) {
    if (!currentUser) { showToast('Duhet të hysh në llogari', 'warning'); return; }
    const result = await API.post('/api/favorites', { position_id: positionId });
    if (result.success) {
        if (btn) btn.textContent = result.favorited ? '♥' : '♡';
        if (btn) btn.style.color = result.favorited ? 'var(--accent)' : '';
        showToast(result.message, 'success');
    }
}

async function showFavorites() {
    const favs = await API.get('/api/favorites');
    const el = document.getElementById('dashboard-content');
    el.innerHTML = `
        <div class="dashboard-header"><h1>Pozicionet e ruajtura</h1><p>Pozicionet që ke shënuar si të preferuara</p></div>
        ${!favs.length ? '<div class="empty-state"><div class="empty-state-icon">♡</div><p>Nuk ke pozicione të ruajtura. Kliko ♡ tek pozicionet për t\'i ruajtur.</p></div>' :
        `<div class="grid grid-2">
            ${favs.map(f => `
                <div class="card" style="cursor:pointer;" onclick="showPositionDetail(${f.position_id})">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div style="min-width:0; flex:1;">
                            <div class="card-title">${f.title}</div>
                            <div class="card-subtitle">${f.company_name} · ${f.city || ''}</div>
                        </div>
                        <span class="badge badge-${f.qualification_type === 'EFZ' ? 'efz' : 'eba'}">${f.qualification_type}</span>
                    </div>
                    <div class="position-meta" style="margin-top:0.5rem;">
                        <span class="position-meta-item">${f.profession_name}</span>
                        ${f.salary_monthly ? `<span class="position-meta-item">💰 ${Number(f.salary_monthly).toLocaleString()} MKD</span>` : ''}
                    </div>
                    <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
                        <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); applyToPosition(${f.position_id})">Apliko</button>
                        <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); toggleFavorite(${f.position_id}); this.closest('.card').remove();">Hiq</button>
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
}

// ============================================================
// APPLICATION TIMELINE
// ============================================================
async function showApplicationTimeline(appId, title) {
    const timeline = await API.get(`/api/applications/${appId}/timeline`);
    const statusIcons = { pending: '📄', reviewed: '👀', interview: '🤝', accepted: '✅', rejected: '❌' };
    const statusNames = { pending: 'Në pritje', reviewed: 'Shqyrtuar', interview: 'Intervistë', accepted: 'Pranuar', rejected: 'Refuzuar' };

    const content = `
        <div style="margin-bottom:1rem;"><strong>${title || 'Aplikimi'}</strong></div>
        ${timeline.length === 0 ? '<p style="color:var(--text-light);">Nuk ka historik.</p>' :
        `<div style="position:relative; padding-left:2rem;">
            <div style="position:absolute; left:10px; top:0; bottom:0; width:2px; background:var(--border);"></div>
            ${timeline.map(h => `
                <div style="position:relative; margin-bottom:1.25rem;">
                    <div style="position:absolute; left:-2rem; top:2px; width:20px; height:20px; border-radius:50%; background:var(--white); border:2px solid var(--primary); display:flex; align-items:center; justify-content:center; font-size:0.6rem;">
                        ${statusIcons[h.new_status] || '📌'}
                    </div>
                    <div style="background:var(--bg); padding:0.75rem; border-radius:var(--radius-sm);">
                        <div style="font-weight:600; font-size:0.9rem;">${statusNames[h.new_status] || h.new_status}</div>
                        ${h.note ? `<div style="font-size:0.85rem; color:var(--text-light); margin-top:0.25rem;">${h.note}</div>` : ''}
                        <div style="font-size:0.75rem; color:var(--text-light); margin-top:0.25rem;">${timeAgo(h.created_at)}${h.changed_by_name ? ' · ' + h.changed_by_name : ''}</div>
                    </div>
                </div>
            `).join('')}
        </div>`}
    `;
    openModal('Historiku i aplikimit', content);
}

// ============================================================
// COMPANY PUBLIC PROFILE
// ============================================================
async function showCompanyProfile(companyUserId) {
    const data = await API.get(`/api/companies/${companyUserId}/profile`);
    if (data.error) { showToast(data.error, 'error'); return; }
    const c = data.company;
    const stars = data.avg_rating ? '⭐'.repeat(Math.round(data.avg_rating)) : 'Pa vlerësime';

    const content = `
        <div style="text-align:center; margin-bottom:1.5rem;">
            <div style="width:70px; height:70px; border-radius:var(--radius); background:var(--primary-light); color:var(--primary); display:flex; align-items:center; justify-content:center; font-size:1.8rem; font-weight:700; margin:0 auto 0.75rem;">
                ${(c.company_name || '?')[0]}
            </div>
            <h3>${c.company_name}</h3>
            <p style="color:var(--text-light);">${c.industry || ''} · ${c.city || ''}</p>
            ${c.is_verified ? '<div style="color:var(--secondary); font-size:0.85rem; font-weight:600; margin-top:0.25rem;">✓ E verifikuar</div>' : ''}
            ${data.avg_rating ? `<div style="margin-top:0.5rem;">${stars} (${data.avg_rating}/5 · ${data.total_reviews} vlerësime)</div>` : ''}
        </div>
        ${c.description ? `<p style="margin-bottom:1rem;">${c.description}</p>` : ''}
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin-bottom:1rem;">
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">Madhësia</strong><p style="font-size:0.9rem;">${c.company_size || 'N/A'}</p></div>
            <div class="card" style="padding:0.75rem;"><strong style="font-size:0.8rem; color:var(--text-light);">Website</strong><p style="font-size:0.9rem;">${c.website ? `<a href="${c.website}" target="_blank">${c.website}</a>` : 'N/A'}</p></div>
        </div>

        ${data.positions.length > 0 ? `
            <h4 style="margin-bottom:0.75rem;">Pozicione të hapura (${data.positions.length})</h4>
            ${data.positions.map(p => `
                <div class="card" style="margin-bottom:0.5rem; padding:0.75rem; cursor:pointer;" onclick="closeModal(); showPositionDetail(${p.id})">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div><strong>${p.title}</strong><div style="font-size:0.8rem; color:var(--text-light);">${p.profession_name} · ${p.qualification_type}</div></div>
                        <span class="btn btn-primary btn-sm">Shiko</span>
                    </div>
                </div>
            `).join('')}
        ` : ''}

        ${data.reviews.length > 0 ? `
            <h4 style="margin:1rem 0 0.75rem;">Vlerësimet (${data.total_reviews})</h4>
            ${data.reviews.map(r => `
                <div class="card" style="margin-bottom:0.5rem; padding:0.75rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="font-size:0.9rem;">${r.reviewer_name}</strong>
                        <span>${'⭐'.repeat(r.rating)}</span>
                    </div>
                    ${r.review_text ? `<p style="font-size:0.85rem; color:var(--text-light); margin-top:0.25rem;">${r.review_text}</p>` : ''}
                </div>
            `).join('')}
        ` : ''}
    `;
    openModal(c.company_name, content);
}

// ============================================================
// PROFESSION COMPARISON
// ============================================================
let compareList = [];

function toggleCompare(profId, name) {
    const idx = compareList.findIndex(c => c.id === profId);
    if (idx > -1) {
        compareList.splice(idx, 1);
        showToast(`${name} u hoq nga krahasimi`, 'info');
    } else if (compareList.length >= 4) {
        showToast('Maksimum 4 profesione për krahasim', 'warning');
        return;
    } else {
        compareList.push({ id: profId, name });
        showToast(`${name} u shtua për krahasim (${compareList.length})`, 'success');
    }
    updateCompareBar();
}

function updateCompareBar() {
    let bar = document.getElementById('compare-bar');
    if (compareList.length === 0) {
        if (bar) bar.remove();
        return;
    }
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'compare-bar';
        bar.style.cssText = 'position:fixed; bottom:0; left:0; right:0; background:var(--white); border-top:2px solid var(--primary); padding:0.75rem 2rem; z-index:1500; display:flex; justify-content:space-between; align-items:center; box-shadow:0 -2px 10px rgba(0,0,0,0.1);';
        document.body.appendChild(bar);
    }
    bar.innerHTML = `
        <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
            <strong style="font-size:0.85rem;">Krahasim:</strong>
            ${compareList.map(c => `<span class="badge badge-primary">${c.name} <span style="cursor:pointer; margin-left:0.25rem;" onclick="toggleCompare(${c.id}, '${c.name.replace(/'/g, "\\'")}')">&times;</span></span>`).join('')}
        </div>
        <button class="btn btn-primary btn-sm" onclick="showComparison()" ${compareList.length < 2 ? 'disabled style="opacity:0.5;"' : ''}>Krahaso (${compareList.length})</button>
    `;
}

async function showComparison() {
    if (compareList.length < 2) return;
    const ids = compareList.map(c => c.id).join(',');
    const profs = await API.get(`/api/professions/compare?ids=${ids}`);
    if (profs.error) { showToast(profs.error, 'error'); return; }

    const fields = [
        { key: 'qualification_type', label: 'Kualifikimi' },
        { key: 'duration_years', label: 'Kohëzgjatja', suffix: ' vjet' },
        { key: 'company_days_per_week', label: 'Ditë kompani', suffix: '/javë' },
        { key: 'school_days_per_week', label: 'Ditë shkollë', suffix: '/javë' },
        { key: 'salary_year1', label: 'Rroga viti 1', format: v => v ? Number(v).toLocaleString() + ' MKD' : 'N/A' },
        { key: 'salary_year3', label: 'Rroga viti 3', format: v => v ? Number(v).toLocaleString() + ' MKD' : 'N/A' },
        { key: 'total_modules', label: 'Module totale' },
        { key: 'total_hours', label: 'Orë totale', suffix: 'h' },
        { key: 'open_positions', label: 'Pozicione të hapura' },
    ];

    const content = `
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
                <thead>
                    <tr style="border-bottom:2px solid var(--primary);">
                        <th style="text-align:left; padding:0.75rem 0.5rem;">Aspekti</th>
                        ${profs.map(p => `<th style="text-align:center; padding:0.75rem 0.5rem;">${p.name_sq}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom:1px solid var(--border);">
                        <td style="padding:0.5rem; font-weight:600;">Kategoria</td>
                        ${profs.map(p => `<td style="text-align:center; padding:0.5rem;"><span class="tag">${p.category}</span></td>`).join('')}
                    </tr>
                    ${fields.map(f => `
                        <tr style="border-bottom:1px solid var(--border);">
                            <td style="padding:0.5rem; font-weight:600;">${f.label}</td>
                            ${profs.map(p => {
                                const val = p[f.key];
                                const display = f.format ? f.format(val) : (val != null ? val + (f.suffix || '') : 'N/A');
                                return `<td style="text-align:center; padding:0.5rem;">${display}</td>`;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    openModal('Krahasimi i profesioneve', content);
}

// ============================================================
// PASSWORD CHANGE
// ============================================================
function showChangePassword() {
    const content = `
        <form id="pw-form">
            <div class="form-group">
                <label>Fjalëkalimi aktual</label>
                <input type="password" class="form-control" id="pw-old" required>
            </div>
            <div class="form-group">
                <label>Fjalëkalimi i ri</label>
                <input type="password" class="form-control" id="pw-new" required minlength="6">
            </div>
            <div class="form-group">
                <label>Konfirmo fjalëkalimin e ri</label>
                <input type="password" class="form-control" id="pw-confirm" required minlength="6">
            </div>
            <button type="submit" class="btn btn-primary btn-block">Ndrysho fjalëkalimin</button>
        </form>
    `;
    openModal('Ndrysho fjalëkalimin', content);

    document.getElementById('pw-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPw = document.getElementById('pw-new').value;
        const confirm = document.getElementById('pw-confirm').value;
        if (newPw !== confirm) {
            showToast('Fjalëkalimet nuk përputhen!', 'error');
            return;
        }
        const result = await API.post('/api/auth/change-password', {
            old_password: document.getElementById('pw-old').value,
            new_password: newPw
        });
        if (result.success) {
            closeModal();
            showToast(result.message, 'success');
        } else {
            showToast(result.error || 'Gabim', 'error');
        }
    });
}

// ============================================================
// HELPERS
// ============================================================
function getStatusBadge(status) {
    const map = { pending: 'badge-warning', reviewed: 'badge-primary', interview: 'badge-primary', accepted: 'badge-secondary', rejected: 'badge-danger' };
    return map[status] || 'badge-primary';
}

function getStatusText(status) {
    const map = { pending: 'Në pritje', reviewed: 'Shqyrtuar', interview: 'Intervistë', accepted: 'Pranuar', rejected: 'Refuzuar' };
    return map[status] || status;
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    // Load saved language on page load
    const savedLang = localStorage.getItem('lang');
    if (savedLang && savedLang !== 'sq') {
        loadTranslations(savedLang);
    }
});
