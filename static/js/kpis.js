// Widget de KPIs (total, novos, em atendimento, parados).
import { currentTickets } from "./view.js";

export function updateKPIs() {
    const tickets = currentTickets();
    const byStatus = (s) =>
        tickets.filter(t => t.baseStatus && t.baseStatus.toLowerCase() === s).length;

    document.getElementById("kpi-total").textContent = tickets.length;
    document.getElementById("kpi-novos").textContent = byStatus("new");
    document.getElementById("kpi-abertos").textContent = byStatus("inattendance");
    document.getElementById("kpi-parados").textContent = byStatus("stopped");
}
