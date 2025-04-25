import pandas as pd
import pyodbc
from datetime import datetime, timedelta, date

from flask import (
    Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort, Unauthorized, Forbidden, NotFound
from auth import login_required
from db import get_db

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
            # Pass the data to the template
            return render_template('timesheet/entry.html',
                                    abasID=abas_ID,
                                    abasUser=abasUser,
                                    startOfPrevWeek=startOfPrevWeek, 
                                    endOfPrevWeek=endOfPrevWeek,
                                    dateRangePrevWeek=dateRangePrevWeek,
                                    timecard_data=timecard_data,
                                    today=today
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
        # Insert the new time entry and fetch the inserted ID
        new_entry_id = dbc.execute(
            """
            INSERT INTO TimeEntry (EmpID, WorkDate, WSNumber, TimeWorked)
            OUTPUT INSERTED.EntryID
            VALUES (?, ?, ?, ?)
            """,
            (abas_id, selected_date, work_slip_id, hours_worked)
        ).fetchone()[0]

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

        # Convert the pyodbc.Row object to a dictionary
        new_entry_dict = dict(zip([column[0] for column in dbc.description], new_entry))

        db.commit()
        return jsonify({'success': True, 'data': new_entry_dict}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/timesheet/entry/delete/<int:time_entry_id>', methods=['POST'])
@login_required
def delete_time_entry(time_entry_id):
    db = get_db()
    dbc = db.cursor()

    try:
        dbc.execute("DELETE FROM TimeEntry WHERE EntryID = ?", (time_entry_id,))
        db.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    
