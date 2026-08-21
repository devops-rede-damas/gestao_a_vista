// Estado de "visão" do painel: modo de exibição do setor e a equipe em foco.
// Injetado pelo backend em window.exibicao no carregamento da página.

const exibicao = window.exibicao || { modo: "agregado", equipes: [] };
export const teamsList = exibicao.equipes || [];
// "por_equipe" faz a tela alternar cada equipe do setor; caso contrário, agrega tudo (padrão).
export const porEquipe = exibicao.modo === "por_equipe" && teamsList.length > 1;

let currentTeamIndex = 0;

// Avança para a próxima equipe do rodízio (modo por_equipe).
export function nextTeam() {
    currentTeamIndex = (currentTeamIndex + 1) % teamsList.length;
}

// Volta para a equipe anterior (usado pelas setas manuais no mobile).
export function prevTeam() {
    currentTeamIndex = (currentTeamIndex - 1 + teamsList.length) % teamsList.length;
}

// Tickets da visão atual: a equipe em foco (por_equipe) ou a lista inteira (agregado).
export function currentTickets() {
    const all = window.tickets || [];
    if (!porEquipe) return all;
    const team = teamsList[currentTeamIndex];
    return all.filter(t => (t.ownerTeam || "") === team);
}

// Mostra qual equipe está no ar (só no modo por_equipe).
export function updateTeamBadge() {
    const badge = document.getElementById("team-badge");
    // Setas manuais só existem no modo por_equipe (o CSS as mostra apenas no mobile).
    document.querySelectorAll(".team-nav-btn").forEach(b => b.classList.toggle("visible", porEquipe));
    if (!badge) return;
    if (!porEquipe) {
        badge.classList.remove("visible");
        return;
    }
    document.getElementById("team-badge-name").textContent = teamsList[currentTeamIndex];
    document.getElementById("team-badge-pos").textContent = `${currentTeamIndex + 1} / ${teamsList.length}`;
    badge.classList.add("visible");
}
