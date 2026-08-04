// Dashboard "Gestão à Vista" — KPIs, tabela e auto-refresh.
// Portado da lógica de charts.js do orquestrador_rpa, sem o código morto.

// Escapa texto para uso seguro em innerHTML (evita XSS a partir de dados do Movidesk).
function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[c]));
}

function getFirstAndLastName(owner) {
    if (!owner || !owner.businessName) return "Sem Responsável";
    const names = owner.businessName.trim().split(" ");
    if (names.length === 1) return names[0];
    return `${names[0]} ${names[names.length - 1]}`;
}

// Mapa de avatares por owner.id (imagens em static/avatars).
const ownerAvatars = {
    "185753352": "/static/avatars/eliaquim.jpg",
    "568534302": "/static/avatars/gracas.jpg",
    "613858261": "/static/avatars/guilherme.jpg",
    "844226215": "/static/avatars/jhonata.jpg",
    "901332917": "/static/avatars/anne.jpg",
    "1226994704": "/static/avatars/edilson.jpg",
    "882923096": "/static/avatars/ricaelle.jpg",
    "1958199556": "/static/avatars/mailonga.jpg",
    "555506729": "/static/avatars/murilo.jpg",
    "789451288": "/static/avatars/daniel.jpg",
    "1430041703": "/static/avatars/paula.jpg",
    "628259032": "/static/avatars/ester.jpg",
    "221575143": "/static/avatars/rodolfo.jpg",
    "1594869193": "/static/avatars/anaflavia.jpg",
    "1873121466": "/static/avatars/generson.jpg",
    "1797121388": "/static/avatars/livia.jpg",
    "928728737": "/static/avatars/wollace.jpg",
    "1011296037": "/static/avatars/ector.jpg",
    "1756765374": "/static/avatars/renato.jpg",
};

// Estado do carrossel do ranking.
let currentCarouselPage = 0;
let carouselData = [];
let carouselInterval = null;
const FIRST_PAGE_INTERVAL = 12000;
const OTHER_PAGES_INTERVAL = 6000;
const ITEMS_PER_PAGE = 10;

// Momento da última atualização bem-sucedida (para o aviso de dados desatualizados).
let lastUpdated = null;

// Classes de cor por status de SLA (definidas no CSS de gta.html).
const SLA_STATUS_CLASS = {
    "SLA a Vencer": "sla-avencer",
    "SLA Vencido": "sla-vencido",
    "Ticket Novo": "sla-novo",
};

function avatarUrlFor(ownerId, name) {
    return ownerAvatars[ownerId] || "https://ui-avatars.com/api/?name=" + encodeURIComponent(name);
}

