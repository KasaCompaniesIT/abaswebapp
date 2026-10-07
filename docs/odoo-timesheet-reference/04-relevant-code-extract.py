# Relevant code extract from the current timesheet implementation.
# Source file: ../../timesheet.py

from datetime import datetime, date, timedelta

# ------------------------------------------------------------
# 1) Core time entry creation and daily aggregation
# ------------------------------------------------------------

def create_time_entry(abas_id, work_date, ws_number, time_worked=None):
    try:
        db = get_db()
        dbc = db.cursor()

        new_entry_id = dbc.execute(
            """
            INSERT INTO TimeEntry (EmpID, WorkDate, WSNumber, TimeWorked)
            OUTPUT INSERTED.EntryID
            VALUES (?, ?, ?, ?)
            """,
            (abas_id, work_date, ws_number, time_worked)
        ).fetchone()[0]

        db.commit()

        new_entry = dbc.execute(
            """
            SELECT t.EntryID AS TimeEntryID, t.WSNumber, t.WorkDate AS WorkDate,
                   ws.WSDescription, o.OpName, o.OpNameExtended,
                   t.TimeWorked AS tHoursWorked, WODescription, OpCode
            FROM TimeEntry t
            INNER JOIN WorkSlips ws ON t.WSNumber = ws.WSNumber
            INNER JOIN Operations o ON ws.OpID = o.OpID
            INNER JOIN WorkOrders wo ON ws.WONumber = wo.WONumber
            WHERE t.EntryID = ?
            """,
            (new_entry_id,)
        ).fetchone()

        if not new_entry:
            raise ValueError("Failed to fetch the newly added time entry.")

        columns = [column[0] for column in dbc.description]
        entry_dict = dict(zip(columns, new_entry))

        if "WorkDate" in entry_dict and isinstance(entry_dict["WorkDate"], (datetime, date)):
            entry_dict["WorkDate"] = entry_dict["WorkDate"].strftime("%m/%d/%y")

        for k, v in entry_dict.items():
            if isinstance(v, decimal.Decimal):
                entry_dict[k] = f"{float(v):.2f}"

        return entry_dict

    except Exception as e:
        db.rollback()
        print("Error creating time entry:", str(e))
        return None


# ------------------------------------------------------------
# 2) Update hours
# ------------------------------------------------------------

@bp.route('/timesheet/entry/update_hours/<int:entry_id>', methods=['POST'])
@login_required
def update_hours(entry_id):
    data = request.get_json()
    hours_worked = data.get('hoursWorked')
    db = get_db()
    dbc = db.cursor()
    try:
        dbc.execute(
            "UPDATE TimeEntry SET TimeWorked = ? WHERE EntryID = ?",
            (hours_worked, entry_id)
        )
        db.commit()

        time_entry = get_time_entry(entry_id=entry_id, full_details=True)
        abas_id = time_entry.EmpID
        entry_date = time_entry.WorkDate
        work_slip_id = time_entry.WSNumber
        time_worked = float(time_entry.tHoursWorked)
        op_code = time_entry.OpCode if time_entry.OpCode != '' else "E1"

        response = send_timeentry_csv_to_abas(
            abas_id, entry_date, work_slip_id, time_worked, "update_hours", op_code
        )
        if response.status_code != 200:
            raise ValueError(f"Failed to send data for {time_entry.WorkDate}.")

        return jsonify({'success': True, 'hoursWorked': f"{float(hours_worked):.2f}"})
    except Exception as e:
        db.rollback()
        print("Error updating hours:", str(e))
        return jsonify({'success': False, 'error': str(e)})


# ------------------------------------------------------------
# 3) Daily totals by date
# ------------------------------------------------------------

