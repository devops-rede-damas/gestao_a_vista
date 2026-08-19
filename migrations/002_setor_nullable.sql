-- Torna a coluna `setor` ANULÁVEL na tabela dos usuários do login.
-- Motivo: o papel ADM (administrador do painel de usuários) não pertence a um
-- setor — ele gerencia todos. Papel (permissão) e setor (visibilidade de tickets)
-- são ortogonais: exigir setor de um ADM seria um dado artificial. O restante do
-- app já tolera `setor` nulo (core/usuarios_mysql.py: setores = [setor] if setor
-- else []), e o login redireciona o ADM para o painel de gestão de usuários.
--
-- Idempotente na prática: MODIFY apenas reafirma a definição da coluna, então
-- rodar de novo não quebra nem apaga dados. Preserva o tipo/charset originais
-- (VARCHAR(50)), removendo somente a restrição NOT NULL.
ALTER TABLE usuarios_gestor
  MODIFY setor VARCHAR(50) NULL;
