import pandas as pd
import pyodbc
from datetime import datetime, timedelta, date

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
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


            # def get_previous_week(start_date):
            #     #today = datetime.now().date()  # Get today's date without the time
            #     # Move back 7 days to ensure we're in the previous week
            #     last_week = start_date - timedelta(days=7)
            #     # Calculate the start (Monday) of the previous week
            #     start_of_week = last_week - timedelta(days=last_week.weekday())
            #     # Calculate the end (Sunday) of the previous week
            #     end_of_week = start_of_week + timedelta(days=6)
            #     return start_of_week, end_of_week

            # # Usage
            # startOfPrevWeek, endOfPrevWeek = get_previous_week(startDate)
            print("Start of the previous week:", startOfPrevWeek.strftime("%m/%d/%y"))
            print("End of the previous week:", endOfPrevWeek.strftime("%m/%d/%y"))

            # Generate a list of dates for the previous week
            dateRangePrevWeek = [
                (startOfPrevWeek + timedelta(days=i)).strftime("%m/%d/%y")
                for i in range((endOfPrevWeek - startOfPrevWeek).days + 1)
            ]

            # Fetch timecard data for each date
            timecard_data = {}
            for date in dateRangePrevWeek:
                rows = dbc.execute("""
                            select EmpID, WorkDate, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, sum(TimeWorked) as tHoursWorked 
                            from TimeEntryAbas 
                            inner join WorkSlips on TimeEntryAbas.WSNumber = WorkSlips.WSNumber 
                            inner join Operations on WorkSlips.OpID = Operations.OpID
                            where EmpID = ? and WorkDate = ? 
                            group by EmpID, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, WorkDate 
                            order by EmpID, WorkDate
                            """
                            , abasUser.EmpID, date).fetchall()
                timecard_data[date] = rows
                print(f"Date: {date}, Rows: {rows}")

            # Pass the data to the template
            return render_template('timesheet/entry.html',
                                    abasID=abas_ID,
                                    abasUser=abasUser,
                                    startOfPrevWeek=startOfPrevWeek, 
                                    endOfPrevWeek=endOfPrevWeek,
                                    dateRangePrevWeek=dateRangePrevWeek,
                                    timecard_data=timecard_data
            )

            # return render_template('timesheet/entry.html', abasID=abas_ID, abasUser=abasUser, startOfPrevWeek=startOfPrevWeek, endOfPrevWeek=endOfPrevWeek, dateRangePrevWeek=dateRangePrevWeek)
        else:
            flash(error)
            
    return render_template('timesheet/entry.html')

#get timesheet data for selected user and return to ajax query
@bp.route("/timesheet/card", methods=['POST'])
@login_required
def getCard():
    print("getCard")

    if request.method == 'POST':
        print("POST")
        abas_ID = request.form.get['abas_ID']
        print("selected ID: " + abas_ID)

        tsDate = request.form.get['tsDate']
        print("selected date: " + tsDate)

        db = get_db()
        dbc = db.cursor()

    timecard_data = dbc.execute("""
                                    select EmpID, WorkDate, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, sum(TimeWorked) as tHoursWorked 
                                    from TimeEntryAbas 
                                    inner join WorkSlips on TimeEntryAbas.WSNumber = WorkSlips.WSNumber 
                                    inner join Operations on WorkSlips.OpID = Operations.OpID
                                    where EmpID = ? and WorkDate = ? 
                                    group by EmpID, TimeEntryAbas.WSNumber, WSDescription, OpName, OpNameExtended, WorkDate 
                                    order by EmpID, WorkDate
                                    """
                                    , abas_ID, tsDate.strftime("%m/%d/%Y"))

    if timecard_data:
        # Render the _card.html template with the fetched data
        return render_template('timesheet/_card.html', timeData=timecard_data)
    else:
        # Return an empty response with a 204 status code
        return render_template('timesheet/_card.html', timeData=None)

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
    