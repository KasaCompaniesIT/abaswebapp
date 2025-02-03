import os, csv, time
import pandas as pd
import pyodbc

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from auth import login_required
from db import get_db

bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = set(['csv'])

@bp.route('/admin')
@login_required
def index():
    return render_template('admin/index.html')

@bp.route('/admin/import/results')
@login_required
def importResults():

    return render_template('admin/results.html')

@bp.route('/admin/importUsers', methods=('GET', 'POST'))
@login_required
def importUserCSV():    
    if request.method == 'POST':        
        updateCount = 0
        newCount = 0

        startTime = time.time()

        try:
            file = request.files['csvEFile']
            db = get_db()
            dbc = db.cursor()
            df = pd.read_csv(file, keep_default_na=False)   
            
            # flash("Importing Employee Data...")
            
            for index, row in df.iterrows():
                if not existingEmployee(row['ID']):
                    # insert new employee record
                    dbc.execute(
                        "INSERT INTO Employee (EmpID, Emp, EmpName, Dept, Supervisor, Wagegroup) VALUES (?, ?, ?, ?, ?, ?)",
                        (row['ID'], row['EMP'], row['NAME'], row['DEPT'], row['SUPERVISOR'], row['WG'])
                    )
                    dbc.commit()
                    print(f"Inserting new employee record: {row['EMP']}")
                    newCount += 1
                else:
                    # update existing employee record
                    dbc.execute(
                        "UPDATE Employee SET Emp=?, EmpName=?, Dept=?, Supervisor=?, Wagegroup=? WHERE empid=?",
                        (row['EMP'], row['NAME'], row['DEPT'], row['SUPERVISOR'], row['WG'], row['ID'])
                    )
                    dbc.commit()
                    print(f"Updating employee record: {row['EMP']}")
                    updateCount += 1

            currentTime = time.time()
            elapsedSeconds = currentTime - startTime

            return render_template('admin/results.html', results="File imported successfully", elapsed=elapsedSeconds, newcount=newCount, updatedcount=updateCount)
        except IOError:
            pass         
        except pyodbc.DatabaseError as err:
             error = err
             return str(error)

        return render_template('admin/results.html', results="Unable to read file")

    return render_template('admin/importCSV.html')

