from collections import defaultdict
import csv
import decimal
import os
import pandas as pd
import pyodbc
import requests

from datetime import datetime, timedelta, date

from flask import (
    Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort, Unauthorized, Forbidden, NotFound
from auth import login_required
from db import get_db
#from config import ABAS_SERVER


bp = Blueprint('timesheet', __name__)

@bp.route("/timesheet")
@login_required
def index():
    return render_template("timesheet/index.html")

@bp.route("/timesheet/entry", methods=('GET', 'POST'))
@login_required
def entry():
    print("getUserID")

    abas_ID = ""
    search_ID = ""
    abasUser = None
    error = None
    isMxEmp = False
    weekday_start = 0  # 0=Monday, 5=Saturday

    if request.method == 'POST' or g.user.EmpID != 0:
        if request.method == 'POST':
            print("POST")
            button_clicked = request.form.get('button')
            startDate = request.form.get('startDate')  # Get the startDate from the form
            abas_ID = request.form['abas_ID']
            search_ID = abas_ID  # Store the original ID for error messages
            print("selected ID: " + abas_ID)
        
            # Validate that abas_ID is an integer
            lookupByName = False
            if not abas_ID.isdigit():
                lookupByName = True
                abas_ID += '%'
                # flash("Abas User ID must be a valid integer.", "error")
                # return render_template('timesheet/entry.html', abasID=abas_ID)
        else:
            abas_ID = g.user.EmpID
            print("user ID: " + str(abas_ID))
            lookupByName = False
            startDate = ""
            button_clicked = ""

        db = get_db()
        dbc = db.cursor()

        if lookupByName:
            abasUser = dbc.execute(
                "SELECT e.*, s.EmpName as SupervisorName FROM employee as e "
                "INNER JOIN employee as s ON e.Supervisor = s.Emp WHERE e.emp LIKE ?", 
                (abas_ID,)
            ).fetchone()
            if abasUser:
                abas_ID = abasUser.Emp.strip()
            else:
                error = "No user found with the given name."
        else:
            abasUser = dbc.execute(
                "SELECT e.*, s.EmpName as SupervisorName FROM employee as e "
                "INNER JOIN employee as s ON e.Supervisor = s.Emp WHERE e.empid = ?", 
                abas_ID
            ).fetchone()
            if not abasUser:
                error = "No user found with the given ID."
        
        
        if abasUser is None:
            abas_ID = g.user.EmpID
            print("user ID: " + str(abas_ID))
            lookupByName = False
            startDate = ""
            button_clicked = ""
            
            abasUser = dbc.execute(
                "SELECT e.*, s.EmpName as SupervisorName FROM employee as e "
                "INNER JOIN employee as s ON e.Supervisor = s.Emp WHERE e.empid = ?", 
                abas_ID
            ).fetchone()
            
            error = "No user found with the given ID ('" + search_ID + "'). Please check the ID and try again."
            flash(error)

        #print (abasUser)        
        if abasUser:     
            # check if logged in user matches the selected user
            if g.user.EmpID != abasUser.EmpID and g.user.Emp != abasUser.Supervisor:       
                if g.user.isAdmin == 0:
                    error = "You are not authorized to view this user's timesheet."
                    flash(error)
                    return render_template('timesheet/entry.html')
            
            if abasUser.isMxEmp:
                isMxEmp = True
                weekday_start = 0 #Leaving like non-mx employees for now. #5 Saturday as the start of the week for MX employees
            
            # Parse the startDate into a datetime object
            if startDate:
                startDate = datetime.strptime(startDate, "%Y-%m-%d").date()
            else:
                startDate = datetime.now().date()

            # Adjust the startDate based on the button clicked
            if button_clicked == "btnPrev":
                startDate -= timedelta(days=7)
            elif button_clicked == "btnNext":
                startDate += timedelta(days=7)
            else:
                startDate = datetime.now().date()
                
            # Calculate the start and end of the week
            startOfPrevWeek = get_week_start(startDate, weekday_start)
            endOfPrevWeek = startOfPrevWeek + timedelta(days=6)

            # Determine if adding/finalizing time is allowed
            now = datetime.now()
            this_week_start = get_week_start(now.date(), weekday_start)
            last_week_start = this_week_start - timedelta(days=7)
            
            # True if viewing the current week
            is_current_week = (startOfPrevWeek == this_week_start)
            
            is_future_week = (startOfPrevWeek > this_week_start)
            
            # True if viewing the previous week, and it's Monday before noon
            is_previous_week_allowed = (
                startOfPrevWeek == last_week_start and
                now.weekday() == weekday_start and
                now.hour < 12
            )

            can_add_or_finalize = is_current_week or is_previous_week_allowed or is_future_week


            # Generate a list of dates for the previous week
            # dateRangePrevWeek = [
            #     (startOfPrevWeek + timedelta(days=i)).strftime("%m/%d/%y")
            #     for i in range((endOfPrevWeek - startOfPrevWeek).days + 1)
            # ]
            today = datetime.now().date()
            current_month = today.month

            dateRangePrevWeek = [
                {
                    "date": (startOfPrevWeek + timedelta(days=i)).strftime("%m/%d/%y"),
                    "isHoliday": dbc.execute(
                        "SELECT 1 FROM Holidays WHERE holidayDate = ?",
                        ((startOfPrevWeek + timedelta(days=i)).strftime("%Y-%m-%d"),)
                    ).fetchone() is not None,
                    "is_locked": (
                        # If today is the 1st and not monday and not the weekend and before 10am, unlock all previous month days for this week
                        not (
                            #Not Monday, not weekend, and before 10am on the 1st day of the month
                            now.weekday() > 0 and now.weekday() < 5 and now.day == 1 and now.hour < 10 and
                            (startOfPrevWeek + timedelta(days=i)).month < current_month
                        )
                        and
                        # Otherwise, lock previous month days as usual
                        (startOfPrevWeek + timedelta(days=i)).month != current_month and (startOfPrevWeek + timedelta(days=i)).month < current_month
                        
                        #old logic                        
                        # Lock if not in current month (existing rule)
                        #(startOfPrevWeek + timedelta(days=i)).month != current_month and (startOfPrevWeek + timedelta(days=i)).month < current_month
                        # For MX: Lock Sat/Sun if after 12pm on Monday
                        # or (
                        #     isMxEmp and
                        #     (startOfPrevWeek + timedelta(days=i)).weekday() in [5, 6] and  # 5=Sat, 6=Sun
                        #     (
                        #         now.weekday() > 0 or  # After Monday
                        #         (now.weekday() == 0 and now.hour >= 12)  # Monday after 12pm
                        #     )
                        # )
                    )
                }
                for i in range((endOfPrevWeek - startOfPrevWeek).days + 1)
            ]

            locked_days = {day['date']: day['is_locked'] for day in dateRangePrevWeek}

            # Fetch timecard data for each date
            timecard_data = {}
            for day in dateRangePrevWeek:
                print(day["date"])
                # Fetch timecard data for the specific date
                timeEntryAbas = dbc.execute("""
                            select EmpID, WorkDate, t.WSNumber, WSDescription, OpName, OpNameExtended, sum(TimeWorked) as tHoursWorked, WODescription, OpCode, WOPart
                            from TimeEntryAbas t
                            inner join WorkSlips ws on t.WSNumber = ws.WSNumber 
                            inner join Operations o on ws.OpID = o.OpID
                            inner join WorkOrders wo on ws.WONumber = wo.WONumber
                            where EmpID = ? and WorkDate = ? 
                            group by EmpID, t.WSNumber, WSDescription, OpName, OpNameExtended, WorkDate, WODescription, OpCode, WOPart
                            order by EmpID, WorkDate
                            """
                            , abasUser.EmpID, day["date"]).fetchall()
                
                timeEntry = dbc.execute("""
                            select EntryID, EmpID, WorkDate, t.WSNumber, WSDescription, OpName, OpNameExtended, TimeWorked as tHoursWorked, WODescription, OpCode, WOPart 
                            from TimeEntry t
                            inner join WorkSlips ws on t.WSNumber = ws.WSNumber 
                            inner join Operations o on ws.OpID = o.OpID
                            inner join workorders wo on ws.WONumber = wo.WONumber
                            where EmpID = ? and WorkDate = ? 
                            order by EmpID, WorkDate
                            """
                            , abasUser.EmpID, day["date"]).fetchall()
                
                # Combine timeEntryAbas and timeEntry results
                combined_entries = []

                # Create a set of keys from timeEntryAbas for quick lookup
                abas_keys = {(entry.EmpID, entry.WorkDate, entry.WSNumber) for entry in timeEntryAbas}

                # Add all entries from timeEntryAbas to the combined list
                for entry in timeEntryAbas:
                    wo_desc = entry.WODescription
                    if wo_desc and wo_desc.strip() != '':
                        wo_desc_clean = wo_desc.strip()
                    else:
                        wo_desc_clean = entry.WOPart
                    combined_entries.append({
                        "EmpID": entry.EmpID,
                        "WorkDate": entry.WorkDate,
                        "WSNumber": entry.WSNumber,
                        "WSDescription": entry.WSDescription,
                        "WODescription": entry.WODescription,                        
                        "WODescriptionClean": wo_desc_clean,
                        "WOPart": entry.WOPart,
                        "OpName": entry.OpName,
                        "OpNameExtended": entry.OpNameExtended,
                        "OpCode": entry.OpCode,
                        "tHoursWorked": entry.tHoursWorked,
                        "TimeEntryID": None  # No TimeEntryID for TimeEntryAbas
                    })

                # Add entries from timeEntry only if they don't exist in timeEntryAbas
                for entry in timeEntry:
                    key = (entry.EmpID, entry.WorkDate, entry.WSNumber)
                    wo_desc = entry.WODescription
                    if wo_desc and wo_desc.strip() != '':
                        wo_desc_clean = wo_desc.strip()
                    else:
                        wo_desc_clean = entry.WOPart
                    if key not in abas_keys:
                        combined_entries.append({
                            "EmpID": entry.EmpID,
                            "WorkDate": entry.WorkDate,
                            "WSNumber": entry.WSNumber,
                            "WSDescription": entry.WSDescription,
                            "WODescription": entry.WODescription,
                            "WODescriptionClean": wo_desc_clean,
                            "WOPart": entry.WOPart,
                            "OpName": entry.OpName,
                            "OpCode": entry.OpCode,
                            "OpNameExtended": entry.OpNameExtended,
                            "tHoursWorked": entry.tHoursWorked,
                            "TimeEntryID": entry.EntryID  # Include TimeEntryID for deletion
                        })

                # Sort the combined entries by EmpID, WorkDate, and WODescription
                combined_entries.sort(key=lambda x: (x["EmpID"], x["WorkDate"], x["WODescription"]))

                timecard_data[day["date"]] = combined_entries

                # print(f"Date: {date}, Rows: {rows}")

            # Calculate weekly totals for each operation
            weekly_totals = get_weekly_operation_totals(timecard_data)

            # Check if any time entry has an OpCode specified
            has_opcode = False
            for entries in timecard_data.values():
                for entry in entries:
                    if entry.get("OpCode"):
                        has_opcode = True
                        break
                if has_opcode:
                    break

            can_use_summary_view = not has_opcode

            # Make sure startDate is a string in 'YYYY-MM-DD' format for DB queries
            #startDateStr = startDate.strftime("%Y-%m-%d")

            comments = get_comments(abasUser.EmpID, startOfPrevWeek)

            today = datetime.now().strftime("%m/%d/%y")  # Format today's date as MM/DD/YY
            
            # Fetch Paychex codes
            paychex_codes = dbc.execute(
                "SELECT PayID, PayChex, PayDescription FROM paychex ORDER BY PayChex"
            ).fetchall()

            # Convert Paychex codes to a list of dictionaries
            paychex_list = [
                {"id": row.PayID, "code": row.PayChex, "description": row.PayDescription}
                for row in paychex_codes
            ]

            # Check if the week has been finalized
            week_finalized = dbc.execute(
                """
                SELECT 1
                FROM ExportStatus
                WHERE exportEmpID = ? AND exportWorkWeek = ?
                """,
                (abasUser.EmpID, startOfPrevWeek)
            ).fetchone() is not None

            # Pass the data to the template
            return render_template('timesheet/entry.html',
                                    abasID=abas_ID,
                                    abasUser=abasUser,
                                    startOfPrevWeek=startOfPrevWeek, 
                                    endOfPrevWeek=endOfPrevWeek,
                                    dateRangePrevWeek=dateRangePrevWeek,
                                    timecard_data=timecard_data,
                                    today=today,
                                    can_add_or_finalize=can_add_or_finalize,
                                    paychex_list=paychex_list,
                                    week_finalized=week_finalized,
                                    can_use_summary_view=can_use_summary_view,
                                    comments=comments,
                                    locked_days=locked_days,
                                    weekly_totals=weekly_totals,
                                    weekday_start=weekday_start
            )

            # return render_template('timesheet/entry.html', abasID=abas_ID, abasUser=abasUser, startOfPrevWeek=startOfPrevWeek, endOfPrevWeek=endOfPrevWeek, dateRangePrevWeek=dateRangePrevWeek)
        else:
            flash(error)
            
    return render_template('timesheet/entry.html')

#get timesheet data for selected user and return to ajax query
# @bp.route("/timesheet/card", methods=['POST'])
# @login_required
# def getCard():
#     print("getCard")

#     if request.method == 'POST':
#         print("POST")
#         abas_ID = request.form.get['abas_ID']
#         print("selected ID: " + abas_ID)

#         tsDate = request.form.get['tsDate']
#         print("selected date: " + tsDate)

#         db = get_db()
#         dbc = db.cursor()

#     timecard_data = dbc.execute("""
#                                     select EmpID, WorkDate, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, sum(TimeWorked) as tHoursWorked 
#                                     from TimeEntryAbas 
#                                     inner join WorkSlips on TimeEntryAbas.WSNumber = WorkSlips.WSNumber 
#                                     inner join Operations on WorkSlips.OpID = Operations.OpID
#                                     where EmpID = ? and WorkDate = ? 
#                                     group by EmpID, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, WorkDate 
#                                     order by EmpID, WorkDate
#                                     """
#                                     , abas_ID, tsDate.strftime("%m/%d/%Y"))

#     if timecard_data:
#         # Render the _card.html template with the fetched data
#         return render_template('timesheet/_card.html', timeData=timecard_data)
#     else:
#         # Return an empty response with a 204 status code
#         return render_template('timesheet/_card.html', timeData=None)

@bp.route("/timesheet/lookup")
def lookup():
    db = get_db()
    dbc = db.cursor()

    projects = dbc.execute("select * from projects where projectcomplete = 0 and projectclosed = 0 order by projectnumber")

    return render_template('timesheet/lookup.html', projects=projects)

# get wo data for selected project and return to ajax query 
@bp.route("/timesheet/wo", methods=['POST'])
def getWO():
    print("getWO")

    selected_project = ""
    if request.method == 'POST':
        print("POST")
        selected_project = request.form.get('project_list')
        print("select project: " + selected_project)
    
    db = get_db()
    dbc = db.cursor()
    
    workorders = dbc.execute("select * from workorders where projectid = ? order by wonumber", selected_project)
    # print(workorders)
    return render_template('timesheet/_wo.html', workorders=workorders)

# get ws data for selected workorder and return to ajax query
@bp.route("/timesheet/ws", methods=['POST'])
def getWS():
    print("getWS")
    
    if request.method == 'POST':
        print("POST")
        selected_wo = request.form.get('wo_list')
        print("select wo: " + selected_wo)
    
    db = get_db()
    dbc = db.cursor()
    
    project_wo = dbc.execute("select * from workorders inner join projects on workorders.projectid = projects.projectid where wonumber = ?", selected_wo).fetchone()
    if project_wo:
        project = project_wo.ProjectNumber
        projectDesc = project_wo.ProjectDescription
        wo = project_wo.WONumber
        woDesc = project_wo.WODescription
        print(projectDesc)

    workslips = dbc.execute("select WSNumber, WONumber, WSDescription, Operations.OpID, OpCode, OpName, OpNameExtended from workslips inner join operations on WorkSlips.OpID = operations.OpID where wonumber = ? and operations.isEnabled = 1 order by WSDescription", selected_wo)
    # print(workslips)
    return render_template('timesheet/_ws.html', workslips=workslips, project=project, projectDesc=projectDesc, wo=wo, woDesc=woDesc)

# get project data return to ajax query
@bp.route('/timesheet/entry/getProjects', methods=['GET'])
def getProjects():
        
    db = get_db()
    dbc = db.cursor()

    projects = dbc.execute("select ProjectID, ProjectNumber, ProjectDescription from projects where projectcomplete = 0 and projectclosed = 0 order by projectnumber").fetchall()
    # print(projects)
    return jsonify({'projects': [{'id': row.ProjectID, 'number': row.ProjectNumber, 'desc': row.ProjectDescription} for row in projects]})

# get wo data for selected project and return to ajax query
@bp.route("/timesheet/entry/getWorkOrders", methods=['POST'])
def getWorkOrders():
    data = request.get_json()
    project_id = data.get('projectId')

    db = get_db()
    dbc = db.cursor()

    workorders = dbc.execute("select WONumber, WODescription, WOPart from workorders where projectid = ? order by wonumber", project_id).fetchall()
    # print(workorders)
    return jsonify({'workOrders': [{'id': row.WONumber, 'desc': row.WODescription, 'part': row.WOPart } for row in workorders]})

# get ws data for selected workorder and return to ajax query
@bp.route("/timesheet/entry/getWorkSlips", methods=['POST'])
def getWorkSlips():
    data = request.get_json()
    work_order_id = data.get('workOrderId')

    db = get_db()
    dbc = db.cursor()

    workslips = dbc.execute("select WSNumber, WSDescription, Operations.OpID, OpCode, OpName, OpNameExtended, OpWageGroup from workslips inner join operations on WorkSlips.OpID = operations.OpID where wonumber = ? and Operations.isEnabled = 1 order by WSDescription", work_order_id).fetchall()
    # print(workslips)
    return jsonify({'workSlips': [{'id': row.WSNumber, 'name': row.OpName, 'nameExtended': row.OpNameExtended, 'wageGroup': row.OpWageGroup} for row in workslips]})


@bp.route('/timesheet/save_entry', methods=['POST'])
@login_required
def save_entry():
    data = request.get_json()
    selected_date = data.get('selectedDate')
    abas_id = data.get('abasID')
    work_slip_id = data.get('workSlipID')
    hours_worked = data.get('hoursWorked')

    try:
        db = get_db()
        dbc = db.cursor()

        # Check if an entry for the same day and work slip already exists
        existing_entry = get_time_entry(abas_id, selected_date, work_slip_id)

        if existing_entry:
            return jsonify({'success': False, 'error': 'An entry for this day and operation already exists.'}), 400

        new_entry = create_time_entry(abas_id, selected_date, work_slip_id, hours_worked)

        if not new_entry:
            raise ValueError("Failed to fetch the newly added time entry.")

        # If OpCode is not set, use "E1"
        op_code = new_entry.OpCode if new_entry.OpCode != '' else "E1"

        # new_entry is already a dict!
        response = send_timeentry_csv_to_abas(abas_id, selected_date, work_slip_id, hours_worked, "save_entry", op_code)

        if response.status_code == 200:
            print("CSV file sent successfully!")
            return jsonify({'success': True, 'data': new_entry}), 200
        else:
            print(f"Failed to create CSV. Status code: {response.status_code}, Response: {response.text}")
            db.rollback()
            return jsonify({'success': False, 'error': 'Failed to send data to the Abas server.'}), 500

    except Exception as e:
        db.rollback()
        print("Error:", str(e))  # Debugging: Log the error
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/timesheet/entry/get_recent_workslips/<int:abas_id>', methods=['GET'])
@login_required
def get_recent_workslips(abas_id):
    """
    Returns all workslips that the current user has added in the last month,
    ordered by most used (highest count first).
    """
    try:
        # abas_id = g.user.EmpID
        db = get_db()
        dbc = db.cursor()

        today = datetime.now().date()
        last_month = today - timedelta(days=30)

        workslips = dbc.execute("""
            SELECT ws.WSNumber, ws.WSDescription, o.OpName, o.OpNameExtended, wo.WODescription, o.OpCode, COUNT(*) as usage_count
            FROM TimeEntry t
            INNER JOIN WorkSlips ws ON t.WSNumber = ws.WSNumber
            INNER JOIN Operations o ON ws.OpID = o.OpID
            INNER JOIN WorkOrders wo ON ws.WONumber = wo.WONumber
            WHERE t.EmpID = ? AND t.WorkDate >= ?
            GROUP BY ws.WSNumber, ws.WSDescription, o.OpName, o.OpNameExtended, wo.WODescription, o.OpCode
            ORDER BY usage_count DESC
        """, abas_id, last_month).fetchall()

        result = [
            {
                "WSNumber": row.WSNumber,
                "WSDescription": row.WSDescription,
                "OpCode": row.OpCode,
                "OpName": row.OpName,
                "OpNameExtended": row.OpNameExtended,
                "WODescription": row.WODescription,
                "usage_count": row.usage_count
            }
            for row in workslips
        ]

        return jsonify({"success": True, "workslips": result}), 200
    except Exception as e:
        print("Error fetching recent workslips:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/timesheet/entry/delete/<int:time_entry_id>', methods=['POST'])
@login_required
def delete_time_entry(time_entry_id):
    db = get_db()
    dbc = db.cursor()

    try:
        # Fetch the entry being deleted
        entry = get_time_entry(entry_id=time_entry_id)
        # entry = dbc.execute(
        #     """
        #     SELECT EmpID, WorkDate, WSNumber, TimeWorked
        #     FROM TimeEntry
        #     WHERE EntryID = ?
        #     """,
        #     (time_entry_id,)
        # ).fetchone()
        if entry:
            entry_date = entry.WorkDate
            abas_id = entry.EmpID
            work_slip_id = entry.WSNumber
    
            # get all entries for the selected entry for the week to delete also
            week_start = entry_date - timedelta(days=entry_date.weekday())
            week_end = week_start + timedelta(days=6)

            # entries_to_delete = dbc.execute(
            #     """
            #     SELECT EntryID
            #     FROM TimeEntry
            #     WHERE EmpID = ? AND WorkDate BETWEEN ? AND ? AND WSNumber = ?
            #     """,
            #     (abas_id, week_start, week_end, work_slip_id)
            # ).fetchall()
            
            # Find all entries for the week with the same EmpID and WSNumber
            entries_to_delete = []
            for i in range(7):
                day = week_start + timedelta(days=i)
                entry = get_time_entry(abas_id, day, work_slip_id, full_details=True)
                if entry:
                    entries_to_delete.append(entry)

            if entries_to_delete:
                # If there are entries to delete, process them
                for entry in entries_to_delete:
                    dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (entry.TimeEntryID,))
                    if entry.tHoursWorked > 0:
                        abas_id = entry.EmpID
                        selected_date = entry.WorkDate
                        work_date = selected_date.strftime('%m/%d/%y')
                        work_slip_id = entry.WSNumber
                        hours_worked = 0 # entry.TimeWorked
                        # If OpCode is not set, use "E1"
                        op_code = entry.OpCode if entry.OpCode != '' else "E1"

                        response = send_timeentry_csv_to_abas(abas_id, work_date, work_slip_id, hours_worked, "delete_time_entry", op_code)
                        if response.status_code == 200:
                            db.commit()
                            print("CSV file sent successfully!")                            
                        else:
                            print(f"Failed to create CSV. Status code: {response.status_code}, Response: {response.text}")
                    else:
                        db.commit()
                        print("No hours worked, entry deleted without sending to Abas.")
                            
        else:            
            raise ValueError("Time entry not found.")

        return jsonify({'success': True}), 200
        # flash('Time entry deleted successfully.', 'success')
        # return render_template('timesheet/entry.html')
    
    except Exception as e:
        db.rollback()
        print("Error:", str(e))
        return jsonify({'error': str(e)}), 500


@bp.route('/timesheet/entry/copy_time_entry', methods=['POST'])
@login_required
def copy_time_entry():
    import decimal
    data = request.get_json()
    job_entry_id = data.get('job_entry_id')
    copy_to_day = data.get('copy_to_day')

    if not job_entry_id or not copy_to_day:
        return jsonify(success=False, error="Missing job_entry_id or copy_to_day"), 400

    db = get_db()
    dbc = db.cursor()

    # Fetch the original job entry (with full details)
    original_entry = get_time_entry(entry_id=job_entry_id)
    if not original_entry:
        return jsonify(success=False, error="Original job entry not found"), 404

    try:
        # original_entry: (EntryID, EmpID, WorkDate, WSNumber, TimeWorked)
        abas_id = original_entry[1]
        ws_number = original_entry[3]
        time_worked = 0 #original_entry[4] 

        # Create a new entry for the new day
        new_entry = create_time_entry(abas_id, copy_to_day, ws_number, time_worked)
        if not new_entry:
            raise Exception("Failed to create copied job entry.")

        # send_response = send_timeentry_csv_to_abas(
        #     abas_id, 
        #     copy_to_day, 
        #     ws_number, 
        #     float(time_worked) if isinstance(time_worked, decimal.Decimal) else time_worked
        # )
        # if send_response.status_code != 200:
        #     raise Exception(f"Failed to send copied job entry to Abas: {send_response.text}")

        db.commit()

        # Return the new entry's details for DOM update
        return jsonify(success=True, data={
            "TimeEntryID": new_entry["TimeEntryID"],
            "WSNumber": new_entry["WSNumber"],
            "OpNameExtended": new_entry["OpNameExtended"],
            "WODescription": new_entry["WODescription"],
            "tHoursWorked": new_entry["tHoursWorked"],
            "WorkDate": copy_to_day
        })
    except Exception as e:
        db.rollback()
        return jsonify(success=False, error=str(e)), 500

@bp.route('/timesheet/entry/add_to_timesheet', methods=['POST'])
@login_required
def add_to_timesheet():
    """
    Add the selected operation (WSNumber) to every day of the week for the current user,
    with TimeWorked = 0. Does NOT submit to the API.
    Expects JSON: { "ws_number": "...", "week_start": "MM/DD/YY" }
    Returns: { success: True, entries: [ ... ] }
    """
    try:
        data = request.get_json()
        abas_id = data.get('abasID')
        ws_number = data.get('workSlipID')
        week_start_str = data.get('week_start')

        # Parse week_start to date
        try:
            week_start = datetime.strptime(week_start_str, "%m/%d/%y").date()
        except ValueError:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()

        new_entries = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            existing_entry = get_time_entry(abas_id, day_date, ws_number)
            if not existing_entry:
                entry = create_time_entry(abas_id, day_date, ws_number, 0)
                if entry:
                    new_entries.append(entry)

        return jsonify({'success': True, 'entries': new_entries})
    except Exception as e:
        print("Error in add_to_timesheet:", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/timesheet/finalize_time', methods=['POST'])
@login_required
def finalize_time():
    data = request.form
    db = get_db()
    dbc = db.cursor()

    try:
        for key, value in data.items():
            if key.startswith("paychex_code_"):
                time_entry_id = key.split("_")[2]
                paychex_code = value

                # Update the Paychex code for the time entry
                dbc.execute(
                    """
                    UPDATE TimeEntry
                    SET PaychexCode = ?
                    WHERE EntryID = ?
                    """,
                    (paychex_code, time_entry_id)
                )

        db.commit()
        flash("Time entries finalized successfully.", "success")
        return redirect(url_for('timesheet.entry'))
    except Exception as e:
        db.rollback()
        flash(f"An error occurred while finalizing time: {str(e)}", "error")
        return redirect(url_for('timesheet.entry'))

# get existing time entries for selected user and return to ajax query for finalize time modal   
@bp.route('/timesheet/entry/get_final_time_entries', methods=['GET'])
@login_required
def get_final_time_entries():
    try:
        # Get the start and end dates for the current week
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        abas_id = request.args.get('abas_id')
        
        totalHoursWorked = 0.0
        
        # # Convert the date strings to datetime objects
        # start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        # end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # # Convert the dates to the format required by the SQL query
        # start_date_str = start_date.strftime('%m/%d/%y')
        # end_date_str = end_date.strftime('%m/%d/%y')

        print("abas_id: " + abas_id)
        print("start_date: " + start_date)
        print("end_date: " + end_date)

        db = get_db()
        dbc = db.cursor()

        # Fetch time entries for the given date range of a salaried employee        
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

        # Convert the results to a list of dictionaries
        if time_entries:
            time_entries_list = []
            for entry in time_entries:
                # Strip whitespace from WorkDate and convert to a datetime object
                # work_date = entry.WorkDate.strip() if isinstance(entry.WorkDate, str) else entry.WorkDate
                # if isinstance(work_date, str):
                #     try:
                #         work_date = datetime.strptime(work_date, '%m/%d/%y')  # Handle MM/DD/YY format
                #     except ValueError:
                #         work_date = datetime.strptime(work_date, '%m/%d/%Y')  # Handle MM/DD/YYYY format

                time_entries_list.append({
                    "WorkDate": entry.WorkDate.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY,                    
                    "tHoursWorked": entry.sTimeWorked
                })
                totalHoursWorked += float(entry.sTimeWorked) if isinstance(entry.sTimeWorked, decimal.Decimal) else entry.sTimeWorked
                
            print("Time Entries:", time_entries_list)  # Debugging: Log the data
            return jsonify({"success": True, "time_entries": time_entries_list, "totalHoursWorked": totalHoursWorked}), 200
        else:
            print("No time entries found for the given date range.")
            return jsonify({"success": True, "time_entries": None, "totalHoursWorked": 0}), 200
    except Exception as e:
        print("Error fetching time entries:", str(e))  # Debugging: Log the error
        return jsonify({"success": False, "error": str(e)}), 500    

@bp.route('/timesheet/entry/get_payroll_export', methods=['GET'])
@login_required
def get_payroll_export():
    try:

        abas_id = request.args.get('abas_id')
        workweek = request.args.get('workweek')

        db = get_db()
        dbc = db.cursor()
        # get last payroll export from PayrollExport table.
        last_export = dbc.execute(
            """
            SELECT exportDate, WorkWeek, HoursWorked, DateWorked, PayID, EmpID, PayChex
            FROM PayrollExport p
            INNER JOIN PayChex c on p.PayChexID = c.PayID
            WHERE EmpID = ? AND WorkWeek = ?
            ORDER BY exportDate DESC
            """,
            (abas_id, workweek)
        ).fetchall()

        # return a JSON of all of the entries for each day worked for the workweek as a list of dicts
        # return JSON
        if last_export:
            export_list = []
            for entry in last_export:
                export_list.append({
                    "exportDate": entry.exportDate.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY
                    "WorkWeek": entry.WorkWeek.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY
                    "HoursWorked": entry.HoursWorked,
                    "DateWorked": entry.DateWorked.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY
                    "PayChexID": entry.PayID,
                    "EmpID": entry.EmpID,
                    "PayChex": entry.PayChex
                })
            return jsonify({"success": True, "payrollExport": export_list})
        
        else:
            return jsonify({"success": True, "payrollExport": None}), 200
    except Exception as e:
        print("Error fetching payroll entries:", str(e))  # Debugging: Log the error
        return jsonify({"success": False, "error": str(e)}), 500    

def save_payroll_export(abas_id, workweek, hours_worked, date_worked, paychex_id):
    db = get_db()
    dbc = db.cursor()
    try:
        export_date = datetime.now()  # Current date and time

        # delete any existing records for the workdate and workweek
        dbc.execute(
            """
            DELETE FROM PayrollExport
            WHERE EmpID = ? AND WorkWeek = ? AND DateWorked = ?
            """,
            (abas_id, workweek, date_worked)
        )

        dbc.execute(
            """
            INSERT INTO PayrollExport (EmpID, WorkWeek, HoursWorked, DateWorked, PayChexID, exportDate)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (abas_id, workweek, hours_worked, date_worked, paychex_id, export_date)
        )

        db.commit()
        print("PayrollExport entry added successfully.")
        return True
    except Exception as e:
        db.rollback()
        print("Error saving PayrollExport:", str(e))
        return False


@bp.route('/timesheet/payroll_export', methods=['POST'])
def payroll_export():
    try:
        # Define the external API URL
        external_api_url = "http://abas.kasa.kasacontrols.com:8000/payroll_import"

        # Get the JSON payload from the client
        data = request.get_json()
        print("Received JSON data:", data)  # Debugging: Log the received data
        
        # Define a mapping of Paychex codes to their values
        paychex_code_mapping = get_paychex_codes()
        print("Paychex Code Mapping:", paychex_code_mapping)  # Debugging: Log the mapping

        # Group and prepare time entries
        grouped = {}
        for entry in data.get("time_entries", []):
            # Convert date to m/d/yyyy
            date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
            date_str = date_obj.strftime("%m/%d/%Y")  # e.g., 5/19/2025

            paychex_code = paychex_code_mapping.get(int(entry["paychexCode"]), entry["paychexCode"])
            hours = float(entry["hours"])
            comments = entry.get("comments") or "null"
            key = (date_str, paychex_code)
            if key not in grouped:
                grouped[key] = {"hours": 0.0, "comments": comments}
            grouped[key]["hours"] += hours
            # If any comment is not "null", keep it
            if comments != "null":
                grouped[key]["comments"] = comments

        # Build the combined time_entries list
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

        print("Converted JSON data:", converted_data)  # Debugging: Log the converted data

        # Forward the converted JSON data to the external API
        response = requests.post(external_api_url, json=converted_data)
        print("Response from external API:", response.status_code, response.text)  # Debugging: Log the response

        # add log to ExportLog table and ExportLogDetail tables
        abas_id = data.get("abas_id")
        export_source = "payroll_export"
        export_date = datetime.now()  # Current date and time
        export_work_week = datetime.strptime(data.get("start_date"), "%Y-%m-%d").date()  # Assuming start_date is passed in the payload
        export_status = "Success" if response.status_code == 200 else "Failed"
        export_status_detail = response.text if response.status_code != 200 else None
        export_type = "Payroll"
        # Function to add an export log summary
        export_id = add_exportlog_summary(abas_id, export_date, export_work_week, export_status, export_status_detail, export_type, export_source)
        # Function to add export log details
        for entry in combined_time_entries:
            add_exportlog_entry(
                export_id=export_id,
                emp_id=abas_id,
                work_date=entry["date"],
                time_worked=float(entry["hours"]) if entry["hours"] is not None else None,
                paychex_code=entry["paychexCode"],
                work_slip=None,
                comments=entry["comments"]
            )
            save_payroll_export(abas_id=abas_id,
                                workweek=export_work_week,
                                hours_worked=float(entry["hours"]) if entry["hours"] is not None else None,
                                date_worked=datetime.strptime(entry["date"], "%m/%d/%Y").date(),
                                paychex_id=lookup_paychex_id(entry["paychexCode"])
            )

        if response.status_code == 200:
            # If the API call is successful, write an entry to the ExportStatus table
            db = get_db()
            dbc = db.cursor()

            # Insert a new record into the ExportStatus table
            export_date = datetime.now()  # Current date and time
            export_work_week = datetime.strptime(data.get("start_date"), "%Y-%m-%d").date()  # Assuming start_date is passed in the payload

            dbc.execute(
                """
                INSERT INTO ExportStatus (exportEmpID, exportDate, exportWorkWeek)
                VALUES (?, ?, ?)
                """,
                (data.get("abas_id"), export_date, export_work_week)
            )

            db.commit()
            print("ExportStatus entry added successfully.")

        # Return the response from the external API to the client
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print("Error during payroll export:", str(e))  # Debugging: Log the error
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/timesheet/entry/copy_prev_week', methods=['POST'])
@login_required
def copy_prev_week():
    try:
        data = request.get_json()
        abas_id = data.get('abas_id')
        curr_start = data.get('curr_start')
        
        curr_start = datetime.strptime(curr_start, "%Y-%m-%d").date()
        curr_month = datetime.now().month  # The month of the current week

        # Calculate the start and end of the week
        prev_start = curr_start - timedelta(days=7)
        prev_end = prev_start + timedelta(days=6)

        # 1. Fetch previous week's entries
        prev_entries = get_time_entries_for_day(abas_id, prev_start)
        
        if not prev_entries:
            # Calculate the start and end of the week for 2 weeks ago
            prev_start = curr_start - timedelta(days=14)
            prev_end = prev_start + timedelta(days=6)
            prev_entries = get_time_entries_for_day(abas_id, prev_start)
        
        if prev_entries:
            # delete existing entries for the current week, but only for days in the current month
            curr_week_entries = get_time_entries_for_week(abas_id, curr_start, curr_start + timedelta(days=6))
            
            # Delete entries for the current week
            for entry in curr_week_entries:
                entry_date = entry.WorkDate if isinstance(entry.WorkDate, date) else datetime.strptime(entry.WorkDate, "%Y-%m-%d").date()
                if entry_date.month >= curr_month: 
                    dbc = get_db().cursor()
                    dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (entry.EntryID,))
                    dbc.commit()
                    # Send negated entry to Abas
                    if entry.TimeWorked > 0:
                        response = send_timeentry_csv_to_abas(
                            abas_id, 
                            entry.WorkDate, 
                            entry.WSNumber, 
                            0.0,  # Negate the hours
                            "copy_prev_week"
                        )
                        if response.status_code != 200:
                            raise ValueError(f"Failed to send negated data for {entry.WorkDate}.")

            # create new copied entries
            for entry in prev_entries:
                for i in range(7):
                    day_date = curr_start + timedelta(days=i)
                    if day_date.month < curr_month:
                        continue  # Skip copying to locked days (previous month)
                    existing_entry = get_time_entry(abas_id, day_date, entry.WSNumber)
                    if not existing_entry:
                        entry_obj = create_time_entry(abas_id, day_date, entry.WSNumber, 0)
                    print("new_entry: ", entry_obj)                  
                      
            flash("Previous week's entries copied successfully.", "success")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'No entries found for the previous week.'})
    except Exception as e:
        print("Error copying previous week:", str(e))
        return jsonify({'success': False, 'error': str(e)})
# def copy_prev_week():
#     try:
#         data = request.get_json()
#         abas_id = data.get('abas_id')
#         curr_start = data.get('curr_start')
        
#         curr_start = datetime.strptime(curr_start, "%Y-%m-%d").date()
#         curr_month = datetime.now().month  # The month of the current week

#         # Calculate the start and end of the week
#         prev_start = curr_start - timedelta(days=7)
#         prev_end = prev_start + timedelta(days=6)

#         # 1. Fetch previous week's entries
#         prev_entries = get_time_entries_for_week(abas_id, prev_start, prev_end)
        
#         if not prev_entries:
#             # Calculate the start and end of the week for 2 weeks ago
#             prev_start = curr_start - timedelta(days=14)
#             prev_end = prev_start + timedelta(days=6)
#             prev_entries = get_time_entries_for_week(abas_id, prev_start, prev_end)
        
#         if prev_entries:
#             # delete existing entries for the current week, but only for days in the current month
#             curr_week_entries = get_time_entries_for_week(abas_id, curr_start, curr_start + timedelta(days=6))
#             for entry in curr_week_entries:
#                 entry_date = entry.WorkDate if isinstance(entry.WorkDate, date) else datetime.strptime(entry.WorkDate, "%Y-%m-%d").date()
#                 if entry_date.month == curr_month:
#                     dbc = get_db().cursor()
#                     dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (entry.EntryID,))
#                     dbc.connection.commit()
#                     # Send negated entry to Abas
#                     response = send_timeentry_csv_to_abas(
#                         abas_id, 
#                         entry.WorkDate, 
#                         entry.WSNumber, 
#                         0.0,  # Negate the hours
#                         "copy_prev_week"
#                     )
#                     if response.status_code != 200:
#                         raise ValueError(f"Failed to send negated data for {entry.WorkDate}.")

#             # 2. Copy entries to current week (adjust dates), but only for days in the current month
#             for entry in prev_entries:
#                 prev_date = entry.WorkDate if isinstance(entry.WorkDate, date) else datetime.strptime(entry.WorkDate, "%Y-%m-%d").date()
#                 days_offset = (prev_date - prev_start).days
#                 new_date = curr_start + timedelta(days=days_offset)
#                 if new_date.month != curr_month:
#                     continue  # Skip copying to locked days (previous month)
#                 eTimeWorked = 0 #entry.TimeWorked
#                 new_entry = create_time_entry(abas_id, new_date, entry.WSNumber, eTimeWorked)
#                 print("new_entry: ", new_entry)
#             flash("Previous week's entries copied successfully.", "success")
#             return jsonify({'success': True})
#         else:
#             return jsonify({'success': False, 'error': 'No entries found for the previous week.'})
#     except Exception as e:
#         print("Error copying previous week:", str(e))
#         return jsonify({'success': False, 'error': str(e)})
# def copy_prev_week():
#     try:
#         data = request.get_json()
#         abas_id = data.get('abas_id')
#         curr_start = data.get('curr_start')
        
#         curr_start = datetime.strptime(curr_start, "%Y-%m-%d").date()
        
#         # Calculate the start and end of the week
#         prev_start = curr_start - timedelta(days=7)
#         print("prev_start: ", prev_start)
#         prev_end = prev_start + timedelta(days=6)
#         print("prev_end: ", prev_end)

#         # 1. Fetch previous week's entries
#         print("get_time_entries_for_week")
#         prev_entries = get_time_entries_for_week(abas_id, prev_start, prev_end)  # Implement this helper
#         print("prev_entries: ", prev_entries)
        
#         if not prev_entries:
#             # Calculate the start and end of the week for 2 weeks ago
#             prev_start = curr_start - timedelta(days=14)
#             print("prev_start: ", prev_start)
#             prev_end = prev_start + timedelta(days=6)
#             print("prev_end: ", prev_end)

#             # 1. Fetch previous week's entries
#             print("get_time_entries_for_week")
#             prev_entries = get_time_entries_for_week(abas_id, prev_start, prev_end)  # Implement this helper
#             print("prev_entries: ", prev_entries)
        
#         if prev_entries:
#             # delete existing entries for the current week
#             curr_week_entries = get_time_entries_for_week(abas_id, curr_start, curr_start + timedelta(days=6))
#             if curr_week_entries:
#                 # delete each existing entry for the current week and send a negated entry to Abas
#                 for entry in curr_week_entries:
#                     print("Deleting existing entry: ", entry)
#                     dbc = get_db().cursor()
#                     dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (entry.EntryID,))
#                     dbc.connection.commit()
                    
#                     # Send negated entry to Abas
#                     response = send_timeentry_csv_to_abas(
#                         abas_id, 
#                         entry.WorkDate, 
#                         entry.WSNumber, 
#                         0.0  # Negate the hours
#                     )
                    
#                     if response.status_code != 200:
#                         raise ValueError(f"Failed to send negated data for {entry.WorkDate}.")
            
#             # 2. Copy entries to current week (adjust dates)
#             for entry in prev_entries:
#                 # Calculate new date for current week
#                 prev_date = entry.WorkDate
#                 days_offset = (prev_date - prev_start).days
#                 new_date = curr_start + timedelta(days=days_offset)
#                 print("new_date: ", new_date)
#                 # Create new entry (implement create_time_entry as needed)
#                 eTimeWorked = 0 #entry.TimeWorked
#                 new_entry = create_time_entry(abas_id, new_date, entry.WSNumber, eTimeWorked)
#                 print("new_entry: ", new_entry)
                
#                 # if new_entry:
#                 #     # After creating new_entry or when building any JSON response:
#                 #     time_worked = float(eTimeWorked) if isinstance(eTimeWorked, decimal.Decimal) else eTimeWorked
#                 #     response = send_timeentry_csv_to_abas(abas_id, new_date, entry.WSNumber, time_worked)
#                 #     if response.status_code != 200:
#                 #         raise ValueError(f"Failed to send data for {new_date}.")

#             flash("Previous week's entries copied successfully.", "success")
#             return jsonify({'success': True})
#         else:
#             return jsonify({'success': False, 'error': 'No entries found for the previous week.'})
#     except Exception as e:
#         print("Error copying previous week:", str(e))  # Debugging: Log the error
#         return jsonify({'success': False, 'error': str(e)})

@bp.route('/timesheet/entry/copy_day', methods=['POST'])
@login_required
def copy_day():
    try:
        data = request.get_json()
        abas_id = g.user.EmpID  # Use the logged-in user's ID
        copy_from_day = data.get('copy_from_day')  # Format: MM/DD/YY or MM/DD/YYYY
        copy_to_day = data.get('copy_to_day')      # Format: MM/DD/YY or MM/DD/YYYY

        # Parse dates to datetime.date objects
        try:
            if '-' in copy_from_day:
                from_date = datetime.strptime(copy_from_day, "%m-%d-%Y").date()
            else:
                try:
                    from_date = datetime.strptime(copy_from_day, "%m/%d/%Y").date()
                except ValueError:
                    from_date = datetime.strptime(copy_from_day, "%m/%d/%y").date()
            if '-' in copy_to_day:
                to_date = datetime.strptime(copy_to_day, "%m-%d-%Y").date()
            else:
                try:
                    to_date = datetime.strptime(copy_to_day, "%m/%d/%Y").date()
                except ValueError:
                    to_date = datetime.strptime(copy_to_day, "%m/%d/%y").date()
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid date format: {e}'}), 400

        db = get_db()
        dbc = db.cursor()

        # Fetch all entries for the source day
        from_entries = dbc.execute(
            "SELECT WSNumber, TimeWorked FROM TimeEntry WHERE EmpID = ? AND WorkDate = ?",
            (abas_id, from_date)
        ).fetchall()

        if not from_entries:
            return jsonify({'success': False, 'error': 'No entries found for the source day.'}), 404

        # Optionally: Delete all entries for the target day before copying
        dbc.execute(
            "DELETE FROM TimeEntry WHERE EmpID = ? AND WorkDate = ?",
            (abas_id, to_date)
        )

        # Copy each entry to the target day
        for entry in from_entries:
            ws_number = entry.WSNumber
            time_worked = 0
            # Insert new entry
            dbc.execute(
                "INSERT INTO TimeEntry (EmpID, WorkDate, WSNumber, TimeWorked) VALUES (?, ?, ?, ?)",
                (abas_id, to_date, ws_number, time_worked)
            )
            # Optionally, send to Abas API
            # send_timeentry_csv_to_abas(abas_id, to_date, ws_number, time_worked)

        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        print("Error copying day:", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


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
        print("time_entry: ", time_entry)
        abas_id = time_entry.EmpID
        entry_date = time_entry.WorkDate
        work_slip_id = time_entry.WSNumber
        time_worked = float(time_entry.tHoursWorked)
        # If OpCode is not set, use "E1"
        op_code = time_entry.OpCode if time_entry.OpCode != '' else "E1"
            
        response = send_timeentry_csv_to_abas(abas_id, entry_date, work_slip_id, time_worked, "update_hours", op_code)
        if response.status_code != 200:
            raise ValueError(f"Failed to send data for {time_entry.WorkDate}.")
                
        return jsonify({'success': True, 'hoursWorked': f"{float(hours_worked):.2f}"})
    except Exception as e:
        db.rollback()
        print("Error updating hours:", str(e))  # Debugging: Log the error
        return jsonify({'success': False, 'error': str(e)})
    
    
@bp.route('/timesheet/entry/delete_day/<path:date_str>', methods=['POST'])
@login_required
def delete_day_entries(date_str):
    """
    Delete all time entries for a given day for the current user,
    and send negated entries to the API server.
    Expects date_str in MM/DD/YY or MM-DD-YYYY format.
    """
    try:
        # Parse date
        try:
            if '-' in date_str and len(date_str.split('-')[2]) == 4:
                work_date = datetime.strptime(date_str, "%m-%d-%Y").date()
            else:
                work_date = datetime.strptime(date_str, "%m/%d/%y").date()
        except Exception:
            work_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        abas_id = g.user.EmpID
        db = get_db()
        dbc = db.cursor()

        # Fetch all entries for this user and date
        entries = dbc.execute(
            "SELECT EntryID, WSNumber, TimeWorked FROM TimeEntry WHERE EmpID = ? AND WorkDate = ?",
            (abas_id, work_date)
        ).fetchall()

        # Send negated entry to API for each entry
        for entry in entries:
            ws_number = entry.WSNumber
            # Send negated entry (hours = 0)
            response = send_timeentry_csv_to_abas(abas_id, work_date, ws_number, 0.0, "delete_day_entries")
            if response.status_code != 200:
                raise ValueError(f"Failed to send negated data for {work_date} WS {ws_number}.")

        # Delete all entries for this user and date
        dbc.execute("DELETE FROM TimeEntry WHERE EmpID = ? AND WorkDate = ?", (abas_id, work_date))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        print("Error deleting day entries:", str(e))
        return jsonify({'success': False, 'error': str(e)})
    

def get_time_entries_for_week(abas_id, start_date, end_date):
    db = get_db()
    dbc = db.cursor()

    # Fetch time entries for the given date range
    time_entries = dbc.execute(
        """
        SELECT EntryID, WorkDate, WSNumber, TimeWorked
        FROM TimeEntry 
        WHERE EmpID = ? AND WorkDate BETWEEN ? AND ?
        ORDER BY WorkDate
        """,
        (abas_id, start_date, end_date)
    ).fetchall()
    
    # get time entries from TimeEntryAbas if no entries found in TimeEntry
    # This is a fallback to ensure we get some data
    if not time_entries:
        time_entries = dbc.execute(
            """
            SELECT AbasEntryID as EntryID, WorkDate, WSNumber, TimeWorked
            FROM TimeEntryAbas 
            WHERE EmpID = ? AND WorkDate BETWEEN ? AND ?
            ORDER BY WorkDate
            """,
            (abas_id, start_date, end_date)
        ).fetchall()       
        
    return time_entries

def get_time_entries_for_day(abas_id, work_date):
    db = get_db()
    dbc = db.cursor()

    # Fetch time entries for the given date
    time_entries = dbc.execute(
        """
        SELECT EntryID, WorkDate, WSNumber, TimeWorked
        FROM TimeEntry 
        WHERE EmpID = ? AND WorkDate = ?
        ORDER BY WorkDate
        """,
        (abas_id, work_date)
    ).fetchall()
    
    # get time entries from TimeEntryAbas if no entries found in TimeEntry
    # This is a fallback to ensure we get some data
    if not time_entries:
        time_entries = dbc.execute(
            """
            SELECT AbasEntryID as EntryID, WorkDate, WSNumber, TimeWorked
            FROM TimeEntryAbas 
            WHERE EmpID = ? AND WorkDate = ?
            ORDER BY WorkDate
            """,
            (abas_id, work_date)
        ).fetchall()

    return time_entries

def get_paychex_codes():
    db = get_db()
    dbc = db.cursor()

    paychex_codes = dbc.execute(
        "SELECT PayID, PayChex FROM paychex WHERE inUse = 1 ORDER BY PayChex"
    ).fetchall()

    # Convert PayID to PayChex code mapping
    paychex_mapping = {row.PayID: row.PayChex for row in paychex_codes}

    return paychex_mapping    

def lookup_paychex_id(paychex_code):
    db = get_db()
    dbc = db.cursor()

    paychex_code = dbc.execute(
        "SELECT PayID, PayChex, PayDescription FROM paychex WHERE PayChex = ? ORDER BY PayChex", paychex_code
    ).fetchone()

    paycode_id = paychex_code.PayID if paychex_code else None

    return paycode_id

def create_time_entry(abas_id, work_date, ws_number, time_worked=None):
    try:
        db = get_db()
        dbc = db.cursor()

        # Insert the new time entry and fetch the inserted ID
        new_entry_id = dbc.execute(
            """
            INSERT INTO TimeEntry (EmpID, WorkDate, WSNumber, TimeWorked)
            OUTPUT INSERTED.EntryID
            VALUES (?, ?, ?, ?)
            """,
            (abas_id, work_date, ws_number, time_worked)
        ).fetchone()[0]

        db.commit()

        # Fetch the newly added entry for the response
        new_entry = dbc.execute(
            """
            SELECT t.EntryID AS TimeEntryID, t.WSNumber, t.WorkDate AS WorkDate, ws.WSDescription, o.OpName, o.OpNameExtended, t.TimeWorked AS tHoursWorked, WODescription, OpCode
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

        # Build a dictionary directly using column names
        columns = [column[0] for column in dbc.description]
        entry_dict = dict(zip(columns, new_entry))
        # After building entry_dict in create_time_entry
        if "WorkDate" in entry_dict and isinstance(entry_dict["WorkDate"], (datetime, date)):
            entry_dict["WorkDate"] = entry_dict["WorkDate"].strftime("%m/%d/%y")
            
        # Convert Decimal to float if needed
        for k, v in entry_dict.items():
            if isinstance(v, decimal.Decimal):
                entry_dict[k] = f"{float(v):.2f}"
                
        return entry_dict

    except Exception as e:
        db.rollback()
        print("Error creating time entry:", str(e))
        return None

def get_time_entry(abas_id=None, work_date=None, ws_number=None, entry_id=None, full_details=False):
    db = get_db()
    dbc = db.cursor()

    if entry_id:
        # If entry_id is provided, fetch the specific entry
        if full_details:
            # Fetch the full details of the time entry
            time_entry = dbc.execute(
                """
                SELECT t.EntryID AS TimeEntryID, t.EmpID, t.WorkDate, t.WSNumber, ws.WSDescription, o.OpName, o.OpNameExtended, t.TimeWorked AS tHoursWorked, wo.WODescription, o.OpCode
                FROM TimeEntry t
                INNER JOIN WorkSlips ws ON t.WSNumber = ws.WSNumber
                INNER JOIN Operations o ON ws.OpID = o.OpID
                INNER JOIN WorkOrders wo ON ws.WONumber = wo.WONumber
                WHERE t.EntryID = ?
                """,
                (entry_id,)
            ).fetchone()
        else:
            # Fetch the time entry for the given entry_id
            time_entry = dbc.execute(
                """
                SELECT EntryID, EmpID, WorkDate, WSNumber, TimeWorked
                FROM TimeEntry
                WHERE EntryID = ?
                """, 
                (entry_id)
            ).fetchone()
    else: 
        # Fetch the time entry for the given parameters
        if full_details:
            # Fetch the full details of the time entry
            time_entry = dbc.execute(
                """
                SELECT t.EntryID AS TimeEntryID, t.EmpID, t.WorkDate, t.WSNumber, ws.WSDescription, o.OpName, o.OpNameExtended, t.TimeWorked AS tHoursWorked, wo.WODescription, o.OpCode
                FROM TimeEntry t
                INNER JOIN WorkSlips ws ON t.WSNumber = ws.WSNumber
                INNER JOIN Operations o ON ws.OpID = o.OpID
                INNER JOIN WorkOrders wo ON ws.WONumber = wo.WONumber
                WHERE t.EmpID = ? AND t.WorkDate = ? AND t.WSNumber = ?
                """,
                (abas_id, work_date, ws_number)
            ).fetchone()
        else:
            # Fetch the time entry for the given abas_id, work_date, and ws_number
            time_entry = dbc.execute(
                """
                SELECT EntryID, EmpID, WorkDate, WSNumber, TimeWorked
                FROM TimeEntry
                WHERE EmpID = ? AND WorkDate = ? AND WSNumber = ?
                """,
                (abas_id, work_date, ws_number)
            ).fetchone()

    return time_entry

def send_timeentry_csv_to_abas(abas_id, work_date, work_slip_id, hours_worked, export_source=None, paychex_code=None):
    # Define the API endpoint
    url = "http://abas.kasa.kasacontrols.com:8000/jobtime_entry"

    # Convert work_date to string if it's a date object
    if isinstance(work_date, (datetime, date)):
        work_date_str = work_date.strftime('%m/%d/%y')
    else:
        work_date_str = str(work_date)

    # Define the payload
    payload = {
        "EmpID": abas_id,
        "WorkDate": work_date_str,  # Format the date as MM/DD/YY
        "WSNumber": work_slip_id,
        "HoursWorked": hours_worked,
        "PaychexCode": paychex_code
    }

    # Send the POST request
    response = requests.post(url, json=payload)
    try:
        # create log entry in ExportStatus table and ExportStatusDetail table
        export_date = datetime.now()
        if isinstance(work_date, str):
            try:
                # Try MM/DD/YY, MM/DD/YYYY, or YYYY-MM-DD formats
                if '-' in work_date and len(work_date.split('-')[0]) == 4:
                    work_date_obj = datetime.strptime(work_date, "%Y-%m-%d").date()
                elif '-' in work_date:
                    work_date_obj = datetime.strptime(work_date, "%m-%d-%Y").date()
                else:
                    try:
                        work_date_obj = datetime.strptime(work_date, "%m/%d/%Y").date()
                    except ValueError:
                        work_date_obj = datetime.strptime(work_date, "%m/%d/%y").date()
            except Exception:
                work_date_obj = datetime.now().date()
        else:
            work_date_obj = work_date

        export_work_week = get_week_start(work_date_obj, week_start_day=0)
        export_status = "Success" if response.status_code == 200 else "Failed"
        export_status_detail = response.text if response.status_code != 200 else None
        export_type = "JobTimeEntry"
        export_id = add_exportlog_summary(abas_id, export_date, export_work_week, export_status, export_status_detail, export_type, export_source)
        add_exportlog_entry(
            export_id=export_id,
            emp_id=abas_id,
            work_date=work_date_str,
            time_worked=hours_worked,
            paychex_code=paychex_code,
            work_slip=work_slip_id
        )
    except Exception as e:
        print("Error logging export:", str(e))
        
    return response

@bp.route('/timesheet/entry/get_summary_flag')
@login_required
def get_summary_flag():
    abas_id = request.args.get('abas_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    db = get_db()
    dbc = db.cursor()
    
    # Fetch timecard data for each date      
    timeEntry = dbc.execute("""
                select OpCode 
                from TimeEntry t
                inner join WorkSlips ws on t.WSNumber = ws.WSNumber 
                inner join Operations o on ws.OpID = o.OpID
                where EmpID = ? and WorkDate BETWEEN ? and ? and OpCode != ''
                """
                , abas_id, start_date, end_date).fetchall()
        
    
    has_opcode = False
    if timeEntry:
        has_opcode = True

    return jsonify({'can_use_summary_view': not has_opcode})

@bp.route('/timesheet/entry/save_comments', methods=['POST'])
@login_required
def save_comments():
    external_api_url = "http://abas.kasa.kasacontrols.com:8000/add_comments"
    
    data = request.get_json()
    abas_id = data.get('abas_id')
    start_date = data.get('start_date')
    comments = data.get('comments')
    # Save comments to your database here, e.g.:
    db = get_db()
    dbc = db.cursor()
    
    date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    date_str = date_obj.strftime("%m/%d/%Y")  # e.g., 5/19/2025
    
    if comments <= "": comments = "None"
    print("comments: ", comments)
          
    comment_entry = {
        "abas_id": abas_id,
        "date": date_str,
        "comments": comments
    }
    
    try:
        if get_comments(abas_id, start_date) is None:
            # Insert new comment if it doesn't exist
            dbc.execute("INSERT INTO TimesheetComments (EmpID, WeekStart, comments) VALUES (?, ?, ?)", (abas_id, start_date, comments))
        else:
            # Update existing comment    
            dbc.execute("UPDATE TimesheetComments SET comments=? WHERE EmpID=? AND WeekStart=?", (comments, abas_id, start_date))
        
        # Forward the converted JSON data to the external API
        response = requests.post(external_api_url, json=comment_entry)
        print("Response from external API:", response.status_code, response.text)  # Debugging: Log the response

        # add log to ExportLog table and ExportLogDetail tables
        export_source = "save_comments"
        export_date = datetime.now()  # Current date and time
        export_work_week = get_week_start(date_obj, week_start_day=0) # Assuming week starts on Monday
        export_status = "Success" if response.status_code == 200 else "Failed"
        export_status_detail = response.text if response.status_code != 200 else None
        export_type = "Comments"
        # Function to add an export log summary
        export_id = add_exportlog_summary(abas_id, export_date, export_work_week, export_status, export_status_detail, export_type, export_source)
        # Function to add export log details
        add_exportlog_entry(
            export_id=export_id,
            emp_id=abas_id,
            work_date=date_str,
            time_worked=None,  # No time worked for comments
            paychex_code=None,  # No Paychex code for comments
            work_slip=None,  # No work slip for comments
            comments=comments
        )

        if response.status_code == 200:        
            dbc.commit()
    
        return jsonify(success=True)
    except Exception as e:
        db.rollback()
        print("Error saving comments:", str(e))        
    
        return jsonify(success=False, error=str(e)), 500
    

def get_comments(abas_id, start_date):
    db = get_db()
    dbc = db.cursor()
    
    if isinstance(start_date, datetime):
        start_date = start_date.strftime("%Y-%m-%d")
    
    # Fetch comments for the given abas_id and start_date
    comments = dbc.execute(
        "SELECT comments FROM TimesheetComments WHERE empID = ? AND weekStart = ?",
        (abas_id, start_date)
    ).fetchone()
    
    if comments:
        return comments[0]  # Return the comment text
    else:
        return None  # No comments found
    
def get_week_start(date, week_start_day=0):
    """Return the start of the week for a given date and week_start_day (0=Mon, 5=Sat)."""
    days_to_subtract = (date.weekday() - week_start_day) % 7
    return date - timedelta(days=days_to_subtract)

def add_exportlog_summary(abas_id=None, export_date=None, export_work_week=None, export_status=None, export_status_detail=None, export_type=None, export_source=None):
    db = get_db()
    dbc = db.cursor()
    # export log table definition
    # [exportID] [int] IDENTITY(1,1) NOT NULL,
    # [EmpID] [int] NOT NULL,
    # [exportDate] [datetime] NULL,
    # [exportWorkWeek] [date] NULL,
    # [exportStatus] [varchar](50) NULL,
    # [exportStatusDetail] [varchar](max) NULL,
    # [exportType] [varchar](50) NULL
    
    try:           
        if abas_id is None or export_date is None or export_work_week is None:
            raise ValueError("abas_id, export_date, and export_work_week must be provided.")                

        # Insert a new record and get the new exportID using OUTPUT
        export_id = dbc.execute(
            """
            INSERT INTO ExportLog (EmpID, exportDate, exportWorkWeek, exportStatus, exportType, exportStatusDetail, exportSource)
            OUTPUT INSERTED.exportID
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (abas_id, export_date, export_work_week, export_status, export_type, export_status_detail, export_source)
        ).fetchone()[0]
        db.commit()
        print("Export log summary added successfully.")
        return export_id

    except Exception as e:
        db.rollback()
        print("Error adding export log summary:", str(e))
        return None

def add_exportlog_entry(export_id=None, emp_id=None, work_date=None, time_worked=None, paychex_code=None, work_slip=None, comments=None):
    db = get_db()
    dbc = db.cursor()    
    # export log detail table definition
    # [logID] [int] IDENTITY(1,1) NOT NULL,
    # [exportID] [int] NOT NULL,
    # [empID] [varchar](10) NULL,
    # [workDate] [date] NULL,
    # [timeWorked] [numeric](18, 2) NULL,
    # [paychexCode] [varchar](10) NULL,
    # [workSlip] [varchar](50) NULL,
    # [comments] [varchar](max) NULL
    
    try:
        if export_id is None or emp_id is None or work_date is None:
            raise ValueError("export_id, emp_id, and work_date must be provided.")

        # Insert a new record into the ExportLogDetail table
        dbc.execute(
            """
            INSERT INTO ExportLogDetail (exportID, empID, workDate, timeWorked, paychexCode, workSlip, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (export_id, emp_id, work_date, time_worked, paychex_code, work_slip, comments)
        )
        db.commit()
        
        print("Export log entry added successfully.")
        
    except Exception as e:
        db.rollback()
        print("Error adding export log entry:", str(e))
        
def get_weekly_operation_totals(timecard_data):
    # timecard_data: dict of {date: [entry, ...]}
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
    