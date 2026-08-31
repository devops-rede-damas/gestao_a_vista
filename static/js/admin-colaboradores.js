/* Tela "Colaboradores" (papel ADM) — comportamento.
 *
 * ES module VANILLA (sem jQuery/DataTables): lista os responsáveis com ticket
 * aberto e permite enviar/trocar/remover a foto. Reusa util.js (iniciais locais
 * + escapeHtml). Consome admin_api.py:
 *   GET    /admin/api/responsaveis
 *   POST   /admin/api/responsaveis/<id>/foto   (multipart, campo 'foto')
 *   DELETE /admin/api/responsaveis/<id>/foto
 */
import { escapeHtml, initialsAvatar } from "/static/js/util.js";

const API = "/admin/api/responsaveis";
const MAX_BYTES = 2 * 1024 * 1024;              // espelha o limite do backend
const TIPOS_OK = ["image/jpeg", "image/png", "image/webp"];

let responsaveis = [];
const equipesSel = new Set(); // equipes marcadas no filtro (multi-selecao)
const setoresSel = new Set(); // setores marcados no filtro (multi-selecao)
const nomeSetor = {};         // chave -> nome amigavel do setor (vem do template)
(window.SETORES || []).forEach((s) => { nomeSetor[s.chave] = s.nome; });

// Icones SVG estaticos (conteudo fixo, nao vem do usuario -> seguro em innerHTML).
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

function avatarSrc(r) {
  return r.foto_url || initialsAvatar(r.nome);
}

function itemHtml(r) {
  const temFoto = !!r.foto_url;
  const oculto = r.exibir === false;
  const situacao = temFoto
    ? '<span class="chip chip-ativo">Com foto</span>'
    : '<span class="foto-sem" title="Sem foto">—</span>';
  const alias = r.nome_exibicao
    ? '<span class="foto-alias">Exibe: ' + escapeHtml(r.nome_exibicao) + "</span>"
    : "";
  return `<tr class="foto-item${oculto ? " foto-item--oculto" : ""}" data-id="${escapeHtml(r.id)}">
    <td data-rotulo="Foto"><img class="foto-mini" src="${escapeHtml(avatarSrc(r))}" alt=""
         onerror="this.onerror=null;this.src='${escapeHtml(initialsAvatar(r.nome))}'"></td>
    <td data-rotulo="Nome"><span class="foto-nome">${escapeHtml(r.nome)}</span>${alias}</td>
    <td data-rotulo="Situação">${situacao}</td>
    <td data-rotulo="Visibilidade">
      <label class="switch">
        <input type="checkbox" class="vis-toggle"${oculto ? "" : " checked"}>
        <span class="switch-track"></span>
        <span class="switch-label">${oculto ? "Oculto" : "Visível"}</span>
      </label>
    </td>
    <td data-rotulo="Ações">
      <div class="row-menu">
        <button type="button" class="btn btn-sm btn-gerenciar row-menu-toggle" aria-haspopup="true" aria-expanded="false">
          <span>Ações</span>
          <svg class="row-menu-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="row-menu-list" hidden>
          <label class="row-menu-item foto-upload">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>${temFoto ? "Trocar foto" : "Enviar foto"}</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
          </label>
          ${temFoto ? `<button type="button" class="row-menu-item row-menu-danger foto-remover">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>Remover foto</span>
          </button>` : ""}
          <button type="button" class="row-menu-item row-menu-nome">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>
            <span>Nome de exibição</span>
          </button>
        </div>
      </div>
    </td>
  </tr>`;
}

