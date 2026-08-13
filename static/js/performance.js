// Dashboard 2 — Performance / Gestao a Vista.
// Modulo independente e opt-in (flag DASHBOARD2): NAO altera o dashboard da fila
// (dashboard.js); so alterna a classe body.perf-ativa (o CSS troca #main-flex por
// #view-perf) e renderiza os indicadores lidos de /api/metrics2.

const METRICS_URL = "/api/metrics2?setor=";
const REFRESH_MS = 60000; // reconsulta os numeros a cada 60s
const RETRY_MS = 3000;    // enquanto a 1a coleta roda (202), tenta de novo rapido
const FILA_MS = 20000;    // tempo com a fila no ar
const PERF_MS = 25000;    // tempo com o painel de performance no ar

let ultimo = null; // ultimo payload recebido de /api/metrics2

// Icones SVG monocromaticos (herdam a cor via currentColor).
const ICONES = {
    check: '<path d="M20 6L9 17l-5-5"/>',
    relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    camadas: '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 12l9 5 9-5"/>',
    fluxo: '<path d="M3 17l6-6 4 4 7-8"/><path d="M17 7h4v4"/>',
};

function icone(nome, tom) {
    return `<span class="perf-icon ${tom}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONES[nome] || ""}</svg></span>`;
}

function fmtNum(v) {
    return (v === null || v === undefined) ? "\u2014" : Number(v).toLocaleString("pt-BR");
}

function fmtPct(v) {
    return (v === null || v === undefined) ? "\u2014" : `${String(v).replace(".", ",")}%`;
}

