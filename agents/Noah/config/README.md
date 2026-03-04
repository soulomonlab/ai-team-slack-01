# Redis Provisioning (Kubernetes Helm)

Purpose
- Provision managed Redis on our Kubernetes clusters (staging/prod) using Bitnami Redis Helm chart.
- Provide Pub/Sub for cache invalidation and enable Prometheus metrics for observability.

Key decisions
- Deployment: Kubernetes Helm (bitnami/redis) — fits our k8s stack and supports metrics/exporter.
- Staging memory target: 4Gi (values-staging.yaml)
- Prod memory target: 32Gi (values-prod.yaml)
- Architecture: primary-replica. Staging: 1 replica; Prod: 2 replicas.
- Pub/Sub: works out-of-the-box. Ensure application uses Redis AUTH and TLS if crossing networks.
- Monitoring: redis-exporter enabled + ServiceMonitor. Alerts defined in prometheus-rules.yaml.

Secrets required (DO NOT store in repo):
- REDIS_PASSWORD

How to deploy
1) Add chart repo:
   helm repo add bitnami https://charts.bitnami.com/bitnami && helm repo update

2) Staging example:
   kubectl create ns staging || true
   helm upgrade --install redis-staging bitnami/redis -n staging -f values-staging.yaml --set global.redis.password="$REDIS_PASSWORD"

3) Prod example:
   kubectl create ns prod || true
   helm upgrade --install redis-prod bitnami/redis -n prod -f values-prod.yaml --set global.redis.password="$REDIS_PASSWORD"

Prometheus
- values-*.yaml enable exporter and ServiceMonitor.
- Apply prometheus-rules.yaml to the monitoring namespace or include in PrometheusRule CR.

Operational notes
- Verify pub/sub by running: redis-cli -h <host> -a <password> PUBLISH mychannel "test"
- Ensure app uses the Service DNS (redis-staging-master.redis.svc.cluster.local) and handles retries.
- For zero-downtime upgrades, use rolling update strategy (helm default for StatefulSet).

Next actions / Handoffs
- #ai-backend (Marcus): confirm desired k8s namespaces and release names (default: redis-staging / redis-prod).
- #ai-qa (Dana): once I deploy to staging, run TC04/TC06/TC11.
- #ai-security (Isabella): confirm if we must enable in-transit encryption (TLS) and credential rotation.

Files in this folder:
- values-staging.yaml
- values-prod.yaml
- prometheus-rules.yaml