function render() {
  const termo = (document.getElementById("f-busca").value || "").trim().toLowerCase();
  let filtrados = responsaveis;
  if (termo) filtrados = filtrados.filter((r) => (r.nome || "").toLowerCase().includes(termo));
  if (setoresSel.size) filtrados = filtrados.filter((r) => (r.setores || []).some((s) => setoresSel.has(s)));
  if (equipesSel.size) filtrados = filtrados.filter((r) => (r.equipes || []).some((e) => equipesSel.has(e)));
  document.getElementById("fotos-lista").innerHTML =
    filtrados.map(itemHtml).join("") || '<tr><td colspan="5" class="foto-vazio">Nenhum responsável encontrado.</td></tr>';
  const total = responsaveis.length;
  document.getElementById("fotos-count").textContent = filtrados.length === total
    ? total + (total === 1 ? " responsável" : " responsáveis")
    : filtrados.length + " de " + total + " responsáveis";
  document.getElementById("btn-limpar").hidden = !(termo || equipesSel.size || setoresSel.size);
}

async function carregar() {
  const lista = document.getElementById("fotos-lista");
  lista.innerHTML = '<tr><td colspan="5" class="foto-vazio">Carregando…</td></tr>';
  try {
    const resp = await fetch(API);
    if (!resp.ok) throw new Error("Falha ao carregar");
    responsaveis = await resp.json();
    popularEquipes();
    popularSetores();
    render();
  } catch (e) {
    lista.innerHTML = '<tr><td colspan="5" class="foto-vazio">Não foi possível carregar os responsáveis.</td></tr>';
    toast("Não foi possível carregar a lista.", "erro");
  }
}

function setBusy(item, busy) {
  item.querySelectorAll("input, button, label").forEach((el) => {
    el.style.pointerEvents = busy ? "none" : "";
    el.style.opacity = busy ? ".6" : "";
  });
}

async function enviar(id, file, item) {
  if (!TIPOS_OK.includes(file.type)) { toast("Use JPG, PNG ou WEBP.", "erro", "Formato inválido"); return; }
  if (file.size > MAX_BYTES) { toast("A imagem excede 2 MB.", "erro", "Muito grande"); return; }
  setBusy(item, true);
  try {
    const fd = new FormData();
    fd.append("foto", file);
    const resp = await fetch(`${API}/${encodeURIComponent(id)}/foto`, { method: "POST", body: fd });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(dados.erro || "Erro ao enviar");
    const r = responsaveis.find((x) => x.id === id);
    const tinhaFoto = !!(r && r.foto_url);
    if (r) { r.foto_url = dados.foto_url; r.arquivo = dados.arquivo; }
    render();
    toast(tinhaFoto ? "Foto substituída." : "Foto salva.", "ok");
  } catch (e) {
    toast(e.message, "erro", "Não foi possível enviar");
    setBusy(item, false);
  }
}

async function remover(id, item) {
  if (!window.confirm("Remover a foto deste responsável?")) return;
  setBusy(item, true);
  try {
    const resp = await fetch(`${API}/${encodeURIComponent(id)}/foto`, { method: "DELETE" });
    if (!resp.ok) throw new Error("Erro ao remover");
    const r = responsaveis.find((x) => x.id === id);
    if (r) { r.foto_url = null; r.arquivo = null; }
    render();
    toast("Foto removida.", "ok");
  } catch (e) {
    toast(e.message, "erro", "Não foi possível remover");
    setBusy(item, false);
  }
}

async function definirVisivel(id, visivel, item) {
  setBusy(item, true);
  try {
    const resp = await fetch(`${API}/${encodeURIComponent(id)}/exibir`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exibir: visivel }),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(dados.erro || "Erro ao salvar");
    const r = responsaveis.find((x) => x.id === id);
    if (r) r.exibir = dados.exibir;
    render();
    toast(dados.exibir ? "Colaborador exibido no painel." : "Colaborador ocultado do painel.", "ok");
  } catch (e) {
    toast(e.message, "erro", "Não foi possível salvar");
    render(); // reverte o switch para o estado real
  }
}

