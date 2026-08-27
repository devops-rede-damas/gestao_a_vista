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
  const situacao = temFoto
    ? '<span class="chip chip-ativo">Com foto</span>'
    : '<span class="chip chip-neutro">Sem foto</span>';
  return `<tr class="foto-item" data-id="${escapeHtml(r.id)}">
    <td data-rotulo="Foto"><img class="foto-mini" src="${escapeHtml(avatarSrc(r))}" alt=""
         onerror="this.onerror=null;this.src='${escapeHtml(initialsAvatar(r.nome))}'"></td>
    <td data-rotulo="Nome">${escapeHtml(r.nome)}</td>
    <td data-rotulo="Situação">${situacao}</td>
    <td data-rotulo="Ações">
      <div class="row-actions">
        <label class="btn btn-sm btn-gerenciar foto-upload">
          <span>${temFoto ? "Trocar" : "Enviar foto"}</span>
          <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
        </label>
        ${temFoto ? '<button type="button" class="btn btn-sm btn-danger foto-remover">Remover</button>' : ""}
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
    filtrados.map(itemHtml).join("") || '<tr><td colspan="4" class="foto-vazio">Nenhum responsável encontrado.</td></tr>';
  const total = responsaveis.length;
  document.getElementById("fotos-count").textContent = filtrados.length === total
    ? total + (total === 1 ? " responsável" : " responsáveis")
    : filtrados.length + " de " + total + " responsáveis";
  document.getElementById("btn-limpar").hidden = !(termo || equipesSel.size || setoresSel.size);
}

async function carregar() {
  const lista = document.getElementById("fotos-lista");
  lista.innerHTML = '<tr><td colspan="4" class="foto-vazio">Carregando…</td></tr>';
  try {
    const resp = await fetch(API);
    if (!resp.ok) throw new Error("Falha ao carregar");
    responsaveis = await resp.json();
    popularEquipes();
    popularSetores();
    render();
  } catch (e) {
    lista.innerHTML = '<tr><td colspan="4" class="foto-vazio">Não foi possível carregar os responsáveis.</td></tr>';
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

// Delegação de eventos (a lista é re-renderizada a cada ação).
document.getElementById("fotos-lista").addEventListener("change", (e) => {
  const input = e.target.closest("input[type=file]");
  if (!input || !input.files || !input.files[0]) return;
  const item = e.target.closest(".foto-item");
  enviar(item.dataset.id, input.files[0], item);
  input.value = "";
});
document.getElementById("fotos-lista").addEventListener("click", (e) => {
  if (!e.target.closest(".foto-remover")) return;
  const item = e.target.closest(".foto-item");
  remover(item.dataset.id, item);
});
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

carregar();
