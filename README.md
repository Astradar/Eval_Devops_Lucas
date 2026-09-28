# Eval DevOps - Astradar

Petite API Flask qui compte les visites dans Redis, avec Docker, une CI/CD GitHub Actions et des metriques Prometheus.

## Routes

| Route | Description |
|---|---|
| `/` | Incremente un compteur de visites dans Redis et l'affiche |
| `/health` | Renvoie `ok` (200) si Redis repond, sinon 500 |
| `/metrics` | Metriques au format Prometheus |

## Lancer le projet en local

Prerequis : Docker Desktop.

```bash
git clone https://github.com/Astradar/Eval_Devops_Lucas.git
cd Eval_Devops_Lucas
docker compose up --build
```

Puis ouvrir :
- http://localhost:5000
- http://localhost:5000/health
- http://localhost:5000/metrics

Arreter : `docker compose down`

## Lancer les tests en local

```bash
docker run -d --name redis-test -p 6379:6379 redis:7.4-alpine
pip install -r requirements.txt pytest
pytest
```

## Contenu du depot

| Fichier | Role |
|---|---|
| `app.py` | Application Flask + metriques |
| `test_app.py` | Tests pytest (utilisent Redis) |
| `Dockerfile` | Image multi-stage `python:3.12-slim`, user non-root, HEALTHCHECK sur `/health` |
| `.dockerignore` | Exclut `.git` et les fichiers inutiles |
| `docker-compose.yml` | 2 services : `app` et `redis`, avec healthchecks |
| `alerts.yml` | Regles d'alerte Prometheus |
| `.yamllint` | Config du lint YAML |
| `.github/actions/setup` | Action locale : setup Python + cache pip + install des dependances |
| `.github/workflows/ci.yml` | CI |
| `.github/workflows/cd.yml` | CD |

## CI (`ci.yml`)

Declenchee sur `pull_request` et `push` sur `main`.

- **lint** : `flake8` sur le code Python et `yamllint` sur tous les YAML
- **test** : matrix Python 3.11 / 3.12, service Redis utilise par les tests, rapport JUnit publie avec `upload-artifact`
- **build** : `docker build` de l'image
- **ci-ok** : depend des 3 autres, echoue si l'un d'eux echoue. C'est ce job qui est obligatoire pour merger sur `main` (branch protection)

Chaque job a un `timeout-minutes`. Le cache pip est gere par `setup-python` (au 2e run : `Cache restored from key ...` dans les logs).

## CD (`cd.yml`)

Declenchee apres une CI verte sur `main` (`workflow_run`), ou a la main avec `workflow_dispatch` (input `environment: production`).

1. **push** : build de l'image et push sur GitHub Container Registry avec 3 tags :
   - `latest`
   - le SHA court du commit
   - un semver `1.0.<numero du run>`
2. **deploy** (uniquement sur `main` ou via `workflow_dispatch`) sur un self-hosted runner :
   - sauvegarde de l'image en cours
   - `docker pull` de la nouvelle image puis `docker compose up -d`
   - `curl` sur `/health` avec 3 retries
   - si le healthcheck echoue : rollback sur l'image precedente et le job echoue

Le login au registry se fait avec `GITHUB_TOKEN` (jamais affiche dans les logs). Les permissions sont limitees a `contents: read` et `packages: write`.

## Metriques

Exposees sur `/metrics` :

| Metrique | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `endpoint`, `code` |
| `http_request_duration_seconds` | Histogram | `endpoint` |
| `app_version_info` | Gauge | `version` (SHA court du commit deploye) |

## Alertes (`alerts.yml`)

- **TauxErreurs5xxEleve** : plus de 5 % de reponses 5xx sur une fenetre glissante de 5 min, pendant 5 min (`for: 5m`). Le `for` evite d'alerter sur un pic isole.
- **LatenceP95Degradee** : p95 de latence au-dessus de 500 ms, pendant 10 min (`for: 10m`). L'appli repond normalement en quelques ms, donc 500 ms indique une vraie degradation.