@bp.route('/timesheet/entry/get_final_time_entries', methods=['GET'])
@login_required
def get_final_time_entries():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        abas_id = request.args.get('abas_id')

        totalHoursWorked = 0.0

        db = get_db()
        dbc = db.cursor()

        time_entries = dbc.execute(
            """
            SELECT WorkDate, sum(TimeWorked) as sTimeWorked
            FROM TimeEntry 
            WHERE EmpID = ? AND WorkDate BETWEEN ? AND ?
            GROUP BY WorkDate
            ORDER BY WorkDate
            """,
            (abas_id, start_date, end_date)
        ).fetchall()

        if time_entries:
            time_entries_list = []
            for entry in time_entries:
                time_entries_list.append({
                    "WorkDate": entry.WorkDate.strftime('%m/%d/%y'),
                    "tHoursWorked": entry.sTimeWorked
                })
                totalHoursWorked += float(entry.sTimeWorked) if isinstance(entry.sTimeWorked, decimal.Decimal) else entry.sTimeWorked

            return jsonify({
                "success": True,
                "time_entries": time_entries_list,
                "totalHoursWorked": totalHoursWorked
            }), 200
        else:
            return jsonify({"success": True, "time_entries": None, "totalHoursWorked": 0}), 200
    except Exception as e:
        print("Error fetching time entries:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 4) Payroll export grouping logic
# ------------------------------------------------------------

@bp.route('/timesheet/payroll_export', methods=['POST'])
def payroll_export():
    try:
        data = request.get_json()
        paychex_code_mapping = get_paychex_codes()

        grouped = {}
        for entry in data.get("time_entries", []):
            date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
            date_str = date_obj.strftime("%m/%d/%Y")

            paychex_code = paychex_code_mapping.get(int(entry["paychexCode"]), entry["paychexCode"])
            hours = float(entry["hours"])
            comments = entry.get("comments") or "null"
            key = (date_str, paychex_code)

            if key not in grouped:
                grouped[key] = {"hours": 0.0, "comments": comments}
            grouped[key]["hours"] += hours

            if comments != "null":
                grouped[key]["comments"] = comments

        combined_time_entries = [
            {
                "abas_id": data.get("abas_id"),
                "date": date,
                "paychexCode": paychex_code,
                "hours": f"{values['hours']:.2f}",
                "comments": values["comments"]
            }
            for (date, paychex_code), values in grouped.items()
        ]

        converted_data = {
            "abas_id": data.get("abas_id"),
            "total_hours": data.get("total_hours"),
            "time_entries": combined_time_entries
        }

        response = requests.post("http://abas.kasa.kasacontrols.com:8000/payroll_import", json=converted_data)
        return response

    except Exception as e:
        print("Error in payroll export:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 5) Export log records
# ------------------------------------------------------------

def add_exportlog_summary(abas_id=None, export_date=None, export_work_week=None, export_status=None, export_status_detail=None, export_type=None, export_source=None):
    db = get_db()
    dbc = db.cursor()
    try:
        if abas_id is None or export_date is None or export_work_week is None:
            raise ValueError("abas_id, export_date, and export_work_week must be provided.")

        export_id = dbc.execute(
            """
            INSERT INTO ExportLog (EmpID, exportDate, exportWorkWeek, exportStatus, exportType, exportStatusDetail, exportSource)
            OUTPUT INSERTED.exportID
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (abas_id, export_date, export_work_week, export_status, export_type, export_status_detail, export_source)
        ).fetchone()[0]
        db.commit()
        return export_id

    except Exception as e:
        db.rollback()
        print("Error adding export log summary:", str(e))
        return None


def add_exportlog_entry(export_id=None, emp_id=None, work_date=None, time_worked=None, paychex_code=None, work_slip=None, comments=None):
    db = get_db()
    dbc = db.cursor()
    try:
        if export_id is None or emp_id is None or work_date is None:
            raise ValueError("export_id, emp_id, and work_date must be provided.")

        dbc.execute(
            """
            INSERT INTO ExportLogDetail (exportID, empID, workDate, timeWorked, paychexCode, workSlip, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (export_id, emp_id, work_date, time_worked, paychex_code, work_slip, comments)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("Error adding export log entry:", str(e))


# ------------------------------------------------------------
# 6) Weekly operation totals
# ------------------------------------------------------------

def get_weekly_operation_totals(timecard_data):
    totals = {}
    for entries in timecard_data.values():
        for entry in entries:
            key = (entry['WSNumber'], entry['OpName'], entry.get('WODescription', ''), entry.get('OpCode', ''))

            if key not in totals:
                totals[key] = {
                    'WSNumber': entry['WSNumber'],
                    'OpName': entry['OpName'],
                    'WODescription': entry.get('WODescription', ''),
                    'OpCode': entry.get('OpCode', ''),
                    'total_hours': 0.0
                }
            totals[key]['total_hours'] += float(entry['tHoursWorked'])
    return list(totals.values())


# ------------------------------------------------------------
# 7) Week start helper
# ------------------------------------------------------------

def get_week_start(date, week_start_day=0):
    """Return the start of the week for a given date and week_start_day (0=Mon, 5=Sat)."""
    days_to_subtract = (date.weekday() - week_start_day) % 7
    return date - timedelta(days=days_to_subtract)


# ------------------------------------------------------------
# 8) Pay code lookup helpers
# ------------------------------------------------------------

def get_paychex_codes():
    db = get_db()
    dbc = db.cursor()
    paychex_codes = dbc.execute(
        "SELECT PayID, PayChex FROM paychex WHERE inUse = 1 ORDER BY PayChex"
    ).fetchall()
    paychex_mapping = {row.PayID: row.PayChex for row in paychex_codes}
    return paychex_mapping


def lookup_paychex_id(paychex_code):
    db = get_db()
    dbc = db.cursor()

    paychex_code = dbc.execute(
        "SELECT PayID, PayChex, PayDescription FROM paychex WHERE PayChex = ? ORDER BY PayChex",
        paychex_code
    ).fetchone()

    paycode_id = paychex_code.PayID if paychex_code else None
    return paycode_id
