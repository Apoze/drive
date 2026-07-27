# Visual Checklist

Use this checklist for UI, layout, and responsive checks.

## Page Health

- no blank screen after load;
- no uncaught console errors related to the scenario;
- no failed critical network requests;
- loading, empty, success, and error states are coherent;
- focus and keyboard navigation work for the main interaction when practical.

## Layout

- no overlapping text or controls;
- no clipped buttons, labels, menus, dialogs, or table cells;
- sticky headers, sidebars, overlays, and modals remain usable;
- scroll containers scroll in the intended direction;
- viewport changes do not hide primary actions.

## Interaction

- buttons and links have visible feedback;
- disabled and loading states prevent duplicate actions;
- form validation messages appear near the relevant field;
- navigation leaves the app in a recoverable state;
- uploaded, downloaded, previewed, or edited items match the expected result.

## Evidence

Capture screenshots for:

- a passed critical state;
- each distinct visual defect;
- confusing or ambiguous rendering;
- before/after comparisons when validating a fix.
