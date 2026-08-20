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
    // Mostra o código cru do banco; se não existir no setores.json, é um valor pendente.
    if (!SETORES[chave]) return '<span class="chip-none">A definir</span>';
    return escapeHtml(chave);
  }
  function renderPapel(papel) {
    var p = String(papel || "").toLowerCase();
    var cls = "chip-papel-gestor";
    if (p === "adm" || p === "admin") cls = "chip-papel-adm";
    else if (p === "tv") cls = "chip-papel-tv";
    return '<span class="chip ' + cls + '">' + escapeHtml(papel || "") + "</span>";
  }
  function renderStatus(ativo) {
    return ativo
      ? '<span class="chip chip-ativo"><span class="chip-dot"></span>Ativo</span>'
      : '<span class="chip chip-inativo"><span class="chip-dot"></span>Inativo</span>';
  }
  function renderAcoes(row) {
    return '<div class="row-actions">' +
      '<button class="btn btn-sm btn-gerenciar" data-acao="gerenciar" data-id="' + row.id + '" title="Gerenciar usuário">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>' +
      '<span>Gerenciar</span></button>' +
      "</div>";
  }

  // ── DataTable ────────────────────────────────────────────────────────────
  var tabela = new DataTable("#tabela-usuarios", {
    ajax: { url: API, dataSrc: "" },
    // Busca global omitida: a filtragem é feita pelo card de filtros (nome/chapa/setor).
    layout: { topStart: "pageLength", topEnd: null, bottomStart: "info", bottomEnd: "paging" },
    language: {
      url: null,
      lengthMenu: "Mostrar _MENU_ registros", info: "_START_–_END_ de _TOTAL_",
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
      { data: "cargo", render: function (d) { return d ? escapeHtml(d) : '<span class="chip-none">—</span>'; } },
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

  // Contador de resultados + visibilidade do "Limpar filtros" (só com filtro ativo)
  function atualizarContador() {
    var info = tabela.page.info();
    var el = document.getElementById("filter-count");
    if (el) {
      var total = info.recordsTotal, mostrando = info.recordsDisplay;
      el.textContent = mostrando === total
        ? total + (total === 1 ? " usuário" : " usuários")
        : mostrando + " de " + total + " usuários";
    }
    var temFiltro = !!(
      document.getElementById("f-nome").value ||
      document.getElementById("f-chapa").value ||
      filtroSetor
    );
    document.getElementById("btn-limpar").hidden = !temFiltro;
  }
  tabela.on("draw", atualizarContador);

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
    var row = tabela.rows().data().toArray().find(function (r) { return r.id === id; });
    if (row) abrirEdicao(row);
  });

  // ── Criar / Editar ───────────────────────────────────────────────────────
  var edicaoAtivoOriginal = true;  // guarda o status antes da edição (detecta mudança)

  function atualizarLabelAtivo() {
    var chk = document.getElementById("u-ativo");
    document.getElementById("u-ativo-label").textContent = chk.checked ? "Ativo" : "Inativo";
  }
  document.getElementById("u-ativo").addEventListener("change", atualizarLabelAtivo);

  function abrirCriacao() {
    document.getElementById("modal-usuario-titulo").textContent = "Novo usuário";
    document.getElementById("form-usuario").reset();
    document.getElementById("u-id").value = "";
    document.getElementById("campo-status").style.display = "none";
    document.getElementById("campo-senha-nova").style.display = "";
    document.getElementById("u-senha-label").textContent = "Senha inicial";
    document.getElementById("u-senha-hint").textContent = "Se ficar em branco, uma senha temporária será gerada e exibida.";
    document.getElementById("u-senha").placeholder = "Deixe em branco para gerar automaticamente";
    abrirModal("modal-usuario");
    document.getElementById("u-nome").focus();
  }
  function abrirEdicao(row) {
    document.getElementById("modal-usuario-titulo").textContent = "Gerenciar usuário";
    document.getElementById("u-id").value = row.id;
    document.getElementById("u-nome").value = row.nome || "";
    document.getElementById("u-email").value = row.email || "";
    document.getElementById("u-chapa").value = row.chapa || "";
    document.getElementById("u-cargo").value = row.cargo || "";
    document.getElementById("u-setor").value = row.setor || "";
    document.getElementById("u-papel").value = row.papel || "gestor";
    // Status: toggle refletindo o valor atual
    edicaoAtivoOriginal = !!row.ativo;
    document.getElementById("u-ativo").checked = !!row.ativo;
    atualizarLabelAtivo();
    document.getElementById("campo-status").style.display = "";
    // Senha: redefinição opcional no mesmo modal
    document.getElementById("campo-senha-nova").style.display = "";
    document.getElementById("u-senha").value = "";
    document.getElementById("u-senha-label").textContent = "Redefinir senha (opcional)";
    document.getElementById("u-senha-hint").textContent = "Deixe em branco para manter a senha atual.";
    document.getElementById("u-senha").placeholder = "Nova senha (mín. 8 caracteres)";
    abrirModal("modal-usuario");
    document.getElementById("u-nome").focus();
  }

  document.getElementById("btn-novo").addEventListener("click", abrirCriacao);

  // Estado de carregamento do botão Salvar (spinner + texto)
  var btnSalvar = document.getElementById("btn-salvar-usuario");
  var btnSalvarHtml = btnSalvar.innerHTML;
  function setSalvando(ativo) {
    btnSalvar.disabled = ativo;
    btnSalvar.innerHTML = ativo
      ? '<span class="spinner"></span><span>Salvando…</span>'
      : btnSalvarHtml;
  }

  document.getElementById("form-usuario").addEventListener("submit", function (e) {
    e.preventDefault();
    var id = document.getElementById("u-id").value;
    var payload = {
      nome: document.getElementById("u-nome").value.trim(),
      email: document.getElementById("u-email").value.trim(),
      chapa: document.getElementById("u-chapa").value.trim() || null,
      cargo: document.getElementById("u-cargo").value.trim() || null,
      setor: document.getElementById("u-setor").value || null,
      papel: document.getElementById("u-papel").value,
    };
    setSalvando(true);

    var promessa;
    if (id) {
      var novoAtivo = document.getElementById("u-ativo").checked;
      var novaSenha = document.getElementById("u-senha").value;
      if (novaSenha && novaSenha.length < 8) {
        toast("A senha deve ter ao menos 8 caracteres.", "erro", "Senha inválida");
        setSalvando(false);
        return;
      }
      if (edicaoAtivoOriginal && !novoAtivo &&
          !window.confirm("Deseja inativar este usuário? Ele não poderá mais fazer login.")) {
        setSalvando(false);
        return;
      }
      promessa = pedir("PUT", API + "/" + id, payload);
      if (novoAtivo !== edicaoAtivoOriginal) {
        promessa = promessa.then(function () {
          return pedir("PUT", API + "/" + id + "/ativo", { ativo: novoAtivo });
        });
      }
      if (novaSenha) {
        promessa = promessa.then(function () {
          return pedir("PUT", API + "/" + id + "/senha", { senha: novaSenha });
        });
      }
      promessa = promessa.then(function () { toast("Usuário atualizado.", "ok"); });
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
      setSalvando(false);
    });
  });
})();
