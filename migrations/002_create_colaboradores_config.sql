-- Configuração por colaborador (exibir no painel / nome de exibição) do Gestão à Vista.
-- Chave = owner.id do Movidesk. IF NOT EXISTS torna o script idempotente:
-- rodar de novo não quebra nem apaga dados.
--
-- A tabela guarda SÓ as EXCEÇÕES: colaborador no padrão (exibir=1 e sem nome de
-- exibição) NÃO tem linha aqui — o default é aplicado no código (core/colaboradores.py).
CREATE TABLE IF NOT EXISTS colaboradores_config (
  owner_id      VARCHAR(50)  NOT NULL,
  exibir        TINYINT(1)   NOT NULL DEFAULT 1,
  nome_exibicao VARCHAR(255) DEFAULT NULL,
  atualizado_em DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
