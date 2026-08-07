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
