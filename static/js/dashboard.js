// Dashboard "Gestão à Vista" — orquestrador: monta a tela, faz o auto-refresh e o relógio.
// Widgets em módulos: kpis.js, ranking.js, tickets.js. Estado de visão em view.js.
import { updateKPIs } from "./kpis.js";
import { renderTicketsTable } from "./tickets.js";
import { renderOwnerRank } from "./ranking.js";
import { porEquipe, nextTeam, prevTeam, updateTeamBadge } from "./view.js";
import { ehMobile, ehGestor } from "./util.js";

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
        resetRefreshTimer();
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

// Contador regressivo (60 -> 0) até o próximo refresh, com anel circular (espelha o piloto).
const REFRESH_SECONDS = 60;
const RING_CIRC = 2 * Math.PI * 24; // r=24 no SVG
let secondsLeft = REFRESH_SECONDS;

function renderRefreshTimer() {
    const count = document.getElementById("refresh-count");
    const ring = document.getElementById("refresh-ring");
    if (count) count.textContent = String(secondsLeft);
    if (ring) ring.style.strokeDashoffset = String(RING_CIRC * (1 - secondsLeft / REFRESH_SECONDS));
}

function resetRefreshTimer() {
    secondsLeft = REFRESH_SECONDS;
    renderRefreshTimer();
}

function tickRefreshTimer() {
    secondsLeft = secondsLeft > 0 ? secondsLeft - 1 : REFRESH_SECONDS;
    renderRefreshTimer();
}

// Rodízio de equipes: troca a equipe em foco em intervalo fixo (modo por_equipe).
function startTeamCarousel() {
    if (teamInterval) clearInterval(teamInterval); // sempre limpa (ex.: ao virar mobile)
    if (!porEquipe || ehMobile()) return; // mobile: troca manual pelas setas
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

// Marca o corpo como gestor: revela as setas manuais no desktop. A TV (conta 'tv')
// não recebe a classe, então permanece sempre automática e sem setas.
document.body.classList.toggle("is-gestor", ehGestor());

// Render inicial com os tickets injetados pelo backend.
lastUpdated = new Date();
render();
startTeamCarousel();

// Setas de troca manual de equipe (aparecem no mobile e, agora, no gestor no desktop).
document.getElementById("team-prev")?.addEventListener("click", () => { prevTeam(); render(); startTeamCarousel(); });
document.getElementById("team-next")?.addEventListener("click", () => { nextTeam(); render(); startTeamCarousel(); });

// Ao cruzar o breakpoint mobile/desktop (ex.: girar o aparelho), re-renderiza e
// reavalia os rodízios para o novo tamanho (mobile mostra tudo; TV/desktop roda).
window.matchMedia("(max-width: 768px)").addEventListener("change", () => {
    render();
    startTeamCarousel();
});

// Relógio do cabeçalho: atualiza a cada segundo.
updateClock();
setInterval(updateClock, 1000);

// Contador regressivo até o próximo refresh.
renderRefreshTimer();
setInterval(tickRefreshTimer, 1000);

// Atualização automática a cada 60 segundos.
setInterval(fetchTicketsAndUpdate, 60000);
