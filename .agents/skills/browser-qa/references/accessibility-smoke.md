# Accessibility Smoke

Use this for quick accessibility checks during browser QA. It is not a full WCAG
audit.

## Keyboard

- Primary actions are reachable with keyboard navigation.
- Focus order follows the visible flow.
- Focus is visible and not trapped outside active dialogs or menus.
- Escape or documented close controls dismiss modals, popovers, and menus.

## Names And Semantics

- Interactive controls have accessible names from text, labels, or ARIA.
- Form fields have associated labels or clear accessible names.
- Icon-only buttons expose their purpose to assistive technology.
- Headings, landmarks, and lists match the visual structure well enough for
  navigation.

## State And Feedback

- Disabled, selected, expanded, checked, invalid, and busy states are exposed
  through native elements or ARIA when applicable.
- Validation errors are announced or placed where screen-reader users can find
  them.
- Status changes that matter to task completion are visible and programmatically
  available when practical.

## Visual Accessibility

- Text and controls remain readable at the tested viewport.
- Content is not conveyed by color alone.
- Motion, animation, and loading states do not block task completion.

## Tooling

If an accessibility scanner is already configured in the repository, run the
targeted check for the scenario. Treat scanner output as evidence to triage, not
as a replacement for keyboard and user-flow inspection.
