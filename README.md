# Expenses Tracker

A REST API for tracking personal expenses, built with **Django** and **Django REST Framework**.
Users can organise expenses into categories and tags, record how each expense was paid, set
monthly budgets, schedule recurring expenses, get monthly reports and statistics, export to CSV,
and track saving goals.

## Tech stack

| Package | Version |
| --- | --- |
| Python | 3.15 |
| Django | 6.1.2 |
| djangorestframework | 3.18.3 |
| djangorestframework-simplejwt | 5.5.1 |
| django-filter | 26.2 |
| Database | SQLite (`db.sqlite3`) |

---

## Getting started

### 1. Clone the repository

```bash
git clone <repository-url>
cd "DRF Expense Tracker"
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (cmd)
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

### 3. Install the dependencies

```bash
pip install Django==6.1.2 djangorestframework==3.18.3 djangorestframework-simplejwt==5.5.1 django-filter==26.2
```

### 4. (Optional) Configure the default superuser

Migration `0002_seed_super_user` creates a superuser automatically. Its credentials come from
these environment variables, with defaults if they are not set:

| Variable | Default |
| --- | --- |
| `DJANGO_SUPERUSER_USERNAME` | `admin` |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` |
| `DJANGO_SUPERUSER_PASSWORD` | `Admin12345!` |

Set them **before** running `migrate` if you want different credentials:

```powershell
# PowerShell
$env:DJANGO_SUPERUSER_USERNAME = "myadmin"
$env:DJANGO_SUPERUSER_PASSWORD = "MyStrongPassword!"
```

```bash
# macOS / Linux
export DJANGO_SUPERUSER_USERNAME=myadmin
export DJANGO_SUPERUSER_PASSWORD='MyStrongPassword!'
```

### 5. Apply the migrations

```bash
python manage.py migrate
```

### 6. (Optional) Load sample data

```bash
python seed.py            # adds users alice & bob (password: Passw0rd!123) with categories and expenses
python seed.py --reset    # deletes existing non-superuser users, categories and expenses first
```

### 7. Run the server

```bash
python manage.py runserver
```

The API is now available at <http://127.0.0.1:8000/> and the Django admin at
<http://127.0.0.1:8000/admin/>.

---

## Useful commands

| Task | Command |
| --- | --- |
| Run the development server | `python manage.py runserver` |
| Run on a different port | `python manage.py runserver 8080` |
| Create migrations after changing models | `python manage.py makemigrations` |
| Create migrations for the `api` app only | `python manage.py makemigrations api` |
| Apply migrations | `python manage.py migrate` |
| Show migrations and their status | `python manage.py showmigrations` |
| Show the SQL of a migration | `python manage.py sqlmigrate api 0007` |
| Roll back to a specific migration | `python manage.py migrate api 0006` |
| Create another superuser | `python manage.py createsuperuser` |
| Run all tests | `python manage.py test` |
| Run one test class | `python manage.py test api.tests.ContributionsTest` |
| Open a Django shell | `python manage.py shell` |
| Check the project for problems | `python manage.py check` |
| Seed sample data | `python seed.py` / `python seed.py --reset` |

---

## Authentication

The API uses **JWT** (via SimpleJWT). Session authentication is also enabled, so you can use the
browsable API after logging in through `/admin/`.

1. **Register** – `POST /users/` with `username`, `email`, `password` (no authentication needed).
2. **Get tokens** – `POST /api/token/` with `username` and `password`. Returns `access` and `refresh`.
3. **Call the API** – send the header `Authorization: Bearer <access token>`.
4. **Refresh** – `POST /api/token/refresh/` with `refresh` to get a new access token.

| Setting | Value |
| --- | --- |
| Access token lifetime | 15 minutes |
| Refresh token lifetime | 7 days |
| Refresh token rotation | On (each refresh returns a new refresh token) |

---

## API endpoints

All endpoints except `POST /users/` and the token endpoints require authentication.

