# 02. Data Model Reference

## Goal

This document describes the data model implied by the current application so it can be translated to Odoo models.

## Related reference

The current calculation and export logic is captured in [04-relevant-code-extract.py](04-relevant-code-extract.py).

## Main entities

### 1) Employee

The app references employee records through `EmpID` and `Employee` data.

Typical properties:

- `EmpID`
- `EmpName`
- `Dept`
- `Supervisor`
- `isHourly`
- `PayChexID`
- `SalaryPlusStart`

The employee record usage appears in [../../timesheet.py](../../timesheet.py#L846-L872) and in the admin management code in [../../admin.py](../../admin.py#L291-L341).

### 2) Work slip / operation

The app ties time entries to work slips and operations.

Important fields:

- `WSNumber`
- `WONumber`
- `WSDescription`
- `OpID`
- `OpCode`
- `OpName`
- `OpNameExtended`
- `hideFromUse`

This is the core relationship behind the hours calculation and reporting.

### 3) Time entry

This is the main transactional record.

Fields implied by the code:

- `EntryID`
- `EmpID`
- `WorkDate`
- `WSNumber`
- `TimeWorked`

The main insert/update logic is in:

- [../../timesheet.py](../../timesheet.py#L1459-L1510)
- [../../timesheet.py](../../timesheet.py#L1294-L1324)

This is the center of the system.

### 4) Pay code

The app uses pay codes to classify exported hours.

Fields include:

- `PayID`
- `PayChex`
- `PayDescription`
- `inUse`

Mapping logic appears in [../../timesheet.py](../../timesheet.py#L1434-L1455).

### 5) Payroll export records

The export summary table stores one row per export event.

Likely fields:

- `EmpID`
- `exportDate`
- `exportWorkWeek`
- `exportStatus`
- `exportStatusDetail`
- `exportType`
- `exportSource`

This is created in [../../timesheet.py](../../timesheet.py#L1734-L1779).

### 6) Export detail records

The detail table stores each individual line exported.

Likely fields:

- `exportID`
- `empID`
- `workDate`
- `timeWorked`
- `paychexCode`
- `workSlip`
- `comments`

This pattern is implemented in [../../timesheet.py](../../timesheet.py#L1780-L1825).

### 7) Comments

There is a `TimesheetComments` store for employee notes.

Relevant logic:

- [../../timesheet.py](../../timesheet.py#L1675-L1740)

## Core relationships

The app effectively behaves like this:

- Employee has many Time Entries
- Work Slip belongs to a Work Order and Operation
- Time Entry references Work Slip and Employee
- Export Log references Employee and Work Week
- Export Detail references Export Log and each line item
- Pay Code is assigned to export lines

## Odoo model mapping

A practical Odoo translation would be:

- `hr.employee` or custom employee model
- `project.task` or custom `work.order` model
- custom `timesheet.line`
- custom `payroll.code`
- custom `payroll.export`
- custom `payroll.export.line`
- custom `timesheet.comment`

## Recommended design rules

Use these business rules when modeling the system:

- one employee can have many entries
- one work slip can have many entries across dates
- one date could hold multiple work slips per employee
- hours are stored as decimals to support quarter-hour precision
- export lines are grouped by date and pay code
- export events should be immutable audit records

---
