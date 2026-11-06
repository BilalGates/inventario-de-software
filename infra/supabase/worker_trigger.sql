-- Lanzamiento horario del workflow «Worker» de GitHub desde Supabase (pg_cron + pg_net).
--
-- El «schedule» de GitHub es de mejor esfuerzo: con carga retrasa o salta ejecuciones. pg_cron
-- dispara a su hora y llama a la API workflow_dispatch; el cron de GitHub queda de respaldo (una
-- pasada de más no hace daño: el workflow tiene grupo de concurrencia y la cola es idempotente).
--
-- Lo aplica .github/workflows/worker-trigger.yml con las variables psql :token (PAT de grano fino
-- con «Actions: Read and write» solo sobre este repositorio) y :repo (propietario/repositorio).
-- Es idempotente: vuelva a ejecutarlo para rotar el token.

\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- El token se guarda cifrado en Supabase Vault, nunca en la definición del trabajo.
SELECT vault.update_secret(id, :'token')
  FROM vault.secrets WHERE name = 'inventario_worker_dispatch';
SELECT vault.create_secret(:'token', 'inventario_worker_dispatch',
                           'PAT de GitHub (Actions write) usado por el trabajo pg_cron inventario-worker')
 WHERE NOT EXISTS (SELECT 1 FROM vault.secrets WHERE name = 'inventario_worker_dispatch');

-- Minuto 5 de cada hora (UTC). Programar un nombre existente lo sustituye.
SELECT cron.schedule('inventario-worker', '5 * * * *', format($job$
  SELECT net.http_post(
    url := 'https://api.github.com/repos/%s/actions/workflows/worker.yml/dispatches',
    body := '{"ref": "main"}'::jsonb,
    headers := jsonb_build_object(
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'asserta-inventario-worker-trigger',
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets
                                     WHERE name = 'inventario_worker_dispatch')),
    timeout_milliseconds := 10000)
$job$, :'repo'));

SELECT jobid, jobname, schedule, active FROM cron.job WHERE jobname = 'inventario-worker';