| Resource | Endpoints |
| --- | --- |
| Users | `POST /users/` |
| Categories | `/categories/`, `/categories/{id}/` |
| Expenses | `/expenses/`, `/expenses/{id}/` |
| Expense statistics | `GET /expenses/statistics/` |
| Expense trash | `GET /expenses/trash/` |
| Restore expense | `POST /expenses/{id}/restore/` |
| Export expenses (CSV) | `GET /expenses/export/` |
| Budgets | `/budgets/`, `/budgets/{id}/` |
| Recurrent expenses | `/recurrent-expenses/`, `/recurrent-expenses/{id}/` |
| Generate recurrent expenses | `POST /recurrent-expenses/generate/` with `{"until_date": "YYYY-MM-DD"}` |
| Tags | `/tags/`, `/tags/{id}/` |
| Monthly report | `GET /reports/monthly/?month=MM&year=YYYY` |
| Saving goals | `/saving-goals/`, `/saving-goals/{id}/` |
| Goal contributions | `GET` / `POST /saving-goals/{id}/contributions/` |
| Single contribution | `GET` / `PUT` / `PATCH` / `DELETE /contributions/{id}/` |
| Payment methods | `/payment-methods/`, `/payment-methods/{id}/` |
| Set default payment method | `POST /payment-methods/{id}/set-default/` |
| Payment method statistics | `GET /payment-methods/statistics/` |

### Filtering, search and ordering on expenses

`GET /expenses/` (and `/expenses/statistics/`, `/expenses/export/`) accept:

| Parameter | Example | Meaning |
| --- | --- | --- |
| `category` | `?category=<uuid>` | Expenses in one category |
| `amount_min` / `amount_max` | `?amount_min=10&amount_max=50` | Amount range (inclusive) |
| `date_from` / `date_to` | `?date_from=2026-01-01&date_to=2026-01-31` | Date range (inclusive) |
| `tags` | `?tags=<uuid1>,<uuid2>` | Expenses that have **any** of these tags |
| `payment_method` | `?payment_method=<uuid>` | Expenses paid with one payment method |
| `payment_method__isnull` | `?payment_method__isnull=true` | `true`: expenses with no payment method; `false`: expenses that have one |
| `search` | `?search=coffee` | Search in the title |
| `ordering` | `?ordering=-amount` | Sort by `amount` or `date` (`-` for descending) |

### Filtering saving goals

`GET /saving-goals/?completed=true` or `?completed=false`.

---

## Business rules and design decisions

### Users and data ownership

- A custom `User` model (`api.User`, extending `AbstractUser`) is used from the start so the user
  model can be extended later without a painful migration.
- **Every record belongs to a user.** The owner is always taken from the authenticated request
  (`perform_create`); clients cannot set or change the `user` field.
- **Regular users only see their own data.** Every list/detail query is filtered by the current
  user. Requesting another user's object returns **404**, not 403, so the API does not reveal
  that the object exists.
- **Staff users can see everyone's data** (categories, expenses, budgets, tags, goals, etc.).
- **Cross-user references are rejected.** An expense, budget or recurrent expense can only use a
  category owned by the same user, and an expense can only use the user's own tags and payment
  method.
- All primary keys are **UUIDs**, so IDs cannot be guessed or enumerated.

### Amounts

- All money fields are `Decimal` with 2 decimal places (never floats) to avoid rounding errors.
- Every amount (expense, budget, recurrent expense, goal target, contribution) **must be greater
  than 0**. This is enforced both by validators and by database `CHECK` constraints, so it holds
  even for data written outside the API.

### Categories

- Category names cannot be empty (database constraint).
- Deleting a category deletes its expenses, budgets and recurrent expenses (cascade).

### Expenses

- Titles cannot be empty.
- **Soft delete:** `DELETE /expenses/{id}/` does not remove the row. It sets `is_deleted = True`,
  so the expense disappears from normal listings, statistics, reports and exports but can be
  recovered.
  - `GET /expenses/trash/` lists soft-deleted expenses.
  - `POST /expenses/{id}/restore/` brings one back.
- **Statistics** (`/expenses/statistics/`) return the number of expenses, the total amount and the
  total per category. They respect the same filters as the expense list.
- **CSV export** (`/expenses/export/`) always exports only the requesting user's own non-deleted
  expenses (also for staff) and respects the expense filters.

### Tags

- A tag name is **unique per user** (two users can both have a "travel" tag, but one user cannot
  have it twice). A duplicate returns a validation error with code `duplicate_tag_name`.
- Tag names cannot be empty.
- An expense can have many tags; filtering by several tags returns expenses that have any of them,
  without duplicates.

### Payment methods

- Each user creates their own payment methods (for example *Cash*, *Visa*, *Bank Transfer*).
  A payment method has a `name`, an `is_default` flag (default `false`) and a `created_at`
  timestamp.
- Names cannot be empty, and a user cannot have two payment methods with the same name,
  **ignoring case** (*Visa* and *visa* count as the same). Two different users can both have
  *Visa*. This is enforced by database constraints.
- A user can have **only one default** payment method (database constraint).
  `POST /payment-methods/{id}/set-default/` makes a method the default and, in the same
  transaction, removes the default flag from the user's previous default.
