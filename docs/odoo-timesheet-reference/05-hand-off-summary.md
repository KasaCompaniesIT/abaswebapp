# Hand-off Summary for Odoo Migration

## Goal

This document summarizes the timesheet hours logic from the existing application in a form that is useful for an Odoo implementation team.

## Business summary

The current application tracks employee time as a set of daily entries tied to a work slip and operation. The core business behavior is:

- each employee can log multiple time entries
- each entry is tied to a date and work slip
- hours are stored in a `TimeWorked` field
- entries are grouped by date to calculate daily totals
- summaries are built for a workweek
- payroll export groups those totals by date and pay code
- exports are logged for audit and troubleshooting

This is a complete timesheet + payroll export workflow.

## Key source references

Main code references:

- [../../timesheet.py](../../timesheet.py#L491-L535)
- [../../timesheet.py](../../timesheet.py#L780-L831)
- [../../timesheet.py](../../timesheet.py#L922-L996)
- [../../timesheet.py](../../timesheet.py#L1294-L1324)
- [../../timesheet.py](../../timesheet.py#L1459-L1568)
- [../../timesheet.py](../../timesheet.py#L1734-L1845)

Extracted code reference:

- [04-relevant-code-extract.py](04-relevant-code-extract.py)

## Business rules to preserve in Odoo

1. One employee can have multiple entries per day.
2. Each time entry belongs to a work slip and operation.
3. Duplicate employee/date/work slip entries should be blocked.
4. Hours are aggregated by date and workweek.
5. Payroll export groups by date + pay code.
6. Export records should be saved in an immutable audit log.
7. Hours may be edited after initial entry and re-exported.

## Core data model

The current app implies these objects:

- Employee
- Work Slip
- Operation
- Time Entry
- Pay Code
- Payroll Export
- Payroll Export Detail
- Export Log
- Comment / Notes

## Odoo mapping

Recommended Odoo equivalents:

- `hr.employee` for employee
- custom `x_work_slip` for work slip
- custom `x_operation` for operation
- custom `x_timesheet_line` for daily time entry
- custom `x_paycode` for payroll pay code
- custom `x_payroll_export` for export summary
- custom `x_payroll_export_line` for export details

## Core calculation pattern

The critical logic is this:

```python
SELECT WorkDate, sum(TimeWorked) as sTimeWorked
FROM TimeEntry
WHERE EmpID = ? AND WorkDate BETWEEN ? AND ?
GROUP BY WorkDate
ORDER BY WorkDate
```

This means the Odoo equivalent should calculate a daily total for each employee across the selected date range.

## Payroll grouping pattern

The existing export logic groups by:

- work date
- pay code

The equivalent Odoo implementation should aggregate line items before sending the export payload.

## Recommended implementation approach

1. Build a custom `timesheet.line` model.
2. Add a uniqueness rule by employee/date/work slip.
3. Add computed daily and weekly totals.
4. Build a payroll export wizard that groups by date and pay code.
5. Persist export log records after each API call.
6. Add a review/approval stage before export if needed.

## Bottom line

The current app is not just a simple hours tracker; it is a complete employee time capture and payroll export system. The Odoo version should preserve that workflow and business logic rather than only reproducing the UI.

---
