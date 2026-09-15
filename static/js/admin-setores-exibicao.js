/* Tela "Setores > Exibição" (papel ADM) — comportamento.
 *
 * ES module vanilla: alterna o modo de exibição de cada setor (agregado x por_equipe).
 * Consome admin_api.py:
 *   PUT /admin/api/setores/<setor>/exibicao   body { "exibicao": "por_equipe"|"agregado" }
 */
import { escapeHtml } from "/static/js/util.js";

const API = "/admin/api/setores";

// Ícones SVG estáticos (conteúdo fixo -> seguro em innerHTML).
const TOAST_ICONES = {
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
  erro: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16.5" x2="12" y2="16.5"/></svg>',
};

function toast(mensagem, tipo, titulo) {
  const wrap = document.getElementById("toast-wrap");
  const el = document.createElement("div");
  el.className = "toast toast-" + (tipo || "ok");
  const corpo = (titulo ? '<span class="toast-title">' + escapeHtml(titulo) + "</span>" : "") + escapeHtml(mensagem);
  el.innerHTML = '<span class="toast-icon">' + (TOAST_ICONES[tipo] || TOAST_ICONES.ok) + '</span><span class="toast-body">' + corpo + "</span>";
  wrap.appendChild(el);
  const vida = tipo === "erro" ? 6000 : 3500;
  setTimeout(() => {
    el.classList.add("toast-hide");
    setTimeout(() => el.remove(), 260);
  }, vida);
}

async function definirModo(setor, porEquipe, input, metaEl) {
  const modo = porEquipe ? "por_equipe" : "agregado";
  input.disabled = true;
  try {
    const resp = await fetch(`${API}/${encodeURIComponent(setor)}/exibicao`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exibicao: modo }),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(dados.erro || "Erro ao salvar.");
    if (metaEl) metaEl.textContent = porEquipe ? "Uma equipe por vez" : "Todas as equipes juntas";
    toast(porEquipe ? "Rodízio por equipe ativado." : "Exibição agregada ativada.", "ok");
  } catch (e) {
    input.checked = !porEquipe; // reverte o switch quando não salvou
    toast(e.message, "erro", "Não salvou");
  } finally {
    input.disabled = false;
  }
}

document.querySelectorAll(".exib-toggle").forEach((input) => {
  input.addEventListener("change", () => {
    const item = input.closest(".exib-item");
    const meta = item ? item.querySelector(".exib-modo-label") : null;
    definirModo(input.dataset.setor, input.checked, input, meta);
  });
});
