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
