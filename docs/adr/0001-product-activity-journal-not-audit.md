# Keep item activity separate from compliance audit

The item activity journal is a product history for regular Drive items, not a
security or compliance audit log. It records successful direct actions for the
item, is visible only to its owners and administrators, and is deleted with the
item on permanent deletion; mounted entries, organization-wide history,
exports, and configurable retention remain outside this boundary. This keeps
the first version aligned with Drive's stable item identity and permission
model without creating an immutable audit system whose retention and access
obligations would be materially different.