- Users can only see and use their own payment methods. Another user's payment method returns
  **404**.

#### Payment methods on expenses

- An expense can have **one** payment method, and a payment method can be used by many expenses.
  Set it with the `payment_method` field (a payment method UUID) when creating or updating an
  expense. Expense responses also include a read-only `payment_method_name`.
- The field is **optional**: expenses without a payment method, including all expenses created
  before this feature, stay valid and have `payment_method: null`.
- Using another user's payment method on an expense returns a validation error:
  *"This payment method does not belong to you."*
- **Deleting a payment method keeps its expenses.** Their `payment_method` is set to `null`.

#### Payment method statistics

`GET /payment-methods/statistics/` returns one row per payment method for the requesting user's
non-deleted expenses (staff see all users):

```json
[
  {"payment_method_id": null, "name": null, "total_spent": "5864.00", "expense_count": 77},
  {"payment_method_id": "8df13687-098c-41cb-a272-eb4f1e0e1e7b", "name": "Cash", "total_spent": "200.00", "expense_count": 1}
]
```

The row with `null` id and name groups the expenses that have no payment method.

### Budgets

- A budget is set **per user, per category, per month** (`year` + `month`). Only one budget can
  exist for the same user/category/month.
- `month` must be 1–12 and `year` must be 2000 or later.
- Each budget response includes computed fields:
  - `spent` – total of the user's expenses in that category for that month
  - `remaining` – `amount - spent` (can be negative when over budget)
  - `percentage_used` – `spent / amount * 100`, rounded to 2 decimals (can exceed 100)

### Recurrent expenses

- A recurrent expense is a **template** (title, amount, category, start date, frequency) that
  produces real expenses. Frequencies: `daily`, `weekly`, `monthly` (default).
- Expenses are **generated on demand**, not automatically: `POST /recurrent-expenses/generate/`
  with an `until_date` creates every missing occurrence from `start_date` up to and including
  `until_date`, for all of the user's **active** templates (`is_active = True`).
- **Generation is idempotent.** Occurrences that already exist are skipped, and a database
  constraint makes a template/date pair unique, so calling `generate` several times never creates
  duplicates. The response says how many expenses were created.
- **Monthly dates keep the original day where possible.** If the day doesn't exist in a month, the
  last day of that month is used, and the next month goes back to the original day
  (Jan 31 → Feb 28 → Mar 31, not Mar 28).
- Generated expenses are dated at midnight of the scheduled day and are linked to their template.
- Deleting a template **keeps** the expenses it already generated (the link is set to `NULL`).

### Monthly report

`GET /reports/monthly/?month=MM&year=YYYY` returns, for the requesting user's non-deleted
expenses:

- `total_spent` and `expense_count` for the month
- `largest_expense` (title and amount), or `null` if there are none
- `previous_month_total`
- `change_percentage` – change compared with the previous month, rounded to 2 decimals; `null`
  when the previous month total is 0 (a percentage change from 0 is undefined)

Months roll over across years correctly (the month before January 2026 is December 2025).

### Saving goals and contributions

- A goal has a title, a `target_amount` and a `target_date`. A user cannot create two identical
  goals (same title, target amount and target date).
- Users add money to a goal through **contributions** (`amount` + `date`). Contributions are
  created only through `/saving-goals/{id}/contributions/`, so a contribution always belongs to
  one of the user's goals.
- Goal responses include values computed from the contributions:
  - `remaining_amount` – `target - total saved`, never below 0
  - `progress_percentage` – `total saved / target * 100`, capped at 100
  - `is_completed` – `true` when total saved ≥ target
- Saving more than the target is allowed; the goal simply shows as completed at 100%.
- `?completed=true|false` on the goal list uses the same "total saved ≥ target" rule.
- Deleting a goal deletes its contributions.

### Time zone

- Time zone support is on and the server time zone is **UTC**. Expense dates are stored as
  time-zone-aware datetimes.

---

## Running the tests

```bash
python manage.py test
```

The tests (in [api/tests.py](api/tests.py)) cover soft delete and restore, data privacy between
users, month calculations, recurrent expense scheduling and generation, tag ownership validation,
and saving goal contributions.

---

## Notes for production

This project is configured for local development. Before deploying:

- Move `SECRET_KEY` out of `config/settings.py` into an environment variable.
- Set `DEBUG = False` and fill in `ALLOWED_HOSTS`.
- Change the default superuser password.
- Consider PostgreSQL instead of SQLite.
