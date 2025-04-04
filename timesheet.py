import pandas as pd
import pyodbc

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from db import get_db

bp = Blueprint('timesheet', __name__)

@bp.route("/timesheet")
def index():
    return render_template('timesheet/index.html')

@bp.route("/timesheet/entry", methods=('GET', 'POST'))
def entry():
    print("getUserID")

    abas_ID = ""
    abasUser = None

    if request.method == 'POST':
        print("POST")
        abas_ID = request.form['abas_ID']
        print("selected ID: " + abas_ID)

        # Validate that abas_ID is an integer
        if not abas_ID.isdigit():
            flash("Abas User ID must be a valid integer.", "error")
            return render_template('timesheet/entry.html', abasID=abas_ID)

        db = get_db()
        dbc = db.cursor()

        abasUser = dbc.execute("select e.*, s.EmpName as SupervisorName from employee as e inner join employee as s on e.Supervisor = s.Emp where e.empid = ?", abas_ID).fetchone()
        print (abasUser)
     
        return render_template('timesheet/entry.html', abasID=abas_ID, abasUser=abasUser)
    
    return render_template('timesheet/entry.html')

# #get timesheet data for selected user and return to ajax query
# @bp.route("/timesheet/card", methods=['POST'])
# def getCard():

#     return render_template('timesheet/_card.html')

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
    