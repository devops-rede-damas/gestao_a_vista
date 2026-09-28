-- Cadastro de colaboradores (agentes) espelhado do Movidesk /persons + configuracao.
-- IF NOT EXISTS torna idempotente: rodar de novo nao quebra nem apaga dados.
--
-- Tabela UNICA com duas naturezas de coluna, separadas por RESPONSABILIDADE:
--   * ESPELHO (so a sincronizacao escreve): nome, ativo, equipes, ultima_sync.
--     equipes = JSON array com os nomes de equipe (ownerTeam) do agente. O setor NAO e
--     guardado aqui de proposito: e derivado na leitura via config/setores.json, entao
--     acompanha automaticamente qualquer mudanca de equipes/setores sem re-sync.
--   * CONFIG (so o admin escreve): foto_arquivo, nome_exibicao, exibir. A sincronizacao
--     NUNCA toca nestas colunas (UPSERT lista apenas as de espelho).
--
-- Regra de ouro: colaborador que sai/incativa no Movidesk vira ativo=0 (nao e deletado),
-- preservando foto/config caso ele retorne. Chave = id do /persons (== owner.id do ticket).
CREATE TABLE IF NOT EXISTS colaboradores (
  id            VARCHAR(50)  NOT NULL,
  nome          VARCHAR(255) NOT NULL DEFAULT '',
  ativo         TINYINT(1)   NOT NULL DEFAULT 1,
  equipes       TEXT         DEFAULT NULL,
  ultima_sync   DATETIME     DEFAULT NULL,
  foto_arquivo  VARCHAR(255) DEFAULT NULL,
  nome_exibicao VARCHAR(255) DEFAULT NULL,
  exibir        TINYINT(1)   NOT NULL DEFAULT 1,
  criado_em     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
