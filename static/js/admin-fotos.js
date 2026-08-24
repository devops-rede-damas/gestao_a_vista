/* Tela "Fotos dos responsáveis" (papel ADM) — comportamento.
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

function toast(mensagem, tipo, titulo) {
  const wrap = document.getElementById("toast-wrap");
  const el = document.createElement("div");
  el.className = "toast toast-" + (tipo || "ok");
  el.innerHTML = (titulo ? '<span class="toast-title">' + escapeHtml(titulo) + "</span>" : "") + escapeHtml(mensagem);
  wrap.appendChild(el);
  setTimeout(() => el.remove(), tipo === "erro" ? 6000 : 3500);
}

function avatarSrc(r) {
  return r.foto_url || initialsAvatar(r.nome);
}

function itemHtml(r) {
  const temFoto = !!r.foto_url;
  return `<div class="foto-item" data-id="${escapeHtml(r.id)}">
    <img class="foto-avatar" src="${escapeHtml(avatarSrc(r))}" alt=""
         onerror="this.onerror=null;this.src='${escapeHtml(initialsAvatar(r.nome))}'">
    <span class="foto-nome">${escapeHtml(r.nome)}</span>
    <div class="foto-acoes">
      <label class="btn btn-sm btn-gerenciar foto-upload">
        <span>${temFoto ? "Trocar" : "Enviar foto"}</span>
        <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
      </label>
      ${temFoto ? '<button type="button" class="btn btn-sm btn-danger foto-remover">Remover</button>' : ""}
    </div>
  </div>`;
}

function render() {
  const termo = (document.getElementById("f-busca").value || "").trim().toLowerCase();
  const filtrados = termo
    ? responsaveis.filter((r) => (r.nome || "").toLowerCase().includes(termo))
    : responsaveis;
  document.getElementById("fotos-lista").innerHTML =
    filtrados.map(itemHtml).join("") || '<div class="foto-vazio">Nenhum responsável encontrado.</div>';
  const total = responsaveis.length;
  document.getElementById("fotos-count").textContent = filtrados.length === total
    ? total + (total === 1 ? " responsável" : " responsáveis")
    : filtrados.length + " de " + total + " responsáveis";
}

async function carregar() {
  const lista = document.getElementById("fotos-lista");
  lista.innerHTML = '<div class="foto-vazio">Carregando…</div>';
  try {
    const resp = await fetch(API);
    if (!resp.ok) throw new Error("Falha ao carregar");
    responsaveis = await resp.json();
    render();
  } catch (e) {
    lista.innerHTML = '<div class="foto-vazio">Não foi possível carregar os responsáveis.</div>';
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
    if (r) { r.foto_url = dados.foto_url; r.arquivo = dados.arquivo; }
    render();
    toast("Foto atualizada.", "ok");
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
document.getElementById("f-busca").addEventListener("input", render);

carregar();
