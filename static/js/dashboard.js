// Dashboard "Gestão à Vista" — orquestrador: monta a tela, faz o auto-refresh e o relógio.
// Widgets em módulos: kpis.js, ranking.js, tickets.js. Estado de visão em view.js.
import { updateKPIs } from "./kpis.js";
import { renderTicketsTable } from "./tickets.js";
import { renderOwnerRank } from "./ranking.js";
import { porEquipe, nextTeam, updateTeamBadge } from "./view.js";

const TEAM_INTERVAL = 15000;
let teamInterval = null;

// Momento da última atualização bem-sucedida (para o aviso de dados desatualizados).
let lastUpdated = null;

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
        const setor = window.setor || "";
        const response = await fetch("/api/tickets?setor=" + encodeURIComponent(setor));
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

// Relógio ao vivo do cabeçalho.
function updateClock() {
    const el = document.getElementById("clock");
    if (el) el.textContent = new Date().toLocaleTimeString("pt-BR");
}

// Rótulo "Atualizado às HH:MM" no cabeçalho.
function updateLastUpdatedLabel() {
    const el = document.getElementById("clock-updated");
    if (el && lastUpdated) el.textContent = "Atualizado às " + lastUpdated.toLocaleTimeString("pt-BR");
}

// Rodízio de equipes: troca a equipe em foco em intervalo fixo (modo por_equipe).
function startTeamCarousel() {
    if (!porEquipe) return;
    if (teamInterval) clearInterval(teamInterval);
    teamInterval = setInterval(() => {
        nextTeam();
        render();
    }, TEAM_INTERVAL);
}

function render() {
    updateKPIs();
    renderTicketsTable();
    renderOwnerRank();
    updateTeamBadge();
    updateLastUpdatedLabel();
}

// Render inicial com os tickets injetados pelo backend.
lastUpdated = new Date();
render();
startTeamCarousel();

// Relógio do cabeçalho: atualiza a cada segundo.
updateClock();
setInterval(updateClock, 1000);

// Atualização automática a cada 60 segundos.
setInterval(fetchTicketsAndUpdate, 60000);
