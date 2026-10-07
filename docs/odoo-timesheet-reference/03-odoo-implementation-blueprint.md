# 03. Odoo Implementation Blueprint

## Objective

This document turns the current timesheet logic into a concrete Odoo implementation plan.

## Related reference

The implementation logic being modeled here is extracted in [04-relevant-code-extract.py](04-relevant-code-extract.py).

## Recommended Odoo approach

Use a custom module with these main models:

### 1) `x_timesheet_line`

Purpose: store each employee work entry.

Fields:

- `employee_id` — many2one to `hr.employee`
- `work_date` — date
- `work_slip_id` — many2one to `x_work_slip` or equivalent
- `operation_id` — many2one to `x_operation`
- `work_order_id` — many2one to `x_work_order`
- `hours` — float
- `paycode_id` — many2one to `x_paycode`
- `comments` — text
- `state` — selection: draft / approved / exported
- `external_reference` — text

Business constraints:

- unique constraint on `(employee_id, work_date, work_slip_id)`
- `hours >= 0`
- optional validation for date / employee / slip combinations

### 2) `x_work_slip`

Purpose: represent the work slip associated with a work order and operation.

Fields:

- `name`
- `work_order_id`
- `operation_id`
- `description`
- `active`

### 3) `x_paycode`

Purpose: represent the payroll code used when exporting hours.

Fields:

- `code`
- `name`
- `active`

### 4) `x_payroll_export`

Purpose: capture each export event.

Fields:

- `employee_id`
- `workweek_start`
- `export_date`
- `status`
- `status_detail`
- `export_type`
- `export_source`

### 5) `x_payroll_export_line`

Purpose: store each detailed exported row.

Fields:

- `export_id`
- `employee_id`
- `work_date`
- `hours`
- `paycode_id`
- `work_slip_id`
- `comments`

## Core business logic to port

### Daily totals

This maps directly to the logic in [../../timesheet.py](../../timesheet.py#L794-L831):

```python
for line in lines:
    totals.setdefault(line.work_date, 0.0)
    totals[line.work_date] += line.hours
```

### Weekly totals

Use the workweek start rule defined in [../../timesheet.py](../../timesheet.py#L1703-L1708):

```python
def get_week_start(date, week_start_day=0):
    days_to_subtract = (date.weekday() - week_start_day) % 7
    return date - timedelta(days=days_to_subtract)
```

### Payroll grouping

This matches the grouping logic in [../../timesheet.py](../../timesheet.py#L922-L996):

```python
grouped = {}
for line in export_lines:
    key = (line.work_date, line.paycode_id)
    grouped.setdefault(key, {'hours': 0.0, 'comments': line.comments})
    grouped[key]['hours'] += line.hours
```

### Total-by-operation reporting

This is the pattern in [../../timesheet.py](../../timesheet.py#L1820-L1845):

```python
def get_weekly_operation_totals(timecard_data):
    totals = {}
    for entries in timecard_data.values():
        for entry in entries:
            key = (entry['WSNumber'], entry['OpName'], entry.get('WODescription', ''), entry.get('OpCode', ''))
            totals[key]['total_hours'] += float(entry['tHoursWorked'])
```

## Recommended actions and workflows

### A) Entry actions

- create time line
- update hours
- delete line
- copy previous day / duplicate record
- calculate daily total automatically

### B) Finalization actions

- review daily totals
- review weekly totals
- approve or finalize timesheet
- prevent further edits once finalized

### C) Export actions

- run payroll export wizard
- group by employee/date/paycode
- send payload to external API
- save export log records
- mark rows as exported

### D) Audit actions

- keep immutable export records
- store status details and API response text
- allow re-export when corrected

## Suggested Odoo module layout

```text
custom_timesheet/
  __manifest__.py
  models/
    __init__.py
    timesheet_line.py
    work_slip.py
    paycode.py
    payroll_export.py
    payroll_export_line.py
  views/
    timesheet_views.xml
    payroll_export_views.xml
  wizard/
    payroll_export_wizard.py
  security/
    ir.model.access.csv
```

## Final recommendation

For Odoo, the best implementation is to treat the current app as a timesheet + payroll export system rather than just a simple hours form.

The key is to preserve:

- per-employee daily entries,
- per-date aggregation,
- work slip and operation linkage,
- pay code grouping,
- and export audit logging.

This will create a clean and maintainable Odoo architecture.

---