function fmtDuracao(min) {
    if (min === null || min === undefined) return "\u2014";
    const total = Math.round(min);
    const d = Math.floor(total / 1440);
    const h = Math.floor((total % 1440) / 60);
    const m = total % 60;
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}min`;
    return `${m}min`;
}

// Delta em pontos percentuais com virgula decimal (pt-BR).
function fmtPp(v) {
    return String(v).replace(".", ",") + "pp";
}

// Seta de tendencia. <melhorSeMenor>=true quando cair e bom (tempos, saldo).
function tendencia(delta, melhorSeMenor, fmt) {
    if (delta === null || delta === undefined || delta === 0) {
        return `<div class="perf-trend flat">\u25AC estavel vs periodo anterior</div>`;
    }
    const melhorou = melhorSeMenor ? delta < 0 : delta > 0;
    const seta = delta > 0 ? "\u25B2" : "\u25BC";
    const valor = fmt ? fmt(Math.abs(delta)) : Math.abs(delta);
    return `<div class="perf-trend ${melhorou ? "up" : "down"}">${seta} ${valor} vs periodo anterior</div>`;
}

function card(iconeNome, tom, titulo, valorHtml, extraHtml) {
    return `<div class="perf-card">
        <div class="perf-card-head">${icone(iconeNome, tom)}<span class="perf-title">${titulo}</span></div>
        <div class="perf-value">${valorHtml}</div>
        ${extraHtml || ""}
    </div>`;
}

function baldes(itens) {
    const html = itens.map(i => `<div class="perf-sub-item"><span class="perf-sub-val ${i.cls}">${fmtNum(i.val)}</span><span class="perf-sub-lbl">${i.lbl}</span></div>`).join("");
    return `<div class="perf-sub">${html}</div>`;
}

// Grafico de linhas (entradas x concluidos) em SVG puro, sem dependencia.
function graficoSVG(evol) {
    const W = 1000, H = 320, padL = 44, padR = 12, padT = 12, padB = 30;
    const pw = W - padL - padR, ph = H - padT - padB;
    const n = evol.length;
    const max = Math.max(1, ...evol.flatMap(d => [d.entradas, d.concluidos]));
    const x = i => padL + (n <= 1 ? pw / 2 : pw * i / (n - 1));
    const y = v => padT + ph * (1 - v / max);
    const pts = k => evol.map((d, i) => `${x(i).toFixed(1)},${y(d[k]).toFixed(1)}`).join(" ");
    const dots = (k, cor) => evol.map((d, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(d[k]).toFixed(1)}" r="3.5" fill="${cor}"/>`).join("");
    let grade = "";
    for (let g = 0; g <= 4; g++) {
        const gy = padT + ph * g / 4;
        const val = Math.round(max * (1 - g / 4));
        grade += `<line x1="${padL}" y1="${gy.toFixed(1)}" x2="${W - padR}" y2="${gy.toFixed(1)}" stroke="#1b4a70" stroke-width="1"/>`;
        grade += `<text x="${padL - 8}" y="${(gy + 4).toFixed(1)}" fill="#9fb6c9" font-size="13" text-anchor="end">${val}</text>`;
    }
    const rotulos = evol.map((d, i) => {
        const [, M, D] = d.data.split("-");
        return `<text x="${x(i).toFixed(1)}" y="${H - 8}" fill="#9fb6c9" font-size="12" text-anchor="middle">${D}/${M}</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        ${grade}${rotulos}
        <polyline points="${pts("entradas")}" fill="none" stroke="#4aa6dd" stroke-width="3"/>
        <polyline points="${pts("concluidos")}" fill="none" stroke="#34d399" stroke-width="3"/>
        ${dots("entradas", "#4aa6dd")}${dots("concluidos", "#34d399")}
    </svg>`;
}

function renderCarregando() {
    const el = document.getElementById("view-perf");
    if (el) el.innerHTML = `<div class="perf-loading">Carregando indicadores de performance\u2026</div>`;
}

function render() {
    const el = document.getElementById("view-perf");
    if (!el || !ultimo) return;
    const a = ultimo.atual || {};
    const c = ultimo.comparacao || {};
    const resp = a.sla_primeira_resposta || {};
    const sol = a.sla_solucao || {};
    const t = a.tempos_medios_min || {};
    const fx = a.fluxo || {};

    const cardResp = card("check", "ic-green", "SLA 1\u00aa Resposta", fmtPct(resp.pct_cumprido),
        tendencia(c.sla_primeira_resposta_pct, false, fmtPp) +
        baldes([
            { val: resp.cumprido, lbl: "Cumpridos", cls: "g" },
            { val: resp.aguardando, lbl: "Aguardando", cls: "a" },
            { val: resp.estourado, lbl: "Estourados", cls: "r" },
        ]));

    const foot = sol.alterados_manualmente ? `<div class="perf-foot">\u24D8 inclui ${fmtNum(sol.alterados_manualmente)} com prazo ajustado</div>` : "";
    const cardSol = card("check", "ic-green", "SLA Solu\u00e7\u00e3o", fmtPct(sol.pct_cumprido),
        tendencia(c.sla_solucao_pct, false, fmtPp) +
        baldes([
            { val: sol.cumprido, lbl: "Cumpridos", cls: "g" },
            { val: sol.em_aberto, lbl: "Em aberto", cls: "a" },
            { val: sol.estourado, lbl: "Estourados", cls: "r" },
        ]) + foot);

    const temUtil = t.primeira_resposta_util !== undefined && t.primeira_resposta_util !== null;
    const cardTResp = temUtil
        ? card("relogio", "ic-blue", "Tempo M\u00e9dio 1\u00aa Resposta", fmtDuracao(t.primeira_resposta_util),
            tendencia(c.tempo_primeira_resposta_util, true, fmtDuracao) +
            `<div class="perf-hint">em hor\u00e1rio \u00fatil (expediente)</div>`)
        : card("relogio", "ic-blue", "Tempo M\u00e9dio 1\u00aa Resposta", fmtDuracao(t.primeira_resposta),
            tendencia(c.tempo_primeira_resposta, true, fmtDuracao) +
            `<div class="perf-hint">tempo de rel\u00f3gio (corrido)</div>`);

    const cardTResol = card("relogio", "ic-purple", "Tempo M\u00e9dio Resolu\u00e7\u00e3o", fmtDuracao(t.resolucao),
        tendencia(c.tempo_resolucao, true, fmtDuracao) +
        `<div class="perf-hint">tempo de rel\u00f3gio (corrido)</div>`);

    const cardBacklog = card("camadas", "ic-orange", "Backlog Atual", fmtNum(a.backlog_atual),
        `<div class="perf-hint">tickets em aberto agora</div>`);

    const saldo = fx.saldo;
    const saldoCls = (saldo !== undefined && saldo < 0) ? "saldo-neg" : (saldo > 0 ? "saldo-pos" : "");
    const fluxoPanel = `<div class="perf-panel perf-fluxo">
        <h2>Taxa de Resolu\u00e7\u00e3o</h2>
        <div class="fluxo-grid">
            <div class="fluxo-row"><span class="fluxo-lbl">Entraram</span><span class="fluxo-val pos">${fmtNum(fx.entraram)}</span></div>
            <div class="fluxo-row"><span class="fluxo-lbl">Resolvidos</span><span class="fluxo-val res">${fmtNum(fx.concluidos)}</span></div>
            <div class="fluxo-row"><span class="fluxo-lbl">Saldo</span><span class="fluxo-val ${saldoCls}">${saldo > 0 ? "+" : ""}${fmtNum(saldo)}</span></div>
            ${tendencia(c.fluxo_saldo, true, v => fmtNum(v)).replace("perf-trend", "fluxo-trend")}
        </div>
    </div>`;

    const chartPanel = `<div class="perf-panel perf-chart">
        <h2>Entradas \u00d7 Resolu\u00e7\u00f5es (14 dias)</h2>
        <div class="perf-legend">
            <span><i class="lg-swatch" style="background:#4aa6dd"></i> Entradas</span>
            <span><i class="lg-swatch" style="background:#34d399"></i> Resolvidos</span>
        </div>
        ${graficoSVG(a.evolucao_diaria || [])}
    </div>`;

    el.innerHTML = `<div class="perf-kpis">${cardResp}${cardSol}${cardTResp}${cardTResol}${cardBacklog}</div>
        <div class="perf-bottom">${chartPanel}${fluxoPanel}</div>`;
}

async function carregar() {
    try {
        const resp = await fetch(METRICS_URL + encodeURIComponent(window.setor || ""));
        if (resp.status === 202) { // coleta ainda rodando em background
            if (!ultimo) renderCarregando();
            setTimeout(carregar, RETRY_MS);
            return;
        }
        if (!resp.ok) throw new Error("metrics2 HTTP " + resp.status);
        ultimo = await resp.json();
        render();
    } catch (error) {
        console.error(error);
    }
    setTimeout(carregar, REFRESH_MS);
}

function mostrarPerf(ativo) {
    document.body.classList.toggle("perf-ativa", ativo);
}

// Rodizio de topo: comeca na fila e alterna fila <-> performance.
function iniciarRodizio() {
    let perfVisivel = false;
    const alterna = () => {
        perfVisivel = !perfVisivel;
        mostrarPerf(perfVisivel);
        setTimeout(alterna, perfVisivel ? PERF_MS : FILA_MS);
    };
    setTimeout(alterna, FILA_MS);
}

carregar();
iniciarRodizio();