// Fallback quando o arquivo de avatar não existe.
function avatarOnError(name) {
    const safeName = encodeURIComponent(name).replace(/'/g, "%27");
    return `this.onerror=null;this.src='https://ui-avatars.com/api/?name=${safeName}'`;
}

function updateKPIs() {
    const tickets = window.tickets || [];
    const byStatus = (s) =>
        tickets.filter(t => t.baseStatus && t.baseStatus.toLowerCase() === s).length;

    document.getElementById("kpi-total").textContent = tickets.length;
    document.getElementById("kpi-novos").textContent = byStatus("new");
    document.getElementById("kpi-abertos").textContent = byStatus("inattendance");
    document.getElementById("kpi-parados").textContent = byStatus("stopped");
}

function renderTicketsTable() {
    // Tickets novos ou ainda sem 1ª resposta registrada.
    const tickets = (window.tickets || []).filter(t =>
        (t.baseStatus && t.baseStatus.toLowerCase() === "new") ||
        !t.slaRealResponseDate
    );

    const rows = tickets.length === 0
        ? `<tr><td colspan="4" class="empty">Nenhum ticket encontrado.</td></tr>`
        : tickets.map(t => {
            const owner = (t.owner && t.owner.businessName) || "-";
            const respondido = !!t.slaRealResponseDate;
            const slaTexto = respondido ? "Realizada" : (t.slaResponseDateFmt || "-");
            const status = t.slaStatus || "";
            const statusClass = SLA_STATUS_CLASS[status] || "";
            return `
                <tr>
                    <td>#${escapeHtml(t.id)}</td>
                    <td>${escapeHtml(owner)}</td>
                    <td>${slaTexto}</td>
                    <td class="${statusClass}">${escapeHtml(status)}</td>
                </tr>`;
        }).join("");

    document.getElementById("tickets-table-container").innerHTML = `
        <h2>Tickets Novos / Sem 1ª Resposta</h2>
        <table>
            <thead>
                <tr><th>Nº</th><th>Responsável</th><th>SLA 1ª Resposta</th><th>Status</th></tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// Aviso de dados desatualizados quando o refresh falha.
function showStaleWarning() {
    const banner = document.getElementById("stale-banner");
    if (!banner) return;
    const quando = lastUpdated ? lastUpdated.toLocaleTimeString("pt-BR") : "-";
    banner.textContent = `⚠️ Dados podem estar desatualizados — última atualização às ${quando}`;
    banner.classList.add("visible");
}

function hideStaleWarning() {
    const banner = document.getElementById("stale-banner");
    if (banner) banner.classList.remove("visible");
}

async function fetchTicketsAndUpdate() {
    try {
        const response = await fetch("/api/tickets");
        if (!response.ok) throw new Error("Erro ao buscar tickets");
        window.tickets = await response.json();
        lastUpdated = new Date();
        hideStaleWarning();
        render();
    } catch (error) {
        console.error(error);
        showStaleWarning();
    }
}

function renderOwnerRank() {
    const tickets = window.tickets || [];
    const owners = {};
    tickets.forEach(t => {
        const ownerId = t.owner && t.owner.id ? t.owner.id : "sem_responsavel";
        if (!owners[ownerId]) {
            owners[ownerId] = { count: 0, name: getFirstAndLastName(t.owner) };
        }
        owners[ownerId].count++;
    });

    carouselData = Object.entries(owners).sort((a, b) => b[1].count - a[1].count);
    renderPodium(carouselData);
    renderCarouselTable();
    startCarousel();
}

function renderPodium(sortedOwners) {
    const podiumItems = sortedOwners.slice(0, 3).map(([ownerId, info]) => {
        const url = avatarUrlFor(ownerId, info.name);
        return `
            <div class="owner-rank-podium-item">
                <img src="${url}" alt="avatar" class="owner-rank-podium-avatar" onerror="${avatarOnError(info.name)}">
                <div class="owner-rank-podium-name">${escapeHtml(info.name)}</div>
                <div class="owner-rank-podium-count">${info.count} tickets</div>
            </div>`;
    }).join("");

    const rankDiv = document.getElementById("owner-rank-container");
    if (rankDiv) {
        rankDiv.innerHTML = `
            <h2 class="owner-rank-title">Tickets por Responsável</h2>
            <div class="owner-rank-podium">${podiumItems}</div>
            <div id="carousel-table-container"></div>`;
    }
}

function renderCarouselTable() {
    const remainingOwners = carouselData.slice(3);
    const container = document.getElementById("carousel-table-container");
    if (!container) return;
    if (remainingOwners.length === 0) {
        container.innerHTML = "";
        return;
    }

    const totalPages = Math.ceil(remainingOwners.length / ITEMS_PER_PAGE);
    const startIndex = currentCarouselPage * ITEMS_PER_PAGE;
    const pageData = remainingOwners.slice(startIndex, startIndex + ITEMS_PER_PAGE);
    const maxCount = Math.max(...remainingOwners.map(([, info]) => info.count), 1);

    const rows = pageData.map(([ownerId, info]) => {
        const url = avatarUrlFor(ownerId, info.name);
        const percent = maxCount ? (info.count / maxCount) * 100 : 0;
        return `<tr>
            <td class="owner-cell">
                <img src="${url}" alt="avatar" class="owner-rank-list-avatar" onerror="${avatarOnError(info.name)}">
                ${escapeHtml(info.name)}
            </td>
            <td>
                <div class="bar-wrap">
                    <div class="bar" style="width:${percent}%"></div>
                    <span class="bar-count">${info.count}</span>
                </div>
            </td>
        </tr>`;
    }).join("");

    let html = `
        <table class="owner-rank-list">
            <thead><tr><th>Responsável</th><th>Tickets</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;

    if (carouselData.length > 10 && totalPages > 1) {
        html += `<div class="carousel-page">Página ${currentCarouselPage + 1} de ${totalPages}</div>`;
    }
    container.innerHTML = html;
}

function startCarousel() {
    if (carouselInterval) clearTimeout(carouselInterval);

    const remainingOwners = carouselData.slice(3);
    const totalPages = Math.ceil(remainingOwners.length / ITEMS_PER_PAGE);
    if (carouselData.length <= 10 || totalPages <= 1) return;

    currentCarouselPage = 0;
    (function nextPage() {
        const interval = currentCarouselPage === 0 ? FIRST_PAGE_INTERVAL : OTHER_PAGES_INTERVAL;
        carouselInterval = setTimeout(() => {
            currentCarouselPage = (currentCarouselPage + 1) % totalPages;
            renderCarouselTable();
            nextPage();
        }, interval);
    })();
}

function render() {
    updateKPIs();
    renderTicketsTable();
    renderOwnerRank();
}

// Render inicial com os tickets injetados pelo backend.
lastUpdated = new Date();
render();

// Etapa 5: atualização automática a cada 60 segundos.
setInterval(fetchTicketsAndUpdate, 60000);
