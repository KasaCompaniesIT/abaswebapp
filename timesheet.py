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
def index():
    return render_template('timesheet/index.html')

@bp.route("/timesheet/entry", methods=('GET', 'POST'))
@login_required
def entry():
    print("getUserID")

    abas_ID = ""
    abasUser = None
    error = None

    if request.method == 'POST' or g.user.EmpID != 0:
        if request.method == 'POST':
            print("POST")
            button_clicked = request.form.get('button')
            startDate = request.form.get('startDate')  # Get the startDate from the form
            abas_ID = request.form['abas_ID']
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
        
        #print (abasUser)        
        if abasUser:     
            # check if logged in user matches the selected user
            if g.user.EmpID != abasUser.EmpID and g.user.Emp != abasUser.Supervisor:       
                if g.user.isAdmin == 0:
                    error = "You are not authorized to view this user's timesheet."
                    flash(error)
                    return render_template('timesheet/entry.html')
                
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
            startOfPrevWeek = startDate - timedelta(days=startDate.weekday())
            endOfPrevWeek = startOfPrevWeek + timedelta(days=6)

            # Determine if adding/finalizing time is allowed
            now = datetime.now()
            is_current_week = startOfPrevWeek <= now.date() <= endOfPrevWeek
            is_previous_week_allowed = (
                now.weekday() == 0 and now.hour < 12 and startOfPrevWeek == (now.date() - timedelta(days=7))
            )

            can_add_or_finalize = is_current_week or is_previous_week_allowed

            # Generate a list of dates for the previous week
            # dateRangePrevWeek = [
            #     (startOfPrevWeek + timedelta(days=i)).strftime("%m/%d/%y")
            #     for i in range((endOfPrevWeek - startOfPrevWeek).days + 1)
            # ]
            dateRangePrevWeek = [
                {
                    "date": (startOfPrevWeek + timedelta(days=i)).strftime("%m/%d/%y"),
                    "isHoliday": dbc.execute(
                        "SELECT 1 FROM Holidays WHERE holidayDate = ?",
                        ((startOfPrevWeek + timedelta(days=i)).strftime("%Y-%m-%d"),)
                    ).fetchone() is not None  # Check if the date exists in the Holidays table
                }
                for i in range((endOfPrevWeek - startOfPrevWeek).days + 1)
            ]

            # Fetch timecard data for each date
            timecard_data = {}
            for day in dateRangePrevWeek:
                print(day["date"])
                # Fetch timecard data for the specific date
                timeEntryAbas = dbc.execute("""
                            select EmpID, WorkDate, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, sum(TimeWorked) as tHoursWorked 
                            from TimeEntryAbas 
                            inner join WorkSlips on TimeEntryAbas.WSNumber = WorkSlips.WSNumber 
                            inner join Operations on WorkSlips.OpID = Operations.OpID
                            where EmpID = ? and WorkDate = ? 
                            group by EmpID, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, WorkDate 
                            order by EmpID, WorkDate
                            """
                            , abasUser.EmpID, day["date"]).fetchall()
                
                timeEntry = dbc.execute("""
                            select EntryID, EmpID, WorkDate, TimeEntry.WSNumber, WSDescription, OpName, OpNameExtended, TimeWorked as tHoursWorked 
                            from TimeEntry 
                            inner join WorkSlips on TimeEntry.WSNumber = WorkSlips.WSNumber 
                            inner join Operations on WorkSlips.OpID = Operations.OpID
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
                    combined_entries.append({
                        "EmpID": entry.EmpID,
                        "WorkDate": entry.WorkDate,
                        "WSNumber": entry.WSNumber,
                        "WSDescription": entry.WSDescription,
                        "OpName": entry.OpName,
                        "OpNameExtended": entry.OpNameExtended,
                        "tHoursWorked": entry.tHoursWorked,
                        "TimeEntryID": None  # No TimeEntryID for TimeEntryAbas
                    })

                # Add entries from timeEntry only if they don't exist in timeEntryAbas
                for entry in timeEntry:
                    key = (entry.EmpID, entry.WorkDate, entry.WSNumber)
                    if key not in abas_keys:
                        combined_entries.append({
                            "EmpID": entry.EmpID,
                            "WorkDate": entry.WorkDate,
                            "WSNumber": entry.WSNumber,
                            "WSDescription": entry.WSDescription,
                            "OpName": entry.OpName,
                            "OpNameExtended": entry.OpNameExtended,
                            "tHoursWorked": entry.tHoursWorked,
                            "TimeEntryID": entry.EntryID  # Include TimeEntryID for deletion
                        })

                # Sort the combined entries by EmpID, WorkDate, and WSNumber
                combined_entries.sort(key=lambda x: (x["EmpID"], x["WorkDate"], x["WSNumber"]))

                timecard_data[day["date"]] = combined_entries

                # print(f"Date: {date}, Rows: {rows}")

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
                                    week_finalized=week_finalized
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

    workslips = dbc.execute("select WSNumber, WONumber, WSDescription, Operations.OpID, OpCode, OpName, OpNameExtended from workslips inner join operations on WorkSlips.OpID = operations.OpID where wonumber = ? order by wsnumber", selected_wo)
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

    workslips = dbc.execute("select WSNumber, WSDescription, Operations.OpID, OpCode, OpName, OpNameExtended from workslips inner join operations on WorkSlips.OpID = operations.OpID where wonumber = ? order by wsnumber", work_order_id).fetchall()
    # print(workslips)
    return jsonify({'workSlips': [{'id': row.WSNumber, 'name': row.OpName, 'nameExtended': row.OpNameExtended} for row in workslips]})


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

        # new_entry is already a dict!
        response = send_timeentry_csv_to_abas(abas_id, selected_date, work_slip_id, hours_worked)

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


@bp.route('/timesheet/entry/delete/<int:time_entry_id>', methods=['POST'])
@login_required
def delete_time_entry(time_entry_id):
    db = get_db()
    dbc = db.cursor()

    try:
        # Fetch the entry being deleted
        entry = dbc.execute(
            """
            SELECT EmpID, WorkDate, WSNumber, TimeWorked
            FROM TimeEntry
            WHERE EntryID = ?
            """,
            (time_entry_id,)
        ).fetchone()

        if not entry:
            raise ValueError("Time entry not found.")

        # Extract entry details
        abas_id = entry.EmpID
        selected_date = entry.WorkDate
        work_slip_id = entry.WSNumber
        hours_worked = 0 # entry.TimeWorked

        # Define the API endpoint
        url = "http://abas.kasa.kasacontrols.com:8000/jobtime_entry"

        # Define the payload
        payload = {
            "EmpID": abas_id,
            "WorkDate": selected_date.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY
            "WSNumber": work_slip_id,
            "HoursWorked": hours_worked
        }

        # Send the POST request
        response = requests.post(url, json=payload)

        # Check the response
        if response.status_code == 200:
            # Delete the entry from the database
            dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (time_entry_id,))
            db.commit()
            print("CSV file sent successfully!")
        else:
            print(f"Failed to create CSV. Status code: {response.status_code}, Response: {response.text}")

        # # Generate a unique file name using a timestamp
        # timestamp = datetime.now().strftime('%Y%m%d%H%M%S')  # Format: YYYYMMDDHHMMSS
        # unique_file_name = f"jobtime_{abas_id}_{timestamp}.csv"

        # # Define the network location for the CSV file        
        # network_path = os.path.join(ABAS_SERVER, unique_file_name)  # Replace with your actual network path

        # # Write the negated entry to the CSV file
        # with open(network_path, mode='w', newline='', encoding='utf-8') as csvfile:
        #     csv_writer = csv.writer(csvfile)
        #     # Write the header
        #     csv_writer.writerow(['AbasID', 'Date', 'WorkSlipID', 'HoursWorked'])
        #     # Write the negated entry
        #     csv_writer.writerow([abas_id, selected_date, work_slip_id, hours_worked])  # Negate the hours



        return jsonify({'success': True}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    
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
@bp.route('/timesheet/entry/get_time_entries', methods=['GET'])
@login_required
def get_time_entries():
    try:
        # Get the start and end dates for the current week
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        abas_id = request.args.get('abas_id')

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

        # Fetch time entries for the given date range
        time_entries = dbc.execute(
            """
            SELECT EntryID, WorkDate, t.WSNumber, TimeWorked, OpName, OpNameExtended
            FROM TimeEntry t 
            INNER JOIN WorkSlips w ON t.WSNumber = w.WSNumber 
            INNER JOIN Operations o ON w.OpID = o.OpID
            WHERE EmpID = ? AND WorkDate BETWEEN ? AND ?
            ORDER BY WorkDate
            """,
            (abas_id, start_date, end_date)
        ).fetchall()

        # Convert the results to a list of dictionaries
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
                "EntryID": entry.EntryID,
                "WorkDate": entry.WorkDate.strftime('%m/%d/%y'),  # Format the date as MM/DD/YY,
                "WSNumber": entry.WSNumber,
                "OpName": entry.OpName,
                "OpNameExtended": entry.OpNameExtended,
                "tHoursWorked": entry.TimeWorked
            })

        print("Time Entries:", time_entries_list)  # Debugging: Log the data
        return jsonify({"success": True, "time_entries": time_entries_list}), 200
    except Exception as e:
        print("Error fetching time entries:", str(e))  # Debugging: Log the error
        return jsonify({"success": False, "error": str(e)}), 500    


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
        
        # Create a new copy of the JSON data with converted Paychex codes
        # converted_data = {
        #     "abas_id": data.get("abas_id"),
        #     "total_hours": data.get("total_hours"),
        #     "time_entries": [
        #         {
        #             "date": entry["date"],
        #             "paychexCode": paychex_code_mapping.get(int(entry["paychexCode"]), entry["paychexCode"]),  # Map PayID to PayChex code
        #             "hours": entry["hours"]
        #         }
        #         for entry in data.get("time_entries", [])
        #     ]
        # }

        grouped = defaultdict(float)
        for entry in data.get("time_entries", []):
            date = entry["date"]
            paychex_code = paychex_code_mapping.get(int(entry["paychexCode"]), entry["paychexCode"])
            hours = float(entry["hours"])
            grouped[(date, paychex_code)] += hours

        # 2. Build the combined time_entries list
        combined_time_entries = [
            {"date": date, "paychexCode": paychex_code, "hours": hours}
            for (date, paychex_code), hours in grouped.items()
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
        
        # Calculate the start and end of the week
        prev_start = curr_start - timedelta(days=7)
        print("prev_start: ", prev_start)
        prev_end = prev_start + timedelta(days=6)
        print("prev_end: ", prev_end)

        # 1. Fetch previous week's entries
        print("get_time_entries_for_week")
        prev_entries = get_time_entries_for_week(abas_id, prev_start, prev_end)  # Implement this helper
        print("prev_entries: ", prev_entries)
        
        if prev_entries:
            # 2. Copy entries to current week (adjust dates)
            for entry in prev_entries:
                # Calculate new date for current week
                prev_date = entry.WorkDate
                days_offset = (prev_date - prev_start).days
                new_date = curr_start + timedelta(days=days_offset)
                print("new_date: ", new_date)
                # Create new entry (implement create_time_entry as needed)
                new_entry = create_time_entry(abas_id, new_date, entry.WSNumber, entry.TimeWorked)
                print("new_entry: ", new_entry)
                
                if new_entry:
                    # After creating new_entry or when building any JSON response:
                    time_worked = float(entry.TimeWorked) if isinstance(entry.TimeWorked, decimal.Decimal) else entry.TimeWorked
                    response = send_timeentry_csv_to_abas(abas_id, new_date, entry.WSNumber, time_worked)
                    if response.status_code != 200:
                        raise ValueError(f"Failed to send data for {new_date}.")

            flash("Previous week's entries copied successfully.", "success")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'No entries found for the previous week.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


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
        
        time_entry = get_time_entry(entry_id=entry_id)
        print("time_entry: ", time_entry)
        abas_id = time_entry[1]
        entry_date = time_entry[2]
        work_slip_id = time_entry[3]
        time_worked = float(time_entry[4])
        response = send_timeentry_csv_to_abas(abas_id, entry_date, work_slip_id, time_worked)
        if response.status_code != 200:
            raise ValueError(f"Failed to send data for {time_entry.WorkDate}.")
                
        return jsonify({'success': True, 'hoursWorked': f"{float(hours_worked):.2f}"})
    except Exception as e:
        db.rollback()
        print("Error updating hours:", str(e))  # Debugging: Log the error
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

    return time_entries

def get_paychex_codes():
    db = get_db()
    dbc = db.cursor()

    paychex_codes = dbc.execute(
        "SELECT PayID, PayChex FROM paychex ORDER BY PayChex"
    ).fetchall()

    # Convert PayID to PayChex code mapping
    paychex_mapping = {row.PayID: row.PayChex for row in paychex_codes}

    return paychex_mapping

def lookup_paychex_id(paychex_id):
    db = get_db()
    dbc = db.cursor()

    paychex_code = dbc.execute(
        "SELECT PayID, PayChex, PayDescription FROM paychex WHERE PayID = ? ORDER BY PayChex", paychex_id
    ).fetchone()

    paycode = paychex_code.PayChex if paychex_code else None

    return paycode

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
            SELECT t.EntryID AS TimeEntryID, t.WSNumber, ws.WSDescription, o.OpName, o.OpNameExtended, t.TimeWorked AS tHoursWorked
            FROM TimeEntry t
            INNER JOIN WorkSlips ws ON t.WSNumber = ws.WSNumber
            INNER JOIN Operations o ON ws.OpID = o.OpID
            WHERE t.EntryID = ?
            """,
            (new_entry_id,)
        ).fetchone()
        
        if not new_entry:
            raise ValueError("Failed to fetch the newly added time entry.")

        # Build a dictionary directly using column names
        columns = [column[0] for column in dbc.description]
        entry_dict = dict(zip(columns, new_entry))
        # Convert Decimal to float if needed
        for k, v in entry_dict.items():
            if isinstance(v, decimal.Decimal):
                entry_dict[k] = f"{float(v):.2f}"
        return entry_dict

    except Exception as e:
        db.rollback()
        print("Error creating time entry:", str(e))
        return None

def get_time_entry(abas_id=None, work_date=None, ws_number=None, entry_id=None):
    db = get_db()
    dbc = db.cursor()

    if entry_id:
        # If entry_id is provided, fetch the specific entry
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
        time_entry = dbc.execute(
            """
            SELECT EntryID, EmpID, WorkDate, WSNumber, TimeWorked
            FROM TimeEntry
            WHERE EmpID = ? AND WorkDate = ? AND WSNumber = ?
            """,
            (abas_id, work_date, ws_number)
        ).fetchone()

    return time_entry

def send_timeentry_csv_to_abas(abas_id, work_date, work_slip_id, hours_worked):
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
        "HoursWorked": hours_worked
    }

    # Send the POST request
    response = requests.post(url, json=payload)

    return response