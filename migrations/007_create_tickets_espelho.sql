-- Migration 007 — Espelho local de tickets do Movidesk (base das metricas gerenciais)
-- 1 linha por ticket (grao individual, fatos — sem agregados).
-- Setor NAO e coluna: deriva via setores_de() (acompanha config/setores.json).
-- Idempotente: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS tickets_espelho (
    -- IDENTIDADE
    id                      BIGINT       NOT NULL,
    type                    INT          NULL,
    subject                 VARCHAR(500) NULL,
    category                VARCHAR(255) NULL,
    urgency                 VARCHAR(100) NULL,
    origin                  INT          NULL,
    status                  VARCHAR(100) NULL,
    base_status             VARCHAR(50)  NULL,

    -- PESSOAS (owner_id casa com a tabela colaboradores)
    owner_id                BIGINT       NULL,
    owner_nome              VARCHAR(255) NULL,
    owner_team              VARCHAR(255) NULL,
    created_by_nome         VARCHAR(255) NULL,
    cliente_org             VARCHAR(255) NULL,

    -- SERVICO
    service_first_level     VARCHAR(255) NULL,
    service_second_level    VARCHAR(255) NULL,
    service_third_level     VARCHAR(255) NULL,

    -- DATAS (UTC, como vem da API)
    created_date            DATETIME     NULL,
    first_response_date     DATETIME     NULL,  -- slaRealResponseDate
    resolved_in             DATETIME     NULL,
    closed_in               DATETIME     NULL,
    canceled_in             DATETIME     NULL,
    reopened_in             DATETIME     NULL,
    last_action_date        DATETIME     NULL,
    last_update             DATETIME     NULL,  -- chave do sync incremental

    -- SLA
    sla_response_date       DATETIME     NULL,
    sla_response_time       INT          NULL,
    sla_solution_date       DATETIME     NULL,
    sla_solution_time       INT          NULL,
    sla_solution_changed    TINYINT(1)   NULL,
    sla_solution_paused     TINYINT(1)   NULL,
    resolved_first_call     TINYINT(1)   NULL,

    -- CONTROLE
    sincronizado_em         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dados_json              MEDIUMTEXT   NULL,  -- copia crua do ticket (campos futuros)

    PRIMARY KEY (id),
    INDEX idx_te_last_update  (last_update),
    INDEX idx_te_created_date (created_date),
    INDEX idx_te_owner_id     (owner_id),
    INDEX idx_te_owner_team   (owner_team),
    INDEX idx_te_base_status  (base_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;