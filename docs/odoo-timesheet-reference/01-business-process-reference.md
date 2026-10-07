# 01. Business Process Reference

## Purpose

This document captures the business behavior implemented by the current timesheet logic, so it can be used as the functional specification for an Odoo implementation.

## Core process

The application behaves as follows:

1. A user selects an employee, date, work slip, and hours.
2. A time entry is created and stored with employee ID, work date, work slip number, and worked hours.
3. The app prevents duplicate entries for the same employee/date/work slip.
4. The app aggregates hours by day and workweek.
5. Payroll export groups entries by date and pay code.
6. Export activity is logged for audit.
7. The user can update or delete entries, then re-export.

## Related reference

The underlying calculation and export logic is collected in [04-relevant-code-extract.py](04-relevant-code-extract.py).

## Key business rules

### 1) Time entry creation

The create flow is centered on `TimeEntry` and the `create_time_entry` helper in [../../timesheet.py](../../timesheet.py#L1459-L1510).

Rules:

- each time entry has an employee
- each time entry has a date
- each time entry belongs to a work slip
- each entry has a hours value stored in `TimeWorked`
- duplicate employee/date/work slip combinations are blocked

### 2) Hours updates

The update process is handled in [../../timesheet.py](../../timesheet.py#L1294-L1324).

Rules:

- an existing time entry can be edited
- the stored `TimeWorked` value is replaced
- the updated value is sent to the external system again
- the API call must succeed or the change is treated as an error

### 3) Daily totals

The app sums time entries per date in [../../timesheet.py](../../timesheet.py#L780-L831).

Logic:

- fetch all entries between a start and end date
- group by `WorkDate`
- sum `TimeWorked`
- return a daily list plus overall total

This is the key logic behind finalizing and summarizing time.

### 4) Weekly summary and approval

The code supports summary/finalization flows that rely on weekly date ranges and totals for a given employee.

These totals are used to:

- present daily total hours
- display workweek totals
- support final validation before export

### 5) Payroll export

The export flow in [../../timesheet.py](../../timesheet.py#L922-L996) groups hours by:

- work date
- paychex/pay code

Then it converts the grouped values into a payload and sends them to an external payroll endpoint.

### 6) Export logging and audit

The system records export events in `ExportLog` and `ExportLogDetail` using helpers defined around [../../timesheet.py](../../timesheet.py#L1734-L1825).

This supports:

- export date tracking
- workweek tracking
- status and detail tracking
- audit trail for employee activity

## Odoo interpretation

An Odoo implementation should preserve these five behaviors:

1. employee-level time entry capture
2. unique validation by employee/date/work slip
3. daily and weekly aggregation
4. payroll export grouping by date + pay class
5. audit logging of every export

## Recommended Odoo process

A simple Odoo equivalent would be:

1. employee logs hours on a timesheet line
2. system validates uniqueness per employee/date/project/task
3. daily totals and week totals are computed automatically
4. manager or user finalizes the sheet
5. payroll export wizard groups time by date and pay code
6. export results are saved in an audit model

---
