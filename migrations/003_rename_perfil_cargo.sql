-- Renomeia a coluna `perfil` para `cargo` na tabela dos usuários do login.
-- Motivo: `perfil` estava sem uso efetivo (não aparecia na tela e ficava sempre
-- no valor padrão). O nome `cargo` reflete melhor a intenção de guardar a
-- função/cargo do usuário. É uma renomeação pura: mesmo tipo/charset, nenhum
-- dado é perdido. O código (core/usuarios_mysql.py e admin_api.py) foi ajustado
-- na mesma mudança para ler/gravar `cargo`.
--
-- Reversível: para desfazer, basta CHANGE COLUMN cargo perfil VARCHAR(100) DEFAULT NULL.
ALTER TABLE usuarios_gestor
  CHANGE COLUMN perfil cargo VARCHAR(100) DEFAULT NULL;
