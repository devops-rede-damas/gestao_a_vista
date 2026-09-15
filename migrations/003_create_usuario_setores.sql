-- Tabela de junção usuário ↔ setores: permite 1 usuário vinculado a N setores.
-- A médio prazo substitui a coluna única `setor` de usuarios_gestor (que passa a
-- ficar adormecida até ser removida numa migration futura).
--
-- Cada linha é um vínculo usuário↔setor. `primario` marca o setor padrão (onde o
-- usuário cai após o login). A chave primária composta impede vínculo duplicado.
-- IF NOT EXISTS torna o CREATE idempotente: rodar de novo não quebra nem apaga.
CREATE TABLE IF NOT EXISTS usuario_setores (
  usuario_id  BIGINT       NOT NULL,
  setor       VARCHAR(50)  NOT NULL,
  primario    TINYINT(1)   NOT NULL DEFAULT 0,
  criado_em   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (usuario_id, setor),
  CONSTRAINT fk_usuario_setores_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuarios_gestor (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Backfill: copia o setor atual de cada usuário para a nova tabela, marcando-o
-- como primário. INSERT IGNORE + a chave primária evitam duplicar em reexecuções.
INSERT IGNORE INTO usuario_setores (usuario_id, setor, primario)
SELECT id, setor, 1
FROM usuarios_gestor
WHERE setor IS NOT NULL AND setor <> '';
