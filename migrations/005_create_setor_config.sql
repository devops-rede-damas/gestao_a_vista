-- Configuração de exibição dos setores do Gestão à Vista (2 tabelas da mesma feature).
-- IF NOT EXISTS torna idempotente: rodar de novo não quebra nem apaga dados.

-- (1) Override do MODO de exibição por setor. Guarda SÓ as EXCEÇÕES: setor sem linha
-- usa o modo padrão do config/setores.json. Valores: 'agregado' | 'por_equipe'.
CREATE TABLE IF NOT EXISTS setor_config (
  setor         VARCHAR(50) NOT NULL,
  exibicao      VARCHAR(20) NOT NULL,
  atualizado_em DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (setor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- (2) Equipes (ownerTeam) descobertas por setor via API Movidesk, mantidas pelo robô
-- mensal (+ botão manual). Alimentam o rodízio 'por_equipe' em união com as equipes
-- vivas dos tickets, permitindo que equipes zeradas ainda apareçam no mural.
CREATE TABLE IF NOT EXISTS setor_equipes (
  setor    VARCHAR(50)  NOT NULL,
  equipe   VARCHAR(255) NOT NULL,
  visto_em DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (setor, equipe)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
