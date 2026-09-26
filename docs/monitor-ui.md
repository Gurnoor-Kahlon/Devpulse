# Monitor management UI

Milestone 8 connects monitor settings to the PostgreSQL API from milestone 7.
Milestone 11 adds observation freshness from the real scheduler; analytics remain
deferred and no observations are fabricated.
Start the application using the [development guide](development.md), apply
`python -m alembic upgrade head`, and use Mailpit to verify your account as
described in the [account guide](account-ui.md).

## Routes and behavior

| Route                 | Purpose                                                                             |
| --------------------- | ----------------------------------------------------------------------------------- |
| `/monitors`           | Owned monitor list, name/URL search, enabled/paused filters, pause/resume, archive. |
| `/monitors/new`       | Configuration form using the API defaults and validation bounds.                    |
| `/monitors/[id]/edit` | Edit an owned configuration with its last-read version.                             |

The desktop sidebar and mobile drawer link to Overview, Monitors, and Incidents. Monitor
names link directly to their settings; analytics/detail routes are deferred.
The account layout checks authentication on the server. FastAPI independently
enforces authentication, ownership, verification, CSRF, and quotas on every API
request. Unverified accounts get a verification link instead of the list's create
action; a direct visit to the new form also blocks creation. Enabling a paused
monitor requires verification.

TanStack Query fetches the complete owned list, following cursors if present.
With the ten-monitor account limit, local case-insensitive name/URL search and
configuration filtering remain small and cover the entire list. Loading uses
skeletons; an empty account and an empty filtered result have different messages.
Refresh failures preserve the previously loaded list and expose a retry action.
Confirmed mutation responses update cached records before a list refresh, so a
failed refresh cannot undo a successfully saved state. There is no dashboard
polling or browser-triggered probing.

Enabled is a configuration setting. New monitors display **No data** and
**Never checked**, and paused monitors display **Paused**. Accepted manual or
scheduled observations update the latest-check timestamp. Manual probes leave
health unchanged; scheduled attempts now evaluate health using the [milestone 12
incident policy](incidents.md). Each monitor links to its filtered incident history.
Milestone 11 displays **Stale observations** ahead of any saved
health label when scheduled evidence is overdue. This does not claim the target
is down. Freshness reflects the last API response; use Refresh list for an
updated reading. Visibility-aware polling remains deferred to milestone 13.
The UI never invents latency, uptime, or checks.

## Forms and concurrent changes

The create/edit forms use types generated from FastAPI OpenAPI. Client validation
covers required settings, URL syntax, and numeric limits; the API remains the
authority. Labels, hints, and field errors are associated with controls. On
validation or save failure, an alert summary receives focus and inputs retain
their values. Forms prevent repeated submissions while a save is pending.

Edits send only changed settings plus `configuration_version`; an unchanged
save still asks the API to verify the version. A stale version blocks resubmission
and offers **Reload latest settings**, explicitly explaining that reloading
replaces the unsaved draft. The editor does not refetch on window focus or
reconnect. An explicit reload failure preserves the form. Missing or archived
monitors show an unavailable message and a link back to the list.

Background session checks preserve the mounted form. A session-check outage
offers retry without discarding input; a confirmed expired/revoked session hides
the workspace and returns to login. The monitor API client also handles `401`
responses immediately. Authentication failures and validation messages never
display raw upstream response text.

Monitor writes share the existing opaque session and CSRF bootstrap. A definite
CSRF rejection is retried once after refreshing the token; uncertain network
failures are not automatically retried. After an uncertain save, the form advises
checking the list before resubmitting. Archive accepts the API's empty `204`
response. No dependency or backend contract changes are required.

## Archive and keyboard behavior

Archive opens a Radix dialog describing permanence and retained history. Initial
focus goes to **Cancel**. Escape closes the dialog and restores focus to its
trigger. Pending archive requests disable dismissal and repeated submission.
The dialog uses the version shown when it opened, even if the underlying list
refreshes. A conflict keeps the dialog open and asks the user to cancel and review
the refreshed list. Successful archive removes the row and moves focus back to
the monitor heading region.

Controls have visible focus states. Forms stack on narrow screens, URLs wrap,
and row actions wrap without horizontal scrolling. Native selects support
keyboard navigation, dialogs trap focus, and existing reduced-motion rules apply.

## Validation workflow

In `frontend/`:

```bash
npm run check
npm run api:check
npm run build
```

Start user-provided PostgreSQL and Mailpit, set `TEST_DATABASE_URL` to the dedicated
`_test` database, then run `npm run test:e2e`. See [browser test setup](account-ui.md#browser-tests).
The runner applies migrations in a fresh schema and starts the production frontend
and a test-only FastAPI process. It shuts down those processes and drops only its
own schema afterward. Monitor browser tests use saved configurations and never
contact the configured URLs.

Component/transport coverage includes validation and accessible errors, pending
saves, verification restrictions, quota failures, stale edits and reload, complete
pagination, filters, pause failures, archive keyboard focus/conflicts, empty/error
states, CSRF retries, and expiry. Account tests also verify draft preservation
during a failed session refresh. Playwright covers real persisted create/edit,
pause/resume, archive after reload, an external edit conflict, unverified access,
and layouts at 360px and desktop widths.

Browser review screenshots are written only to ignored `.cache/` files:
`monitors-desktop.png`, `monitors-mobile.png`, `monitor-form-mobile.png`, and
`monitor-archive-mobile.png`. These show synthetic test accounts and configurations,
not monitoring results or public demo data. Public product screenshots remain a
later milestone.

Development uses WSL2 Ubuntu. The historical milestone 8 validation below used
Windows; current Linux results are recorded in [scheduling](scheduling.md#validation).

Milestone 8 validation passed 56 component/transport tests and all six production
browser tests (three account and three monitor workflows), plus formatting,
lint, strict type checks, generated API-contract checks, and the production build.
Desktop/mobile screenshots were visually reviewed, including the archive dialog
after its opening animation. Temporary browser-test schemas were removed and
the project validation services were stopped afterward.