@bp.route('/admin/import', methods=('GET', 'POST'))
@login_required
def importCSV():    
    if request.method == 'POST':        
        updateProjectCount = 0
        newProjectCount = 0

        updateWOCount = 0
        newWOCount = 0

        updateWSCount = 0
        newWSCount = 0

        startTime = time.time()

        try:
            file = request.files['csvFile']
            db = get_db()
            dbc = db.cursor()
            df = pd.read_csv(file, keep_default_na=False)        
            
            # flash("Importing Labor Ops Data...")
            
            currentProject = ""
            currentWO = ""
            currentWS = ""

            for index, row in df.iterrows():
                projectID = row['project'].replace("P", "")
                if currentProject != projectID:
                    if not existingProject(projectID):
                        # insert new project record
                        dbc.execute(
                            "INSERT INTO projects (ProjectID, ProjectNumber, ProjectDescription) VALUES (?, ?, ?)",
                            (projectID, row['project'], row['prjdesc'])
                        )
                        dbc.commit()
                        print(f"Inserting new project record: {row['project']}")
                        newProjectCount += 1
                        currentProject = projectID
                    else:
                        # update existing project record
                        dbc.execute(
                            "UPDATE projects SET ProjectDescription=? WHERE projectid=?",
                            (row['prjdesc'], projectID)
                        )
                        dbc.commit()
                        print(f"Updating project record: {row['project']}")
                        updateProjectCount += 1
                        currentProject = projectID

                workorderID = row['wo']
                if currentWO != workorderID:
                    if not existingWO(row['wo']):
                        # insert new workorder
                        dbc.execute(
                            "INSERT INTO workorders (ProjectID, WONumber, WODescription, WOPart) VALUES (?, ?, ?, ?)",
                            (projectID, row['wo'], row['wodesc'], row['wopart'])
                        )
                        dbc.commit()
                        print(f"Inserting new workorder record: {row['wo']}")
                        newWOCount += 1
                        currentWO = workorderID
                    else:
                        # update existing workorder
                        dbc.execute(
                            "UPDATE workorders SET WODescription=?, WOPart=? WHERE wonumber=?",
                            (row['wodesc'], row['wopart'], row['wo'])
                        )
                        dbc.commit()
                        print(f"Updating workorder record: {row['wo']}")
                        updateWOCount += 1
                        currentWO = workorderID

                workslipID = row['wrkslp']
                if workslipID != currentWS:
                    if not existingWS(row['wrkslp']):
                        # insert new workslip
                        dbc.execute(
                            "INSERT INTO workslips (WSNumber, WONumber, WSDescription, WSDockDate, OpID) VALUES (?, ?, ?, ?, ?)",
                            (row['wrkslp'], row['wo'], row['wsdesc'], row['wsdockdate'], row['wslabop'])
                        )
                        dbc.commit()
                        print(f"Inserting new workslip record: {row['wrkslp']}")
                        newWSCount += 1
                        currentWS = workslipID
                    else:
                        # update new workslip
                        dbc.execute(
                            "UPDATE workslips SET WSDescription=?, WSDockDate=?, OpID=? WHERE WSNumber=?",
                            (row['wsdesc'], row['wsdockdate'], row['wslabop'], row['wrkslp'])
                        )
                        dbc.commit()
                        print(f"Updating workslip record: {row['wrkslp']}")
                        updateWSCount += 1
                        currentWS = workslipID

            currentTime = time.time()
            elapsedSeconds = currentTime - startTime

            return render_template('admin/results.html', results="File imported successfully", elapsed=elapsedSeconds, newprojects=newProjectCount, updatedprojects=updateProjectCount, newwo=newWOCount, updatewo=updateWOCount, newws=newWSCount, updatews=updateWSCount)          
        
        except IOError:
            pass         
        except pyodbc.DatabaseError as err:
             error = err
             return str(error)

        return render_template('admin/results.html', results="Unable to read file")

    return render_template('admin/importCSV.html')

# CSV file columns
# 
# M|project','M|prjdesc','M|wo','M|wopart','M|wodesc','M|wrkslp','M|wsdesc','M|wslabop','M|wslodpt','M|wsdockdate','M|wsopdesc'
# 
# project = P8905
# prjdesc = project description
# wo = work order number
# wopart = the work order production or project part
# wodesc = description of the work order
# wrkslp = 7 or 8 digit integer, left most 4 or 5 are the work order #, right most 3 digits is the labor operation within the production list
# wsdesc = work slip description - description of the labor op
# wslabop = operation number of the workslip
# wslodpt = operation's department
# wsdockdate = dock (due) date for this labor op
# wsopdesc = operation description

def existingProject(project):
    db = get_db()
    dbc = db.cursor()
    row  = dbc.execute(f"select * from projects where projectID = '{project}'").fetchone()
    if row:
        return True
    else:
        return False
    
def existingWO(wo):
    db = get_db()
    dbc = db.cursor()
    row  = dbc.execute(f"select * from workorders where wonumber = '{wo}'").fetchone()
    if row:
        return True
    else:
        return False
    
def existingWS(ws):
    db = get_db()
    dbc = db.cursor()
    row  = dbc.execute(f"select * from workslips where wsnumber = '{ws}'").fetchone()
    if row:
        return True
    else:
        return False
    
def existingEmployee(eid):
    db = get_db()
    dbc = db.cursor()
    row  = dbc.execute(f"select * from employee where empid = '{eid}'").fetchone()
    if row:
        return True
    else:
        return False

def allowed_filename(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS