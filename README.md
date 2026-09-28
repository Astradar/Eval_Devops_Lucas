# Eval DevOps - Lucas Dumoulin

Alors le projet c'est une petite API en Flask qui compte le nombre de visites et qui stocke le compteur dans Redis. Autour de ça j'ai mis en place tout le pipeline : Docker, CI, CD avec déploiement sur ma machine, et les métriques Prometheus avec des alertes.

## L'appli

Y'a 3 routes :

- `/` : ça incrémente le compteur dans Redis et ça affiche le nombre de visites
- `/health` : renvoie `ok` si Redis répond, sinon une 500. Du coup si Redis tombe, le healthcheck le voit direct
- `/metrics` : les métriques au format Prometheus

## Lancer le projet en local

Faut juste avoir Docker Desktop de lancé.

```bash
git clone https://github.com/Astradar/Eval_Devops_Lucas.git
cd Eval_Devops_Lucas
docker compose up --build
```

Ensuite on peut aller sur :
- http://localhost:5000
- http://localhost:5000/health
- http://localhost:5000/metrics

Pour tout couper : `docker compose down`

## Lancer les tests en local

Les tests ont besoin d'un Redis qui tourne sur le port 6379 :

```bash
docker run -d --name redis-test -p 6379:6379 redis:7.4-alpine
pip install -r requirements.txt pytest
pytest
```

Les tests vérifient que `/` renvoie bien 200 et que le compteur a vraiment augmenté dans Redis, que `/health` répond `ok`, et que `/metrics` contient bien les métriques.

## Ce qu'il y a dans le repo

- `app.py` : l'appli Flask + les métriques
- `test_app.py` : les tests pytest
- `Dockerfile` : build en 2 étapes (multi-stage) sur `python:3.12-slim`. L'appli tourne avec un user `appuser` et pas en root, et y'a un HEALTHCHECK qui tape sur `/health`
- `.dockerignore` : pour pas mettre le `.git` et les fichiers inutiles dans l'image
- `docker-compose.yml` : 2 services, l'appli et Redis, chacun avec son healthcheck. L'appli attend que Redis soit healthy avant de démarrer
- `alerts.yml` : les règles d'alerte Prometheus
- `.yamllint` : la config du lint des YAML
- `.github/actions/setup/` : mon action locale (installe Python avec le cache pip + les dépendances), comme ça je la réutilise dans les jobs au lieu de copier-coller
- `.github/workflows/ci.yml` et `cd.yml` : la CI et la CD

## La CI

Elle se lance à chaque push sur `main` et à chaque pull request. Il y a 4 jobs :

1. **lint** : flake8 sur le code Python et yamllint sur tous les fichiers YAML
2. **test** : les tests tournent sur Python 3.11 et 3.12 (matrix). Il y a un service Redis que les tests utilisent vraiment. Le rapport JUnit est envoyé en artifact
3. **build** : on build l'image Docker pour être sûr qu'elle passe
4. **ci-ok** : il attend les 3 autres et il échoue si un seul a planté. C'est ce job que j'ai mis en obligatoire dans la protection de la branche `main`, comme ça on peut pas merger si la CI est rouge

Chaque job a un `timeout-minutes`. Pour le cache, c'est celui de `setup-python` : au 2e run on voit `Cache restored from key` dans les logs de l'étape Setup.

## La CD

Elle se lance quand la CI est verte sur `main`, ou à la main avec le bouton "Run workflow" (`workflow_dispatch`, avec l'input `environment` = production).

1. **push** : build de l'image et push sur le GitHub Container Registry avec 3 tags :
   - `latest`
   - le SHA court du commit (ex : `1dfb0a2`)
   - une version `1.0.<numéro du run>`
2. **deploy** : ça tourne sur un self-hosted runner installé sur mon PC (Windows). Le job :
   - garde de côté l'image qui tourne actuellement
   - pull la nouvelle image et relance avec `docker compose up -d`
   - fait un curl sur `/health` avec 3 retries
   - si le curl échoue, ça fait un rollback : on re-pull l'image d'avant et on la relance. Et le job finit quand même en rouge pour qu'on voie qu'il y a eu un souci

Le deploy tourne que sur `main` ou via `workflow_dispatch`.

Pour la connexion au registry j'utilise le `GITHUB_TOKEN`, il est jamais affiché dans les logs (GitHub le masque). Les permissions sont mises en haut du workflow et limitées au minimum : `contents: read` et `packages: write` pour pouvoir pousser l'image.

### Test du rollback

J'ai testé le rollback en faisant exprès de mettre l'appli sur le port 5001 au lieu de 5000. Les tests passent (ils utilisent pas le vrai port) donc la CI est verte, mais une fois déployée le curl sur `localhost:5000/health` échoue 3 fois, le rollback remet l'image d'avant et le job passe en rouge. Après j'ai remis le port 5000.

### Installer le runner

Dans le repo : Settings > Actions > Runners > New self-hosted runner > Windows, puis suivre les commandes dans `C:\actions-runner` et lancer `./run.cmd`. Il faut que Docker Desktop soit lancé sur la machine.

## Les métriques

Sur `/metrics` on a :

- `http_requests_total` : un compteur du nombre de requêtes, avec les labels `endpoint` et `code` (le code HTTP)
- `http_request_duration_seconds` : un histogramme de la durée des requêtes par route, ce qui permet de calculer le p95 / p99 avec `histogram_quantile`
- `app_version_info` : une jauge qui donne le SHA du commit déployé (dans le label `version`)

## Les alertes

Dans `alerts.yml` y'a 2 règles :

- **TauxErreurs5xxEleve** : si plus de 5 % des requêtes finissent en 5xx sur les 5 dernières minutes, pendant 5 minutes (`for: 5m`). J'ai mis 5 % parce qu'en dessous ça peut être quelques erreurs isolées, et le `for: 5m` évite de déclencher pour un petit pic qui dure 30 secondes.
- **LatenceP95Degradee** : si le p95 dépasse 500 ms pendant 10 minutes (`for: 10m`). Normalement l'appli répond en quelques millisecondes, donc 500 ms ça veut dire qu'il y a un vrai problème. J'ai mis 10 minutes parce qu'une latence un peu haute c'est moins grave qu'une erreur, donc on attend que ça dure avant d'alerter.
