# Deployment Documentation

This folder covers **cloud deployment** of Football Hub. It complements —
does not replace — the existing local/manual deployment documentation:

| Guide | Covers |
|---|---|
| [../deployment.md](../deployment.md) | Full local setup walkthrough (clone → Docker Compose → running site), plus the manual single-host production Docker Compose combination (`docker-compose.yml` + `docker-compose.prod.yml`) |
| [../docker.md](../docker.md) | Day-to-day Docker Compose commands, networking, health checks, and platform-portability notes |
| [../architecture/deployment-architecture.md](../architecture/deployment-architecture.md) | *Why* the Docker/Nginx/Daphne architecture is shaped the way it is — read this first if you want the reasoning behind the choices these cloud guides build on |
| **[aws.md](aws.md)** | Production deployment to **Amazon Web Services** — ECS Fargate, RDS PostgreSQL, ElastiCache Redis, ECR, ALB, Route 53, ACM |
| **[gcp.md](gcp.md)** | Production deployment to **Google Cloud Platform** — Cloud Run, Cloud SQL, Memorystore, Artifact Registry, Cloud DNS |

## Which guide do I want?

- **Just running the app locally?** → [../deployment.md](../deployment.md)
- **Deploying to a single VM/host you manage yourself, with Docker Compose?** → [../deployment.md §20](../deployment.md#20-production-deployment)
- **Deploying to AWS as a managed, scalable service?** → [aws.md](aws.md)
- **Deploying to GCP as a managed, scalable service?** → [gcp.md](gcp.md)

## Baseline this documentation assumes

Both cloud guides deploy the **same Docker image** built from this
repository's `Dockerfile` — nothing about the application, its container
image, or its startup sequence (`docker/entrypoint.sh`: wait for DB →
migrate → `setup_roles` → `backfill_user_roles` → conditionally
`collectstatic` → serve) changes between local Docker Compose and either
cloud. What changes is *what runs the container* (Fargate vs. Cloud Run),
*what provides Postgres/Redis* (managed services instead of sibling
containers), and *what serves `/media/`* (see each guide's Static and
Media Files section — this is the one place both guides ask you to make a
deliberate choice, because the current codebase has no S3/Cloud Storage
integration built in; see [Known limitations](#known-limitations-carried-into-both-guides)).

Both guides assume you've already read [../deployment.md §1–§4](../deployment.md)
(project overview, prerequisites, environment variables) — they don't
repeat that material, only what's different in the cloud.

## Known limitations carried into both guides

These are gaps in the *current application code*, not gaps in this
documentation. Both guides call them out explicitly at the point they
matter, rather than silently working around them:

1. **No object-storage integration.** `requirements.txt` does not include
   `django-storages` (or `boto3`/`google-cloud-storage`), and
   `config/settings.py` has no `STORAGES`/`DEFAULT_FILE_STORAGE` override.
   `ImageField`/`FileField` uploads (`Post.featured_image`,
   `CustomUser.avatar`) always write to the local filesystem
   (`MEDIA_ROOT`) via Django's default storage backend. Both guides
   document the no-code-change option (a shared network filesystem — EFS
   on AWS, a Cloud Storage FUSE volume mount on GCP — reusing the same
   Nginx-serves-`/media/` pattern `docker-compose.prod.yml` already uses)
   and name direct S3/Cloud Storage object-storage integration as a
   **future application change**, not something silently added here.
2. **No application health-check endpoint.** The `web` service's Docker
   healthcheck is a bare TCP connect (see [../docker.md](../docker.md)).
   Both guides use that same shallow check for ALB/Cloud Run health
   checks — it confirms the process is listening, not that it can reach
   the database.
3. **`CSRF_TRUSTED_ORIGINS` is not set** anywhere in `config/settings.py`.
   This is usually fine for a single production domain served over HTTPS
   with a correctly configured proxy, but see each guide's Troubleshooting
   section for when it becomes necessary and what adding it would require.
4. **Migrations run automatically on every container start**
   (`docker/entrypoint.sh`). This is safe with exactly one running
   instance (true for local Docker Compose today). Both cloud guides flag
   where this needs a deliberate decision once more than one task/instance
   can start concurrently — see each guide's Database Migration Strategy
   section.
