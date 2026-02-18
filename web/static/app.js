/* ═══════════════════════════════════════════════════════════════════════════
   Pokémon SpriteGen — Frontend App Logic
   ═══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let selectedType = null;

    // ─── Tab Switching ─────────────────────────────────────────────────
    const tabs = document.querySelectorAll('.tab');
    const panels = document.querySelectorAll('.panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const mode = tab.dataset.mode;
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`panel-${mode}`).classList.add('active');
        });
    });

    // ─── Load Gallery Thumbnails ───────────────────────────────────────
    loadGallery();

    async function loadGallery() {
        try {
            const resp = await fetch('/api/sprites');
            const sprites = await resp.json();
            sprites.forEach(sprite => {
                const img = document.getElementById(`img-${sprite.name}`);
                if (img && sprite.thumbnail) {
                    img.src = sprite.thumbnail;
                }
            });
        } catch (err) {
            console.error('Failed to load gallery:', err);
        }
    }

    // ─── Slider Values ────────────────────────────────────────────────
    function setupSlider(sliderId, valueId) {
        const slider = document.getElementById(sliderId);
        const valueDisplay = document.getElementById(valueId);
        if (slider && valueDisplay) {
            slider.addEventListener('input', () => {
                valueDisplay.textContent = slider.value;
            });
        }
    }
    setupSlider('shiny-count', 'shiny-count-val');
    setupSlider('sheet-cols', 'sheet-cols-val');
    setupSlider('sheet-rows', 'sheet-rows-val');

    // ─── Type Buttons ──────────────────────────────────────────────────
    const typeButtons = document.querySelectorAll('.type-btn');
    typeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            typeButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedType = btn.dataset.type;
        });
    });
    // Select first type by default
    if (typeButtons.length > 0) {
        typeButtons[0].click();
    }

    // ─── Shiny Generation ──────────────────────────────────────────────
    document.getElementById('btn-gen-shiny')?.addEventListener('click', async () => {
        const source = document.getElementById('shiny-source').value;
        const count = document.getElementById('shiny-count').value;
        const hueInput = document.getElementById('shiny-hue').value;
        const satInput = document.getElementById('shiny-sat').value;

        const body = { source, count: parseInt(count) };
        if (hueInput) body.hue_shift = parseFloat(hueInput);
        if (satInput) body.sat_shift = parseFloat(satInput);

        showLoading('Generating shinies...');
        try {
            const resp = await fetch('/api/generate/shiny', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('shiny-results');
            container.innerHTML = '';

            data.variants.forEach((variant, idx) => {
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.animationDelay = `${idx * 0.08}s`;
                card.innerHTML = `
                    <img src="${variant.image}" alt="${variant.label}">
                    <div class="result-label">${variant.label}</div>
                    <div class="result-meta">H: ${variant.hue_shift}° S: ${variant.sat_shift}×</div>
                `;
                container.appendChild(card);
            });

            showToast(`✨ Generated ${data.variants.length} shiny variants!`, 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── Palette Swap ──────────────────────────────────────────────────
    document.getElementById('btn-gen-palette')?.addEventListener('click', async () => {
        const source = document.getElementById('palette-source').value;
        const target = document.getElementById('palette-target').value;

        if (source === target) {
            showToast('Pick two different Pokémon!', 'error');
            return;
        }

        showLoading('Swapping palette...');
        try {
            const resp = await fetch('/api/generate/palette-swap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, target }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('palette-results');
            container.innerHTML = `
                <div class="result-card">
                    <img src="${data.source.image}" alt="${data.source.name}">
                    <div class="result-label">${capitalize(data.source.name)}</div>
                    <div class="result-meta">Source shape</div>
                </div>
                <div class="result-card">
                    <img src="${data.target.image}" alt="${data.target.name}">
                    <div class="result-label">${capitalize(data.target.name)}</div>
                    <div class="result-meta">Target colors</div>
                </div>
                <div class="result-card" style="border-color: var(--accent-2);">
                    <img src="${data.result.image}" alt="Result">
                    <div class="result-label">✨ Result</div>
                    <div class="result-meta">${data.result.label}</div>
                </div>
            `;

            showToast('🎨 Palette swap complete!', 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── Type Swap ─────────────────────────────────────────────────────
    document.getElementById('btn-gen-type')?.addEventListener('click', async () => {
        const source = document.getElementById('type-source').value;
        if (!selectedType) {
            showToast('Select a type first!', 'error');
            return;
        }

        showLoading(`Applying ${selectedType} type...`);
        try {
            const resp = await fetch('/api/generate/type-swap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, type: selectedType }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('type-results');
            container.innerHTML = `
                <div class="result-card">
                    <img src="${data.source.image}" alt="${data.source.name}">
                    <div class="result-label">${capitalize(data.source.name)}</div>
                    <div class="result-meta">Original</div>
                </div>
                <div class="swap-result-arrow">→</div>
                <div class="result-card" style="border-color: var(--type-${data.type});">
                    <img src="${data.result.image}" alt="Result">
                    <div class="result-label">✨ ${capitalize(data.type)} Type</div>
                    <div class="result-meta">${data.result.label}</div>
                </div>
            `;

            showToast(`🔥 Applied ${selectedType} type palette!`, 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── Spritesheet ───────────────────────────────────────────────────
    document.getElementById('btn-gen-sheet')?.addEventListener('click', async () => {
        const cols = document.getElementById('sheet-cols').value;
        const rows = document.getElementById('sheet-rows').value;

        showLoading('Building spritesheet...');
        try {
            const resp = await fetch('/api/generate/spritesheet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sprites: [],  // Empty = use all available
                    cols: parseInt(cols),
                    rows: parseInt(rows),
                }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('sheet-results');
            container.innerHTML = `
                <div class="result-card sheet-result">
                    <img src="${data.image}" alt="Spritesheet">
                    <div class="result-label">Spritesheet (${data.width}×${data.height})</div>
                    <div class="result-meta">${data.count} sprites in ${cols}×${rows} grid</div>
                </div>
            `;

            showToast('📋 Spritesheet assembled!', 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── Download More Sprites ─────────────────────────────────────────
    document.getElementById('btn-download-more')?.addEventListener('click', downloadMore);

    async function downloadMore() {
        const btn = document.getElementById('btn-download-more');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> Downloading...';
        showLoading('Downloading sprites from pokemondb.net...');

        try {
            const resp = await fetch('/api/download-more', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: 10 }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            showToast(`↓ ${data.message}`, 'success');

            // Reload page to show new sprites
            if (data.downloaded > 0) {
                setTimeout(() => window.location.reload(), 1500);
            }
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }

        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">↓</span> Download More';
        hideLoading();
    }
    // Make downloadMore available globally for the empty-state button
    window.downloadMore = downloadMore;

    // ─── Gallery Pokédex Info ──────────────────────────────────────────
    document.querySelectorAll('.sprite-card').forEach(card => {
        card.addEventListener('click', async () => {
            const name = card.dataset.name;
            try {
                const resp = await fetch(`/api/pokemon/${name}`);
                const data = await resp.json();
                if (data.error) return;

                // Show Pokédex panel
                const panel = document.getElementById('pokedex-panel');
                panel.style.display = 'block';

                // Sprite image
                const spriteImg = document.getElementById('pokedex-sprite');
                if (data.image) spriteImg.src = data.image;

                // Name & species
                document.getElementById('pokedex-name').textContent =
                    `#${data.id} ${capitalize(data.name)}`;
                document.getElementById('pokedex-species').textContent =
                    data.species || '';

                // Type badges
                const typesEl = document.getElementById('pokedex-types');
                typesEl.innerHTML = (data.types || []).map(t =>
                    `<span class="pokedex-type-badge" style="background: var(--type-${t})">${t}</span>`
                ).join('');

                // Stat bars
                const statsEl = document.getElementById('pokedex-stats');
                const stats = data.base_stats || {};
                const maxStat = 255;
                statsEl.innerHTML = Object.entries(stats).map(([k, v]) =>
                    `<div class="stat-row">
                        <span class="stat-name">${k}</span>
                        <div class="stat-bar-wrap">
                            <div class="stat-bar ${k}" style="width: ${(v / maxStat) * 100}%"></div>
                        </div>
                        <span class="stat-val">${v}</span>
                    </div>`
                ).join('');

                // Meta info
                const metaEl = document.getElementById('pokedex-meta');
                metaEl.innerHTML = `
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Body Style</span>
                        <span class="pokedex-meta-value">${data.body_style || '—'}</span>
                    </div>
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Height</span>
                        <span class="pokedex-meta-value">${data.height}m</span>
                    </div>
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Weight</span>
                        <span class="pokedex-meta-value">${data.weight}kg</span>
                    </div>
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Abilities</span>
                        <span class="pokedex-meta-value">${(data.abilities || []).join(', ')}</span>
                    </div>
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Egg Groups</span>
                        <span class="pokedex-meta-value">${(data.egg_groups || []).join(', ')}</span>
                    </div>
                    <div class="pokedex-meta-item">
                        <span class="pokedex-meta-label">Generation</span>
                        <span class="pokedex-meta-value">Gen ${data.gen}</span>
                    </div>
                `;

                // Smooth scroll to panel
                panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } catch (err) {
                console.error('Pokédex fetch:', err);
            }
        });
    });

    // ─── Stat Shiny Generation ─────────────────────────────────────────
    document.getElementById('btn-gen-stat-shiny')?.addEventListener('click', async () => {
        const source = document.getElementById('stat-shiny-source').value;
        showLoading('Generating stat-influenced shiny...');

        try {
            const resp = await fetch('/api/generate/stat-shiny', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('stat-shiny-results');
            container.innerHTML = `
                <div class="stat-info-card">
                    <div>
                        <div class="stat-info-label">Dominant Stat</div>
                        <div class="stat-info-value">${data.dominant_stat}</div>
                    </div>
                    <div>
                        <div class="stat-info-label">Hue Shift</div>
                        <div class="stat-info-value">${data.hue_shift}°</div>
                    </div>
                    <div>
                        <div class="stat-info-label">Saturation</div>
                        <div class="stat-info-value">${data.saturation}×</div>
                    </div>
                </div>
                <div class="result-card">
                    <img src="${data.source.image}" alt="${data.source.name}">
                    <div class="result-label">${capitalize(data.source.name)}</div>
                    <div class="result-meta">Original</div>
                </div>
                <div class="swap-result-arrow">→</div>
                <div class="result-card" style="border-color: var(--accent-2);">
                    <img src="${data.result.image}" alt="Stat Shiny">
                    <div class="result-label">✨ Stat Shiny</div>
                    <div class="result-meta">${data.result.label}</div>
                </div>
            `;

            showToast(`📊 Stat shiny generated! (${data.dominant_stat}-dominant)`, 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── Smart Swap — Body Style Matcher ───────────────────────────────
    window.loadBodyMatches = async function () {
        const source = document.getElementById('smart-source').value;
        const targetSelect = document.getElementById('smart-target');
        const badge = document.getElementById('smart-body-style');

        try {
            const resp = await fetch(`/api/pokemon/${source}/matches`);
            const data = await resp.json();

            badge.textContent = data.body_style || '';

            targetSelect.innerHTML = '';
            if (data.matches && data.matches.length > 0) {
                data.matches.forEach(name => {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = capitalize(name);
                    targetSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No matching body styles found';
                targetSelect.appendChild(opt);
            }
        } catch (err) {
            console.error('Body matches:', err);
        }
    };
    // Load matches on page load for default selection
    loadBodyMatches();

    // ─── Smart Swap Generation ─────────────────────────────────────────
    document.getElementById('btn-gen-smart')?.addEventListener('click', async () => {
        const source = document.getElementById('smart-source').value;
        const target = document.getElementById('smart-target').value;

        if (!target) {
            showToast('No matching Pokémon available!', 'error');
            return;
        }
        if (source === target) {
            showToast('Pick two different Pokémon!', 'error');
            return;
        }

        showLoading('Smart swapping...');
        try {
            const resp = await fetch('/api/generate/smart-swap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, target }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            const container = document.getElementById('smart-swap-results');
            container.innerHTML = `
                <div class="result-card">
                    <img src="${data.source.image}" alt="${data.source.name}">
                    <div class="result-label">${capitalize(data.source.name)}</div>
                    <div class="result-meta">Source shape</div>
                </div>
                <div class="result-card">
                    <img src="${data.target.image}" alt="${data.target.name}">
                    <div class="result-label">${capitalize(data.target.name)}</div>
                    <div class="result-meta">Target colors</div>
                </div>
                <div class="result-card" style="border-color: var(--accent-2);">
                    <img src="${data.result.image}" alt="Result">
                    <div class="result-label">✨ Result</div>
                    <div class="result-meta">${data.result.label}</div>
                </div>
            `;

            showToast('🧬 Smart swap complete!', 'success');
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
        hideLoading();
    });

    // ─── UI Helpers ────────────────────────────────────────────────────

    function showLoading(text) {
        const overlay = document.getElementById('loading');
        overlay.querySelector('.loading-text').textContent = text || 'Generating...';
        overlay.classList.add('active');
    }

    function hideLoading() {
        document.getElementById('loading').classList.remove('active');
    }

    function showToast(message, type = '') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast active ${type}`;
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('active');
        }, 3500);
    }

    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
});
