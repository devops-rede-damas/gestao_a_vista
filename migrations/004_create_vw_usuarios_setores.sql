-- VIEW de leitura amigável: junta cada usuário (usuarios_gestor) com os setores
-- dele (tabela de junção usuario_setores) numa única linha, para inspeção no banco.
--
-- Não guarda dados: monta a visão na hora da consulta, sempre coerente com a fonte
-- verdadeira (usuario_setores). Evita a coluna `setor` antiga "congelada" e a
-- redundância de duplicar nome/chapa. CREATE OR REPLACE torna a migration idempotente.
-- senha_hash é omitida de propósito (não expor hash numa view de conveniência).
CREATE OR REPLACE VIEW vw_usuarios_setores AS
SELECT
  g.id,
  g.chapa,
  g.nome,
  g.email,
  g.papel,
  g.cargo,
  g.ativo,
  MAX(CASE WHEN us.primario = 1 THEN us.setor END)                       AS setor_principal,
  GROUP_CONCAT(us.setor ORDER BY us.primario DESC, us.setor SEPARATOR ', ') AS setores,
  COUNT(us.setor)                                                        AS qtd_setores
FROM usuarios_gestor g
LEFT JOIN usuario_setores us ON us.usuario_id = g.id
GROUP BY g.id;