// Delegação de eventos (a lista é re-renderizada a cada ação).
document.getElementById("fotos-lista").addEventListener("change", (e) => {
  const vis = e.target.closest(".vis-toggle");
  if (vis) {
    const item = e.target.closest(".foto-item");
    definirVisivel(item.dataset.id, vis.checked, item);
    return;
  }
  const input = e.target.closest("input[type=file]");
  if (!input || !input.files || !input.files[0]) return;
  const item = e.target.closest(".foto-item");
  enviar(item.dataset.id, input.files[0], item);
  input.value = "";
});
// Fecha todos os menus de ação abertos.
function fecharMenusLinha() {
  document.querySelectorAll("#fotos-lista .row-menu-list").forEach((l) => (l.hidden = true));
  document.querySelectorAll("#fotos-lista .row-menu-toggle").forEach((t) => t.setAttribute("aria-expanded", "false"));
}

// Abre o menu de uma linha, posicionado FIXO a partir do botão (escapa o overflow:hidden do card).
function abrirMenuLinha(toggle) {
  const list = toggle.parentElement.querySelector(".row-menu-list");
  const abrir = list.hidden;
  fecharMenusLinha();
  if (!abrir) return;
  list.hidden = false;
  const r = toggle.getBoundingClientRect();
  list.style.top = `${Math.round(r.bottom + 6)}px`;
  list.style.left = `${Math.round(Math.max(8, r.right - list.offsetWidth))}px`;
  toggle.setAttribute("aria-expanded", "true");
}

document.getElementById("fotos-lista").addEventListener("click", (e) => {
  const toggle = e.target.closest(".row-menu-toggle");
  if (toggle) { abrirMenuLinha(toggle); return; }
  const nomeBtn = e.target.closest(".row-menu-nome");
  if (nomeBtn) {
    const item = e.target.closest(".foto-item");
    fecharMenusLinha();
    abrirModalNome(item.dataset.id);
    return;
  }
  if (!e.target.closest(".foto-remover")) return;
  const item = e.target.closest(".foto-item");
  fecharMenusLinha();
  remover(item.dataset.id, item);
});

// Fecha os menus ao clicar fora, rolar a página ou redimensionar.
document.addEventListener("click", (e) => { if (!e.target.closest(".row-menu")) fecharMenusLinha(); });
window.addEventListener("scroll", fecharMenusLinha, true);
window.addEventListener("resize", fecharMenusLinha);
// Popula o dropdown (checkboxes) com as equipes distintas dos responsaveis carregados.
function popularEquipes() {
  const set = new Set();
  responsaveis.forEach((r) => (r.equipes || []).forEach((e) => set.add(e)));
  document.getElementById("f-equipe-menu").innerHTML = [...set].sort().map((e) => `
    <label class="multi-option" title="${escapeHtml(e)}">
      <input type="checkbox" value="${escapeHtml(e)}"${equipesSel.has(e) ? " checked" : ""}>
      <span>${escapeHtml(e)}</span>
    </label>`).join("");
  atualizarLabelEquipe();
}

function atualizarLabelEquipe() {
  const n = equipesSel.size;
  document.querySelector("#f-equipe .multi-label").textContent =
    n ? `${n} equipe${n > 1 ? "s" : ""}` : "Todas as equipes";
}

// Popula o dropdown de setores com os setores DISTINTOS presentes nos dados (nome amigavel).
function popularSetores() {
  const set = new Set();
  responsaveis.forEach((r) => (r.setores || []).forEach((s) => set.add(s)));
  const chaves = [...set].sort((a, b) => (nomeSetor[a] || a).localeCompare(nomeSetor[b] || b));
  document.getElementById("f-setor-menu").innerHTML = chaves.map((s) => `
    <label class="multi-option" title="${escapeHtml(nomeSetor[s] || s)}">
      <input type="checkbox" value="${escapeHtml(s)}"${setoresSel.has(s) ? " checked" : ""}>
      <span>${escapeHtml(nomeSetor[s] || s)}</span>
    </label>`).join("");
  atualizarLabelSetor();
}

function atualizarLabelSetor() {
  const n = setoresSel.size;
  document.querySelector("#f-setor .multi-label").textContent =
    n ? `${n} setor${n > 1 ? "es" : ""}` : "Todos os setores";
}

document.getElementById("f-busca").addEventListener("input", render);

