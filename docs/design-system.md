# DevPulse interface foundation

The interface uses flat dark surfaces, restrained borders, compact controls,
and a pale blue accent. Monitoring values are not displayed until real data
exists. The current `/dashboard` route is explicitly labeled as an interface
preview; the root redirects there until the public landing page is implemented.
The workspace now requires a session. Account pages use a compact public layout
with shared fields, buttons, validation, and feedback states; see [account UI](account-ui.md).

## Tokens

Tokens live in `frontend/src/app/globals.css` and are exposed to Tailwind through
`@theme`. Use semantic names instead of introducing ad hoc status colors.

| Token          | Value     | Purpose                                  |
| -------------- | --------- | ---------------------------------------- |
| Background     | `#0d1015` | Main canvas                              |
| Surface        | `#12161d` | Sidebar, panels, dialogs                 |
| Elevated       | `#1a202a` | Hover surfaces and decorative containers |
| Border         | `#2b3340` | Decorative separation                    |
| Control border | `#62718a` | Identifiable input and button boundaries |
| Foreground     | `#edf1f7` | Primary text                             |
| Muted          | `#a3afc2` | Secondary text                           |
| Accent         | `#b0c3ff` | Actions, selected navigation, focus      |
| Success        | `#83dbb3` | Operational status                       |
| Warning        | `#efca7d` | Failure confirmation                     |
| Danger         | `#ffa0ad` | Failure and validation errors            |

Use the system sans-serif stack for interface text and the system monospace
stack for technical labels. Fonts require no external download. Body text is
14px; primary page titles are 30px; section titles are 18px. Labels use 12–14px,
with 10px reserved for short supporting labels. Spacing follows a 4px base,
usually in 8px increments. Corner radii are 4px, 6px, and 8px.

## Shared components

- `Button`: primary, secondary, and ghost variants; an icon size with a 44px
  target; explicit disabled/busy behavior. Defaults to `type="button"` to avoid
  accidental form submission. Icon-only callers must provide an accessible name.
- `TextField`: required visible label, generated or caller-supplied ID, linked
  hints/errors, native input props, and preserved caller descriptions.
- `DialogContent`: Radix-backed modal with a required title and description,
  explicit close control, focus trapping, Escape dismissal, and focus restoration.
  A drawer variant powers mobile navigation.
- `StatusIndicator`: operational, confirming failure, failing, paused, and no
  data. Every color has a visible text label. Indicators do not imply live updates.
- `EmptyState`: heading, description, and an optional real action. Never inserts
  a disabled placeholder action or invented measurements.
- `LoadingState` and `Skeleton`: one polite announcement, decorative blocks
  hidden from assistive technology, and motion disabled for reduced-motion users.
- `ErrorState`: safe visible copy, an alert announcement, and a supplied retry
  callback. It never displays exception details.

The workspace shell is kept in the `(app)` route group so later public and
authentication pages can use their own layouts. The implemented Overview and
Monitors routes appear in navigation, with the current destination highlighted.
The About dialog explains the preview's current
limits and has working dismissal controls.

## Accessibility and responsive behavior

- A skip link targets a focusable main landmark.
- The desktop sidebar changes to a modal navigation drawer below 768px.
- Resizing an open drawer to desktop closes it and focuses the main region
  rather than its now-hidden trigger.
- Focus uses a two-pixel accent outline, with four-pixel offset.
- Text meets WCAG AA contrast on the supported dark surfaces. Identifiable
  control boundaries meet 3:1 contrast. Decorative separators are quieter.
- Reduced-motion mode removes transitions, skeleton pulsing, and spinners.
- Dialogs remain scrollable at small viewport heights; the shell targets 360px
  mobile widths through desktop and supports browser zoom.
- Error and loading route boundaries use the same shared state components.

Run `npm run check` and `npm run build` from `frontend/`. Component tests cover
interaction and semantics, while contrast tests check the actual CSS tokens.
For browser review, inspect 360px, 768px, and desktop layouts; tab through the
page and dialogs; dismiss the drawer with Escape and by selecting Overview;
resize with the drawer open; check reduced motion and the missing-page link.
Do not add demonstration data to the product to test these states.
