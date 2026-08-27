// Widget "Tickets por Responsável": pódio (top 3) + carrossel do restante.
import { escapeHtml, getFirstAndLastName, ehMobile, ehGestor, initialsAvatar } from "./util.js";
import { currentTickets } from "./view.js";

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

function avatarUrlFor(ownerId, name) {
    const enviadas = window.avatars || {};
    if (enviadas[ownerId]) return enviadas[ownerId];          // foto enviada pelo admin (nome c/ timestamp = cache-busting)
    if (ownerAvatars[ownerId]) return ownerAvatars[ownerId]; // legado (as 19 do commit inicial)
    return initialsAvatar(name);                             // iniciais geradas localmente (sem servico externo)
}

// Fallback quando o arquivo de avatar nao carrega (ex.: sumiu): iniciais locais.
function avatarOnError(name) {
    const uri = initialsAvatar(name).replace(/'/g, "\\'");
    return `this.onerror=null;this.src='${uri}'`;
}

export function renderOwnerRank() {
    const tickets = currentTickets();
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
    const perPage = Math.ceil(remainingOwners.length / totalPages); // distribui igual entre as paginas (evita pagina quase vazia)
    const startIndex = currentCarouselPage * perPage;
    // Mobile: mostra todos os responsáveis com rolagem (sem paginação); TV/desktop: página do carrossel.
    const pageData = ehMobile() ? remainingOwners : remainingOwners.slice(startIndex, startIndex + perPage);
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

    const mostraPager = carouselData.length > 10 && totalPages > 1 && !ehMobile();
    const gestor = ehGestor();
    if (mostraPager) {
        html += gestor
            ? `<div class="tickets-pager rank-pager">
                   <button type="button" class="rank-page-btn" data-dir="prev" aria-label="Página anterior">&#8249;</button>
                   <span class="tickets-pager-info">Página ${currentCarouselPage + 1} de ${totalPages}</span>
                   <button type="button" class="rank-page-btn" data-dir="next" aria-label="Próxima página">&#8250;</button>
               </div>`
            : `<div class="carousel-page">Página ${currentCarouselPage + 1} de ${totalPages}</div>`;
    }
    container.innerHTML = html;

    // Gestor no desktop: setas manuais que preservam a página e re-armam o rodízio (pausa).
    if (mostraPager && gestor) {
        container.querySelectorAll(".rank-page-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                currentCarouselPage = btn.dataset.dir === "next"
                    ? (currentCarouselPage + 1) % totalPages
                    : (currentCarouselPage - 1 + totalPages) % totalPages;
                renderCarouselTable();
                armCarousel();
            });
        });
    }
}

function startCarousel() {
    currentCarouselPage = 0;
    armCarousel();
}

// Arma o rodízio SEM resetar a página (usado também ao clicar nas setas = pausa/retoma).
function armCarousel() {
    if (carouselInterval) clearTimeout(carouselInterval);
    if (ehMobile()) return; // mobile: lista completa com rolagem, sem rodízio

    const remainingOwners = carouselData.slice(3);
    const totalPages = Math.ceil(remainingOwners.length / ITEMS_PER_PAGE);
    if (carouselData.length <= 10 || totalPages <= 1) return;

    (function nextPage() {
        const interval = currentCarouselPage === 0 ? FIRST_PAGE_INTERVAL : OTHER_PAGES_INTERVAL;
        carouselInterval = setTimeout(() => {
            currentCarouselPage = (currentCarouselPage + 1) % totalPages;
            renderCarouselTable();
            nextPage();
        }, interval);
    })();
}
