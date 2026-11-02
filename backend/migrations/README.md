# RETUNORI migrations

For local zero-setup development the application creates tables automatically. For PostgreSQL deployments use the executable baseline:

```powershell
alembic upgrade head
```

Future schema changes should be reviewed Alembic revisions rather than relying on `create_all`.

