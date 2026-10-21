# django_shop
Django API for Shop

## API documentation

Install dependencies with `uv sync --frozen`. Before running with the existing
`DEBUG=False` setting, collect local Swagger UI and ReDoc assets:

```sh
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver
```

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI: `/api/schema/`

All three routes require a valid JWT and the existing shop role `admin`, both
locally and in production. Django's `is_staff` flag alone does not grant access.
Sign in as an administrator through the existing Vue application to set the
HttpOnly `auth_token` cookie, then open the documentation in the same browser.
Header-based access (`Authorization: Bearer <JWT>`) is also supported. Swagger's
**Authorize** accepts the JWT without the `Bearer` prefix. Tokens are not persisted
by Swagger across reloads. Logout clears the cookie; issued JWTs retain their
existing validity until expiry.

The schema preserves the existing API, including its status codes and response
shapes. `OrderDetail/{order_id}` GET uses an order ID, while DELETE uses a position
ID. The existing Product DELETE handler can raise a server error when its image
directory does not exist; this behavior is documented without changing it.

Validation:

```sh
uv run python manage.py check
uv run python manage.py test
uv run python manage.py spectacular --validate --fail-on-warn --file /tmp/django-shop-schema.yaml
uv run python manage.py makemigrations --check --dry-run
```

### PythonAnywhere

After pushing and reviewing the changes, run in the existing project directory:

```sh
git pull --ff-only
uv sync --frozen
uv run python manage.py check
uv run python manage.py spectacular --validate --fail-on-warn --file /tmp/django-shop-schema.yaml
uv run python manage.py collectstatic --noinput
```

Use the same Python environment for the web application and `uv` (the project
requires Python 3.14). Keep the existing environment variables and WSGI setup.
On the **Web** tab, verify the `/static/` mapping points to the absolute
`<project-directory>/staticfiles` path, then **Reload** the application. Verify
anonymous access is denied and an administrator can open the docs and load the
schema and local assets. No database migrations are required by this change.

Static file setup: https://help.pythonanywhere.com/pages/DjangoStaticFiles/
