/* Painel de Gestão de Usuários (papel ADM) — comportamento da tela.
 *
 * Diferente do restante do front (ES modules vanilla), ESTA página usa jQuery +
 * DataTables (Decisão #4), carregados localmente antes deste script. Por isso é um
 * script clássico (IIFE) que depende dos globais jQuery ($) e DataTables. Fica
 * isolado nesta página; nenhuma outra tela do sistema é afetada.
 *
 * Consome a API já validada em admin_api.py:
 *   GET    /admin/api/usuarios
 *   POST   /admin/api/usuarios
 *   PUT    /admin/api/usuarios/<id>
 *   PUT    /admin/api/usuarios/<id>/senha
 *   PUT    /admin/api/usuarios/<id>/ativo
 */
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("dados-admin").textContent);
  var SETORES = {};  // chave -> nome de exibição
  (CONFIG.setores || []).forEach(function (s) { SETORES[s.chave] = s.nome; });

  var API = "/admin/api/usuarios";
  var filtroSetor = "";  // valor do filtro de setor (chave), aplicado via custom search

  function escapeHtml(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ── Toast ────────────────────────────────────────────────────────────────
  function toast(mensagem, tipo, titulo) {
    var wrap = document.getElementById("toast-wrap");
    var el = document.createElement("div");
    el.className = "toast toast-" + (tipo || "ok");
    el.innerHTML = (titulo ? '<span class="toast-title">' + escapeHtml(titulo) + "</span>" : "") +
      escapeHtml(mensagem);
    wrap.appendChild(el);
    setTimeout(function () { el.remove(); }, tipo === "erro" ? 6000 : 3500);
  }

  // ── HTTP (fetch) ─────────────────────────────────────────────────────────
  function pedir(metodo, url, corpo) {
    return fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (dados) {
        if (!resp.ok) {
          var msg = (dados && dados.erro) || ("Erro " + resp.status);
          throw new Error(msg);
        }
        return dados;
      });
    });
  }

  // ── Modais ───────────────────────────────────────────────────────────────
  function abrirModal(id) { document.getElementById(id).classList.add("open"); }
  function fecharModal(id) { document.getElementById(id).classList.remove("open"); }
  function fecharTodos() {
    document.querySelectorAll(".modal-backdrop.open").forEach(function (m) { m.classList.remove("open"); });
  }
  document.querySelectorAll("[data-fechar]").forEach(function (b) {
    b.addEventListener("click", fecharTodos);
  });
  document.querySelectorAll(".modal-backdrop").forEach(function (bd) {
    bd.addEventListener("click", function (e) { if (e.target === bd) fecharTodos(); });
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") fecharTodos(); });

  // ── Renderizadores de célula ─────────────────────────────────────────────
  function renderSetor(chave) {
    if (!chave) return '<span class="chip-none">—</span>';
    return escapeHtml(SETORES[chave] || chave);
  }
  function renderPapel(papel) {
    return '<span class="chip chip-papel">' + escapeHtml(papel || "") + "</span>";
  }
  function renderStatus(ativo) {
    return ativo
      ? '<span class="chip chip-ativo">Ativo</span>'
      : '<span class="chip chip-inativo">Inativo</span>';
  }
  function renderAcoes(row) {
    var inativar = row.ativo
      ? '<button class="btn btn-sm btn-danger" data-acao="inativar" data-id="' + row.id + '">Inativar</button>'
      : '<button class="btn btn-sm" data-acao="ativar" data-id="' + row.id + '">Ativar</button>';
    return '<div class="row-actions">' +
      '<button class="btn btn-sm btn-ghost" data-acao="editar" data-id="' + row.id + '">Editar</button>' +
      '<button class="btn btn-sm btn-ghost" data-acao="senha" data-id="' + row.id + '">Senha</button>' +
      inativar +
      "</div>";
  }

  // ── DataTable ────────────────────────────────────────────────────────────
  var tabela = new DataTable("#tabela-usuarios", {
    ajax: { url: API, dataSrc: "" },
    language: {
      url: null,
      search: "Buscar:", lengthMenu: "Mostrar _MENU_ registros", info: "_START_–_END_ de _TOTAL_",
      infoEmpty: "Nenhum registro", infoFiltered: "(de _MAX_)", zeroRecords: "Nenhum usuário encontrado",
      paginate: { first: "«", previous: "‹", next: "›", last: "»" },
      emptyTable: "Nenhum usuário cadastrado",
    },
    order: [[0, "asc"]],
    pageLength: 25,
    columns: [
      { data: "nome", render: function (d) { return escapeHtml(d); } },
      { data: "email", render: function (d) { return escapeHtml(d); } },
      { data: "chapa", render: function (d) { return d ? escapeHtml(d) : '<span class="chip-none">—</span>'; } },
      { data: "setor", render: renderSetor },
      { data: "papel", render: renderPapel },
      { data: "ativo", render: renderStatus },
      { data: null, orderable: false, searchable: false, render: renderAcoes },
    ],
    createdRow: function (tr, data) {
      if (!data.ativo) tr.classList.add("linha-inativo");
    },
  });

  // Filtro de setor (custom search sobre a chave crua da linha)
  DataTable.ext.search.push(function (settings, searchData, index, rowData) {
    if (settings.nTable.id !== "tabela-usuarios") return true;
    if (!filtroSetor) return true;
    return (rowData.setor || "") === filtroSetor;
  });

  // ── Filtros da UI ────────────────────────────────────────────────────────
  document.getElementById("f-nome").addEventListener("input", function () {
    tabela.column(0).search(this.value).draw();
  });
  document.getElementById("f-chapa").addEventListener("input", function () {
    tabela.column(2).search(this.value).draw();
  });
  document.getElementById("f-setor").addEventListener("change", function () {
    filtroSetor = this.value;
    tabela.draw();
  });
  document.getElementById("btn-limpar").addEventListener("click", function () {
    document.getElementById("f-nome").value = "";
    document.getElementById("f-chapa").value = "";
    document.getElementById("f-setor").value = "";
    filtroSetor = "";
    tabela.column(0).search("").column(2).search("").draw();
  });

  // ── Ações da tabela (delegação de evento) ────────────────────────────────
  document.querySelector("#tabela-usuarios tbody").addEventListener("click", function (e) {
    var botao = e.target.closest("button[data-acao]");
    if (!botao) return;
    var id = Number(botao.getAttribute("data-id"));
    var acao = botao.getAttribute("data-acao");
    var row = tabela.rows().data().toArray().find(function (r) { return r.id === id; });
    if (acao === "editar") return abrirEdicao(row);
    if (acao === "senha") return abrirSenha(row);
    if (acao === "ativar") return alternarAtivo(id, true);
    if (acao === "inativar") return alternarAtivo(id, false);
  });

  // ── Criar / Editar ───────────────────────────────────────────────────────
  function abrirCriacao() {
    document.getElementById("modal-usuario-titulo").textContent = "Novo usuário";
    document.getElementById("form-usuario").reset();
    document.getElementById("u-id").value = "";
    document.getElementById("campo-senha-nova").style.display = "";
    abrirModal("modal-usuario");
    document.getElementById("u-nome").focus();
  }
  function abrirEdicao(row) {
    document.getElementById("modal-usuario-titulo").textContent = "Editar usuário";
    document.getElementById("u-id").value = row.id;
    document.getElementById("u-nome").value = row.nome || "";
    document.getElementById("u-email").value = row.email || "";
    document.getElementById("u-chapa").value = row.chapa || "";
    document.getElementById("u-setor").value = row.setor || "";
    document.getElementById("u-papel").value = row.papel || "gestor";
    // Na edição, a senha é alterada pelo botão "Senha" (fluxo próprio).
    document.getElementById("campo-senha-nova").style.display = "none";
    abrirModal("modal-usuario");
    document.getElementById("u-nome").focus();
  }

  document.getElementById("btn-novo").addEventListener("click", abrirCriacao);

  document.getElementById("form-usuario").addEventListener("submit", function (e) {
    e.preventDefault();
    var id = document.getElementById("u-id").value;
    var payload = {
      nome: document.getElementById("u-nome").value.trim(),
      email: document.getElementById("u-email").value.trim(),
      chapa: document.getElementById("u-chapa").value.trim() || null,
      setor: document.getElementById("u-setor").value || null,
      papel: document.getElementById("u-papel").value,
    };
    var botao = document.getElementById("btn-salvar-usuario");
    botao.disabled = true;

    var promessa;
    if (id) {
      promessa = pedir("PUT", API + "/" + id, payload).then(function () {
        toast("Usuário atualizado.", "ok");
      });
    } else {
      var senha = document.getElementById("u-senha").value;
      if (senha) payload.senha = senha;
      promessa = pedir("POST", API, payload).then(function (resp) {
        if (resp.senha_temporaria) {
          toast("Senha temporária: " + resp.senha_temporaria, "ok", "Usuário criado");
        } else {
          toast("Usuário criado.", "ok");
        }
      });
    }

    promessa.then(function () {
      fecharTodos();
      tabela.ajax.reload(null, false);
    }).catch(function (err) {
      toast(err.message, "erro", "Não foi possível salvar");
    }).finally(function () {
      botao.disabled = false;
    });
  });

  // ── Alterar senha ────────────────────────────────────────────────────────
  function abrirSenha(row) {
    document.getElementById("form-senha").reset();
    document.getElementById("s-id").value = row.id;
    document.getElementById("s-nome").textContent = row.nome + " (" + row.email + ")";
    abrirModal("modal-senha");
    document.getElementById("s-senha").focus();
  }
  document.getElementById("form-senha").addEventListener("submit", function (e) {
    e.preventDefault();
    var id = document.getElementById("s-id").value;
    var senha = document.getElementById("s-senha").value;
    pedir("PUT", API + "/" + id + "/senha", { senha: senha }).then(function () {
      toast("Senha alterada.", "ok");
      fecharTodos();
    }).catch(function (err) {
      toast(err.message, "erro", "Não foi possível alterar a senha");
    });
  });

  // ── Ativar / Inativar ────────────────────────────────────────────────────
  function alternarAtivo(id, ativo) {
    var verbo = ativo ? "ativar" : "inativar";
    if (!ativo && !window.confirm("Deseja realmente inativar este usuário? Ele não poderá mais fazer login.")) return;
    pedir("PUT", API + "/" + id + "/ativo", { ativo: ativo }).then(function () {
      toast("Usuário " + (ativo ? "ativado" : "inativado") + ".", "ok");
      tabela.ajax.reload(null, false);
    }).catch(function (err) {
      toast(err.message, "erro", "Não foi possível " + verbo);
    });
  }
})();
