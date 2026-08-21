// Widget "Tickets Novos / Sem 1ª Resposta": lista paginada por criticidade de SLA.
import { escapeHtml, ehMobile } from "./util.js";
import { currentTickets } from "./view.js";

// Classes de cor por status de SLA (definidas em static/css/gta.css).
const SLA_STATUS_CLASS = {
    "SLA a Vencer": "sla-avencer",
    "SLA Vencido": "sla-vencido",
    "Ticket Novo": "sla-novo",
};

// Ordem de criticidade (menor = mais urgente, aparece no topo).
const SLA_PRIORITY = { "SLA Vencido": 0, "SLA a Vencer": 1, "Ticket Novo": 2 };

// Estado do carrossel da tabela de tickets (pagina o volume alto sem vazar da TV).
let currentTicketsPage = 0;
let ticketsInterval = null;
const TICKETS_PAGE_INTERVAL = 10000;
const TICKETS_ROW_PX = 42;      // altura fixa de uma linha (casada com o CSS)
const TICKETS_CHROME_PX = 130;  // titulo + cabecalho + paginador + paddings

// Quantas linhas cabem por página, a partir da altura real disponível do card.
function ticketsPerPage(container) {
    const h = container.clientHeight || 0;
    if (h < 120) return 8; // fallback antes de o layout estabilizar
    return Math.max(1, Math.floor((h - TICKETS_CHROME_PX) / TICKETS_ROW_PX));
}

function ticketRowHtml(t) {
    const owner = (t.owner && t.owner.businessName) || "-";
    const respondido = !!t.slaRealResponseDate;
    const slaTexto = respondido ? "Realizada" : (t.slaResponseDateFmt || "-");
    const status = t.slaStatus || "";
    const statusClass = SLA_STATUS_CLASS[status] || "";
    return `
                <div class="tk-row">
                    <span class="tk-num" data-label="Nº">#${escapeHtml(t.id)}</span>
                    <span class="tk-owner" data-label="Responsável">${escapeHtml(owner)}</span>
                    <span class="tk-sla" data-label="SLA 1ª Resposta">${escapeHtml(slaTexto)}</span>
                    <span class="tk-status ${statusClass}" data-label="Status">${escapeHtml(status)}</span>
                </div>`;
}

export function renderTicketsTable() {
    const container = document.getElementById("tickets-table-container");
    if (!container) return;

    // Tickets novos ou ainda sem 1ª resposta registrada, dos mais críticos aos menos.
    const tickets = currentTickets().filter(t =>
        (t.baseStatus && t.baseStatus.toLowerCase() === "new") ||
        !t.slaRealResponseDate
    ).sort((a, b) => (SLA_PRIORITY[a.slaStatus] ?? 9) - (SLA_PRIORITY[b.slaStatus] ?? 9));

    const perPage = ehMobile() ? Math.max(tickets.length, 1) : ticketsPerPage(container);
    const totalPages = ehMobile() ? 1 : Math.max(1, Math.ceil(tickets.length / perPage));
    if (currentTicketsPage >= totalPages) currentTicketsPage = 0;
    const pageData = ehMobile() ? tickets : tickets.slice(currentTicketsPage * perPage, currentTicketsPage * perPage + perPage);

    const rows = tickets.length === 0
        ? `<div class="tk-empty">Nenhum ticket encontrado.</div>`
        : pageData.map(ticketRowHtml).join("");

    const pager = (!ehMobile() && totalPages > 1)
        ? `<div class="carousel-page">Página ${currentTicketsPage + 1} de ${totalPages}</div>`
        : "";

    container.innerHTML = `
        <h2>Tickets Novos / Sem 1ª Resposta</h2>
        <div class="tickets-list">
            <div class="tk-row tk-head">
                <span class="tk-num">Nº</span>
                <span class="tk-owner">Responsável</span>
                <span class="tk-sla">SLA 1ª Resposta</span>
                <span class="tk-status">Status</span>
            </div>
            ${rows}
        </div>
        ${pager}`;

    // Mobile: mostra todos os tickets com rolagem (sem rodízio). TV/desktop: mantém o carrossel.
    if (ehMobile()) {
        if (ticketsInterval) clearTimeout(ticketsInterval);
    } else {
        startTicketsCarousel(totalPages);
    }
}

// Rodízio das páginas da tabela de tickets (só quando há mais de uma página).
function startTicketsCarousel(totalPages) {
    if (ticketsInterval) clearTimeout(ticketsInterval);
    if (totalPages <= 1) return;
    ticketsInterval = setTimeout(() => {
        currentTicketsPage = (currentTicketsPage + 1) % totalPages;
        renderTicketsTable();
    }, TICKETS_PAGE_INTERVAL);
}
