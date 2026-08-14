-- Tabela dos usuários do login (gestores + TVs) do painel Gestão à Vista.
-- Fiel à estrutura em produção. IF NOT EXISTS torna o script idempotente:
-- rodar de novo não quebra nem apaga dados.
CREATE TABLE IF NOT EXISTS usuarios_gestor (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  email         VARCHAR(255) NOT NULL,
  chapa         VARCHAR(20)  DEFAULT NULL,
  nome          VARCHAR(255) NOT NULL,
  setor         VARCHAR(50)  NOT NULL,
  papel         VARCHAR(20)  NOT NULL DEFAULT 'gestor',
  perfil        VARCHAR(100) DEFAULT NULL,
  imagem        VARCHAR(255) DEFAULT NULL,
  senha_hash    VARCHAR(255) NOT NULL,
  ativo         TINYINT(1)   NOT NULL DEFAULT 1,
  criado_em     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_usuarios_gestor_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