// Multi-select de equipe: abre/fecha, marca checkboxes, fecha ao clicar fora.
const multiEquipe = document.getElementById("f-equipe");
const toggleEquipe = document.getElementById("f-equipe-toggle");
const menuEquipe = document.getElementById("f-equipe-menu");
toggleEquipe.addEventListener("click", (e) => {
  e.stopPropagation();
  const abrir = menuEquipe.hidden;
  menuEquipe.hidden = !abrir;
  toggleEquipe.setAttribute("aria-expanded", String(abrir));
});
menuEquipe.addEventListener("change", (e) => {
  const cb = e.target.closest("input[type=checkbox]");
  if (!cb) return;
  if (cb.checked) equipesSel.add(cb.value); else equipesSel.delete(cb.value);
  atualizarLabelEquipe();
  render();
});
document.addEventListener("click", (e) => {
  if (!multiEquipe.contains(e.target)) {
    menuEquipe.hidden = true;
    toggleEquipe.setAttribute("aria-expanded", "false");
  }
});

// Multi-select de setor: mesma mecanica do de equipe.
const multiSetor = document.getElementById("f-setor");
const toggleSetor = document.getElementById("f-setor-toggle");
const menuSetor = document.getElementById("f-setor-menu");
toggleSetor.addEventListener("click", (e) => {
  e.stopPropagation();
  const abrir = menuSetor.hidden;
  menuSetor.hidden = !abrir;
  toggleSetor.setAttribute("aria-expanded", String(abrir));
});
menuSetor.addEventListener("change", (e) => {
  const cb = e.target.closest("input[type=checkbox]");
  if (!cb) return;
  if (cb.checked) setoresSel.add(cb.value); else setoresSel.delete(cb.value);
  atualizarLabelSetor();
  render();
});
document.addEventListener("click", (e) => {
  if (!multiSetor.contains(e.target)) {
    menuSetor.hidden = true;
    toggleSetor.setAttribute("aria-expanded", "false");
  }
});

// Limpa busca + equipes selecionadas (aparece so quando ha filtro ativo).
document.getElementById("btn-limpar").addEventListener("click", () => {
  document.getElementById("f-busca").value = "";
  equipesSel.clear();
  menuEquipe.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
  atualizarLabelEquipe();
  setoresSel.clear();
  menuSetor.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
  atualizarLabelSetor();
  render();
});

// Modal de nome de exibicao: abre com o valor atual, salva via PUT (vazio volta ao padrao).
const modalNome = document.getElementById("modal-nome");
const formNome = document.getElementById("form-nome");
const inputNome = document.getElementById("n-nome");
const inputNomeId = document.getElementById("n-id");
const btnSalvarNome = document.getElementById("btn-salvar-nome");

function abrirModalNome(id) {
  const r = responsaveis.find((x) => x.id === id);
  inputNomeId.value = id;
  inputNome.value = (r && r.nome_exibicao) || "";
  modalNome.classList.add("open");
  setTimeout(() => inputNome.focus(), 30);
}

function fecharModalNome() {
  modalNome.classList.remove("open");
}

modalNome.addEventListener("click", (e) => {
  if (e.target === modalNome || e.target.closest("[data-fechar]")) fecharModalNome();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalNome.classList.contains("open")) fecharModalNome();
});

formNome.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = inputNomeId.value;
  const nome = inputNome.value.trim();
  btnSalvarNome.disabled = true;
  try {
    const resp = await fetch(`${API}/${encodeURIComponent(id)}/nome`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(dados.erro || "Erro ao salvar");
    const r = responsaveis.find((x) => x.id === id);
    if (r) r.nome_exibicao = dados.nome_exibicao;
    render();
    fecharModalNome();
    toast(dados.nome_exibicao ? "Nome de exibição salvo." : "Nome de exibição removido.", "ok");
  } catch (err) {
    toast(err.message, "erro", "Não foi possível salvar");
  } finally {
    btnSalvarNome.disabled = false;
  }
});

carregar();
