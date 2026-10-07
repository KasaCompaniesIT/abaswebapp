# Odoo Timesheet Reference

This folder contains the reference documents and the extracted code logic from the current timesheet implementation in the application.

## Files

- [01-business-process-reference.md](01-business-process-reference.md) — process and workflow reference
- [02-data-model-reference.md](02-data-model-reference.md) — model and data structure reference
- [03-odoo-implementation-blueprint.md](03-odoo-implementation-blueprint.md) — Odoo implementation plan
- [04-relevant-code-extract.py](04-relevant-code-extract.py) — extracted logic from the current application

## Source context

The figures and rules below are based on the current logic in:

- [../../timesheet.py](../../timesheet.py)
- [../../admin.py](../../admin.py)
- [04-relevant-code-extract.py](04-relevant-code-extract.py)

## Summary

The existing app implements a timesheet flow with these key steps:

1. Employee creates a time entry for a date and work slip.
2. Hours are recorded as `TimeWorked` for the entry.
3. Daily totals are calculated by summing hours for a date.
4. Weekly payroll exports group entries by date and pay code.
5. Entries can be updated or deleted and re-exported.
6. Export activity is logged for audit and troubleshooting.

This is a strong starting point for a corresponding Odoo design.
