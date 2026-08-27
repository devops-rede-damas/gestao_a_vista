// Utilitários compartilhados entre os widgets do painel.

// Escapa texto para uso seguro em innerHTML (evita XSS a partir de dados do Movidesk).
export function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[c]));
}

export function getFirstAndLastName(owner) {
    if (!owner || !owner.businessName) return "Sem Responsável";
    const names = owner.businessName.trim().split(" ");
    if (names.length === 1) return names[0];
    return `${names[0]} ${names[names.length - 1]}`;
}

// True quando a tela é estreita (celular/tablet, <=768px). Usado para dar
// comportamento próprio no mobile (mostrar tudo com rolagem) SEM afetar a TV,
// que é sempre grande e nunca cai neste ramo.
export function ehMobile() {
    return window.matchMedia("(max-width: 768px)").matches;
}

// True quando quem vê é um GESTOR logado (não a TV). A TV entra com conta 'tv'
// (window.logado=false) e fica sempre automática, sem setas — por isso a decisão
// de mostrar controles manuais ancora na CONTA, nunca no tamanho da tela.
export function ehGestor() {
    return !!window.logado;
}

// Gera um avatar de INICIAIS localmente (SVG data URI), sem depender de serviço
// externo (privacidade + funciona sem internet). Usado como fallback de foto.
// Contexto de <img>: o SVG NÃO executa scripts; ainda assim escapamos o texto.
export function initialsAvatar(name, size = 128) {
    const nome = String(name ?? "").trim();
    const partes = nome ? nome.split(/\s+/) : [];
    let iniciais = "?";
    if (partes.length === 1) iniciais = partes[0].slice(0, 2).toUpperCase();
    else if (partes.length >= 2) iniciais = (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
    // Cor de fundo determinística a partir do nome (mesmo nome -> mesma cor).
    let hash = 0;
    for (let i = 0; i < nome.length; i++) hash = (hash * 31 + nome.charCodeAt(i)) & 0xffffff;
    const bg = `hsl(${hash % 360}, 45%, 42%)`;
    const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
        `<rect width="100%" height="100%" fill="${bg}"/>` +
        `<text x="50%" y="50%" dy=".35em" text-anchor="middle" ` +
        `font-family="Inter, Segoe UI, Arial, sans-serif" font-size="${Math.round(size * 0.42)}" ` +
        `font-weight="700" fill="#ffffff">${escapeHtml(iniciais)}</text></svg>`;
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}
