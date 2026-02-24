import os, csv, time
import pandas as pd
import pyodbc

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from auth import login_required
from db import get_db
from timesheet import get_week_start

bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = set(['csv'])

@bp.route('/admin')
@login_required
def index():
    if g.user.isAdmin:
        return render_template('admin/index.html')
    else:
        return "Unauthorized access"

@bp.route('/admin/import/results')
@login_required
def importResults():
    if g.user.isAdmin:
        return render_template('admin/results.html')
    else:
        return "Unauthorized access"
    
@bp.route('/admin/importUsers', methods=('GET', 'POST'))
@login_required
def importUserCSV():    
    if g.user.isAdmin:
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
                print(f"Importing Employee Data......Finished  in {elapsedSeconds:.2f} seconds")        
                print(f"{newCount} new employee records.  {updateCount} updated employee records.")
            
                return render_template('admin/results.html', results="Employee File imported successfully", elapsed=elapsedSeconds, newcount=newCount, updatedcount=updateCount)
            except IOError:
                pass         
            except pyodbc.DatabaseError as err:
                error = err
                print("Importing Employee Data......Incomplete")            
                print(f"{newCount} new employee records.  {updateCount} updated employee records.")
                print(error)            
                            
                return str(error)

            return render_template('admin/results.html', results="Unable to read file")

        return render_template('admin/importCSV.html')
    else:
        return "Unauthorized access"
    
@bp.route('/admin/import', methods=('GET', 'POST'))
@login_required
def importCSV():    
    if g.user.isAdmin:
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
                print(f"Importing Labor Ops Data......Finished in {elapsedSeconds:.2f} seconds")        
                print(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
                print(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")        
                print(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")        

                return render_template('admin/results.html', results="Labor Ops File imported successfully", elapsed=elapsedSeconds, newcount=newProjectCount+newWOCount+newWSCount, updatedcount=updateProjectCount+updateWOCount+updateWSCount)          
            
            except IOError:
                pass         
            except pyodbc.DatabaseError as err:
                error = err
                print("Importing Labor Ops Data......Incomplete")            
                print(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
                print(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")
                print(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")
                print(error)

                return str(error)

            return render_template('admin/results.html', results="Unable to read file")

        return render_template('admin/importCSV.html')
    else:
        return "Unauthorized access"
    
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

@bp.route('/admin/employees', methods=('GET', 'POST'))
@login_required
def manage_employees():
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    if request.method == 'POST':
        # Handle form submission to update employee details
        emp_id = request.form.get('EmpID')
        is_admin = request.form.get('isAdmin') == 'on'  # Checkbox value
        is_hourly = request.form.get('isHourly') == 'on'  # Checkbox value
        is_mxemp = request.form.get('isMxEmp') == 'on'  # Checkbox value
        paychex_id = request.form.get('PayChexID')
        salary_plus_start = request.form.get('SalaryPlusStart')

        # Only allow super admins to set the isSuperAdmin field
        if g.user.isSuperAdmin:
            is_superadmin = request.form.get('isSuperAdmin') == 'on'  # Checkbox value
        else:
            # Prevent non-super admins from modifying this field
            is_superadmin = None

        try:
            # Update the employee record
            if is_superadmin is not None:
                # Include isSuperAdmin in the update if the user is a super admin
                dbc.execute(
                    """
                    UPDATE Employee
                    SET isAdmin = ?, PayChexID = ?, SalaryPlusStart = ?, isHourly = ?, isSuperAdmin = ?, isMxEmp = ?
                    WHERE EmpID = ?
                    """,
                    (is_admin, paychex_id, salary_plus_start, is_hourly, is_superadmin, is_mxemp, emp_id)
                )
            else:
                # Exclude isSuperAdmin from the update if the user is not a super admin
                dbc.execute(
                    """
                    UPDATE Employee
                    SET isAdmin = ?, PayChexID = ?, SalaryPlusStart = ?, isHourly = ?, isMxEmp = ?
                    WHERE EmpID = ?
                    """,
                    (is_admin, paychex_id, salary_plus_start, is_hourly, is_mxemp, emp_id)
                )

            db.commit()
            flash(f"Employee {emp_id} updated successfully!", "success")
        except pyodbc.DatabaseError as err:
            db.rollback()
            flash(f"Error updating employee {emp_id}: {err}", "danger")

    # Fetch all employees to display in the table
    employees = dbc.execute("""
        SELECT EmpID, Emp, EmpName, Dept, Supervisor, Wagegroup, isAdmin, PayChexID, SalaryPlusStart, isHourly, isSuperAdmin, isMxEmp
        FROM Employee
        ORDER BY EmpName
    """).fetchall()

    # Fetch all PayChex entries for the dropdown
    paychex_entries = dbc.execute("""
        SELECT PayID, PayChex, PayDescription
        FROM PayChex
        ORDER BY PayDescription
    """).fetchall()

    return render_template('admin/employees.html', employees=employees, paychex_entries=paychex_entries)

@bp.route('/admin/paychex_codes', methods=['GET', 'POST'])
@login_required
def manage_paychex_codes():
    # Only allow admin users
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    # Handle add/update/delete actions
    if request.method == 'POST':
        action = request.form.get('action')
        payid = request.form.get('payid')
        paychex = request.form.get('paychex')
        description = request.form.get('description')
        in_use = int(request.form.get('in_use', 1))

        if action == 'add':
            dbc.execute(
                "INSERT INTO paychex (PayChex, PayDescription, inUse) VALUES (?, ?, ?)",
                (paychex, description, in_use)
            )
        elif action == 'update' and payid:
            dbc.execute(
                "UPDATE paychex SET PayChex=?, PayDescription=?, inUse=? WHERE PayID=?",
                (paychex, description, in_use, payid)
            )
        elif action == 'delete' and payid:
            dbc.execute("DELETE FROM paychex WHERE PayID=?", (payid,))
        db.commit()

    codes = dbc.execute(
        "SELECT PayID, PayChex, PayDescription, inUse FROM paychex ORDER BY PayDescription, PayChex"
    ).fetchall()

    return render_template('admin/paychex_codes.html', codes=codes)

@bp.route('/admin/holidays', methods=['GET', 'POST'])
@login_required
def manage_holidays():
    # Only allow admin users
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    # Handle add/delete actions
    if request.method == 'POST':
        action = request.form.get('action')
        holiday_date = request.form.get('holiday_date')

        if action == 'add' and holiday_date:
            dbc.execute("INSERT INTO Holidays (holidayDate) VALUES (?)", (holiday_date,))
        elif action == 'delete' and holiday_date:
            dbc.execute("DELETE FROM Holidays WHERE holidayDate = ?", (holiday_date,))
        db.commit()

    holidays = dbc.execute(
        "SELECT holidayDate FROM Holidays ORDER BY holidayDate DESC"
    ).fetchall()

    return render_template('admin/holidays.html', holidays=holidays)

@bp.route('/admin/operations', methods=['GET', 'POST'])
@login_required
def manage_operations():
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)
    
    db = get_db()
    dbc = db.cursor()

    if request.method == 'POST':
        # Update OpCode and isEnabled for all rows in the form
        for key, value in request.form.items():
            if key.startswith('OpCode_'):
                op_id = key.split('_')[1]
                op_code = value
                is_enabled = 1 if request.form.get(f'isEnabled_{op_id}') == 'on' else 0
                op_wage_group = request.form.get(f'OpWageGroup_{op_id}', '')
                dbc.execute(
                    "UPDATE Operations SET OpCode=?, OpWageGroup=?, isEnabled=? WHERE OpID=?",
                    (op_code, op_wage_group, is_enabled, op_id)
                )
        db.commit()
        flash('Operations updated successfully.', 'success')
        return redirect(url_for('admin.manage_operations'))

    operations = dbc.execute(
        "SELECT OpID, OpName, OpNameExtended, OpCode, OpWageGroup, isEnabled FROM Operations ORDER BY OpID"
    ).fetchall()
    return render_template('admin/operations.html', operations=operations)

@bp.route('/admin/project_data', methods=['GET', 'POST'])
@login_required
def manage_project_data():
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    if request.method == 'POST':
        entity = request.form.get('entity')
        action = request.form.get('action')

        try:
            if entity == 'project':
                project_id = request.form.get('ProjectID', '').strip()
                project_number = request.form.get('ProjectNumber', '').strip()
                project_description = request.form.get('ProjectDescription', '').strip()
                project_complete = 1 if request.form.get('ProjectComplete') == 'on' else 0
                project_complete_date = request.form.get('ProjectCompleteDate', '').strip()
                hide_from_use = 1 if request.form.get('hideFromUse') == 'on' else 0
                # project_closed = 1 if request.form.get('ProjectClosed') == 'on' else 0
                # project_closed_date = request.form.get('ProjectClosedDate', '').strip()

                if action == 'add':
                    dbc.execute(
                        """
                        INSERT INTO Projects (
                            ProjectID, ProjectNumber, ProjectDescription, ProjectComplete,
                            ProjectCompleteDate, hideFromUse
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(project_id),
                            project_number,
                            project_description or None,
                            project_complete,
                            project_complete_date or None,
                            hide_from_use,
                        )
                    )
                    flash(f'Project {project_id} added.', 'success')
                elif action == 'update':
                    dbc.execute(
                        """
                        UPDATE Projects
                        SET ProjectNumber = ?, ProjectDescription = ?, ProjectComplete = ?,
                            ProjectCompleteDate = ?, hideFromUse = ?
                        WHERE ProjectID = ?
                        """,
                        (
                            project_number,
                            project_description or None,
                            project_complete,
                            project_complete_date or None,
                            hide_from_use,
                            int(project_id),
                        )
                    )
                    flash(f'Project {project_id} updated.', 'success')
                elif action == 'delete':
                    dbc.execute("DELETE FROM Projects WHERE ProjectID = ?", (int(project_id),))
                    flash(f'Project {project_id} deleted.', 'success')

            elif entity == 'workorder':
                project_id = request.form.get('ProjectID', '').strip()
                wo_number = request.form.get('WONumber', '').strip()
                wo_description = request.form.get('WODescription', '').strip()
                wo_part = request.form.get('WOPart', '').strip()
                hide_from_use = 1 if request.form.get('hideFromUse') == 'on' else 0

                if action == 'add':
                    dbc.execute(
                        """
                        INSERT INTO WorkOrders (ProjectID, WONumber, WODescription, WOPart, hideFromUse)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (int(project_id), int(wo_number), wo_description or None, wo_part or None, hide_from_use)
                    )
                    flash(f'WorkOrder {wo_number} added.', 'success')
                elif action == 'update':
                    dbc.execute(
                        """
                        UPDATE WorkOrders
                        SET ProjectID = ?, WODescription = ?, WOPart = ?, hideFromUse = ?
                        WHERE WONumber = ?
                        """,
                        (int(project_id), wo_description or None, wo_part or None, hide_from_use, int(wo_number))
                    )
                    flash(f'WorkOrder {wo_number} updated.', 'success')
                elif action == 'delete':
                    dbc.execute("DELETE FROM WorkOrders WHERE WONumber = ?", (int(wo_number),))
                    flash(f'WorkOrder {wo_number} deleted.', 'success')

            elif entity == 'workslip':
                ws_number = request.form.get('WSNumber', '').strip()
                wo_number = request.form.get('WONumber', '').strip()
                ws_description = request.form.get('WSDescription', '').strip()
                ws_dock_date = request.form.get('WSDockDate', '').strip()
                op_id = request.form.get('OpID', '').strip()
                hide_from_use = 1 if request.form.get('hideFromUse') == 'on' else 0

                if action == 'add':
                    dbc.execute(
                        """
                        INSERT INTO WorkSlips (WSNumber, WONumber, WSDescription, WSDockDate, OpID, hideFromUse)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (int(ws_number), int(wo_number), ws_description or None, ws_dock_date or None, int(op_id), hide_from_use)
                    )
                    flash(f'WorkSlip {ws_number} added.', 'success')
                elif action == 'update':
                    dbc.execute(
                        """
                        UPDATE WorkSlips
                        SET WONumber = ?, WSDescription = ?, WSDockDate = ?, OpID = ?, hideFromUse = ?
                        WHERE WSNumber = ?
                        """,
                        (int(wo_number), ws_description or None, ws_dock_date or None, int(op_id), hide_from_use, int(ws_number))
                    )
                    flash(f'WorkSlip {ws_number} updated.', 'success')
                elif action == 'delete':
                    dbc.execute("DELETE FROM WorkSlips WHERE WSNumber = ?", (int(ws_number),))
                    flash(f'WorkSlip {ws_number} deleted.', 'success')

            db.commit()
        except (ValueError, TypeError):
            db.rollback()
            flash('Invalid input values. Please check numeric fields.', 'danger')
        except pyodbc.DatabaseError as err:
            db.rollback()
            flash(f'Database error: {err}', 'danger')

        section_anchor_map = {
            'project': 'projects',
            'workorder': 'workorders',
            'workslip': 'workslips'
        }
        section_anchor = section_anchor_map.get(entity, 'projects')

        redirect_url = url_for(
            'admin.manage_project_data',
            project_q=request.args.get('project_q', ''),
            project_page=request.args.get('project_page', 1),
            workorder_q=request.args.get('workorder_q', ''),
            workorder_page=request.args.get('workorder_page', 1),
            workslip_q=request.args.get('workslip_q', ''),
            workslip_page=request.args.get('workslip_page', 1)
        )
        return redirect(f"{redirect_url}#{section_anchor}")

    def parse_page(value):
        try:
            page_value = int(value)
            return page_value if page_value > 0 else 1
        except (TypeError, ValueError):
            return 1

    per_page = 25

    project_q = request.args.get('project_q', '').strip()
    workorder_q = request.args.get('workorder_q', '').strip()
    workslip_q = request.args.get('workslip_q', '').strip()

    project_page = parse_page(request.args.get('project_page', 1))
    workorder_page = parse_page(request.args.get('workorder_page', 1))
    workslip_page = parse_page(request.args.get('workslip_page', 1))

    project_where = []
    project_params = []
    if project_q:
        project_where.append("(CAST(ProjectID AS NVARCHAR(20)) LIKE ? OR ProjectNumber LIKE ? OR ProjectDescription LIKE ?)")
        project_like = f"%{project_q}%"
        project_params.extend([project_like, project_like, project_like])
    project_where_sql = f"WHERE {' AND '.join(project_where)}" if project_where else ""

    total_projects = dbc.execute(
        f"SELECT COUNT(*) FROM Projects {project_where_sql}",
        project_params
    ).fetchone()[0]
    project_total_pages = max(1, (total_projects + per_page - 1) // per_page)
    project_page = min(project_page, project_total_pages)
    project_offset = (project_page - 1) * per_page

    projects = dbc.execute(
        f"""
         SELECT ProjectID, ProjectNumber, ProjectDescription, ProjectComplete,
             hideFromUse,
               ProjectCompleteDate, ProjectClosed, ProjectClosedDate
        FROM Projects
        {project_where_sql}
        ORDER BY ProjectID
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        project_params + [project_offset, per_page]
    ).fetchall()

    workorder_where = []
    workorder_params = []
    if workorder_q:
        workorder_where.append("(CAST(ProjectID AS NVARCHAR(20)) LIKE ? OR CAST(WONumber AS NVARCHAR(20)) LIKE ? OR WODescription LIKE ? OR WOPart LIKE ?)")
        workorder_like = f"%{workorder_q}%"
        workorder_params.extend([workorder_like, workorder_like, workorder_like, workorder_like])
    workorder_where_sql = f"WHERE {' AND '.join(workorder_where)}" if workorder_where else ""

    total_workorders = dbc.execute(
        f"SELECT COUNT(*) FROM WorkOrders {workorder_where_sql}",
        workorder_params
    ).fetchone()[0]
    workorder_total_pages = max(1, (total_workorders + per_page - 1) // per_page)
    workorder_page = min(workorder_page, workorder_total_pages)
    workorder_offset = (workorder_page - 1) * per_page

    workorders = dbc.execute(
        f"""
        SELECT ProjectID, WONumber, WODescription, WOPart, hideFromUse
        FROM WorkOrders
        {workorder_where_sql}
        ORDER BY WONumber
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        workorder_params + [workorder_offset, per_page]
    ).fetchall()

    workslip_where = []
    workslip_params = []
    if workslip_q:
        workslip_where.append("(CAST(WSNumber AS NVARCHAR(20)) LIKE ? OR CAST(WONumber AS NVARCHAR(20)) LIKE ? OR WSDescription LIKE ? OR WSDockDate LIKE ? OR CAST(OpID AS NVARCHAR(20)) LIKE ?)")
        workslip_like = f"%{workslip_q}%"
        workslip_params.extend([workslip_like, workslip_like, workslip_like, workslip_like, workslip_like])
    workslip_where_sql = f"WHERE {' AND '.join(workslip_where)}" if workslip_where else ""

    total_workslips = dbc.execute(
        f"SELECT COUNT(*) FROM WorkSlips {workslip_where_sql}",
        workslip_params
    ).fetchone()[0]
    workslip_total_pages = max(1, (total_workslips + per_page - 1) // per_page)
    workslip_page = min(workslip_page, workslip_total_pages)
    workslip_offset = (workslip_page - 1) * per_page

    workslips = dbc.execute(
        f"""
        SELECT WSNumber, WONumber, WSDescription, WSDockDate, OpID, hideFromUse
        FROM WorkSlips
        {workslip_where_sql}
        ORDER BY WSNumber
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        workslip_params + [workslip_offset, per_page]
    ).fetchall()

    return render_template(
        'admin/project_data.html',
        projects=projects,
        workorders=workorders,
        workslips=workslips,
        project_q=project_q,
        workorder_q=workorder_q,
        workslip_q=workslip_q,
        project_page=project_page,
        workorder_page=workorder_page,
        workslip_page=workslip_page,
        project_total_pages=project_total_pages,
        workorder_total_pages=workorder_total_pages,
        workslip_total_pages=workslip_total_pages,
        total_projects=total_projects,
        total_workorders=total_workorders,
        total_workslips=total_workslips
    )

@bp.route('/admin/export_logs', methods=['GET', 'POST'])
@login_required
def view_export_logs():
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    # Fetch distinct values for dropdowns
    empid_choices = dbc.execute(
            "SELECT DISTINCT ExportLog.EmpID, Employee.EmpName FROM ExportLog LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID ORDER BY ExportLog.EmpID"
        ).fetchall()
    status_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportStatus FROM ExportLog ORDER BY exportStatus").fetchall()]
    type_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportType FROM ExportLog ORDER BY exportType").fetchall()]
    weekstart_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportWorkWeek FROM ExportLog ORDER BY exportWorkWeek DESC").fetchall()]

    # Filtering options
    emp_id = request.args.getlist('emp_id')
    status = request.args.getlist('status')
    export_type = request.args.getlist('type')
    week_start = request.args.getlist('week_start')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Build WHERE clause dynamically
    where_clauses = []
    params = []

    if emp_id:
        where_clauses.append(f"ExportLog.EmpID IN ({','.join(['?']*len(emp_id))})")
        params.extend(emp_id)
    if status:
        where_clauses.append(f"exportStatus IN ({','.join(['?']*len(status))})")
        params.extend(status)
    if export_type:
        where_clauses.append(f"exportType IN ({','.join(['?']*len(export_type))})")
        params.extend(export_type)
    if week_start:
        where_clauses.append("exportWorkWeek = ?")
        params.append(week_start)
    if date_from:
        where_clauses.append("exportDate >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("exportDate <= ?")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    logs = dbc.execute(
    f"""
    SELECT ExportLog.exportID, ExportLog.EmpID, Employee.EmpName, ExportLog.exportDate, ExportLog.exportWorkWeek,
           ExportLog.exportStatus, ExportLog.exportType, ExportLog.exportStatusDetail, ExportLog.exportSource
    FROM ExportLog
    LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID
    {where_sql}
    ORDER BY exportDate DESC
    """,
    params
).fetchall()

    selected_export_id = request.args.get('export_id')
    details = []
    if selected_export_id:
        details = dbc.execute(
            """
            SELECT exportID, empID, workDate, timeWorked, paychexCode, workSlip, comments
            FROM ExportLogDetail
            WHERE exportID = ?
            ORDER BY workDate DESC
            """,
            (selected_export_id,)
        ).fetchall()

    return render_template(
        'admin/export_logs.html',
        logs=logs,
        details=details,
        filters={
            "emp_id": emp_id,
            "status": status,
            "type": export_type,
            "date_from": date_from,
            "date_to": date_to,
            "week_start": week_start,
            "selected_export_id": selected_export_id
        },
        empid_choices=empid_choices,
        status_choices=status_choices,
        type_choices=type_choices,
        weekstart_choices=weekstart_choices
    )

@bp.route('/admin/export_log_details/<int:export_id>')
@login_required
def export_log_details_modal(export_id):
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)
    db = get_db()
    dbc = db.cursor()
    details = dbc.execute("""
        SELECT exportID, empID, workDate, timeWorked, paychexCode, workSlip, comments
        FROM ExportLogDetail
        WHERE exportID = ?
        ORDER BY workDate
    """, (export_id,)).fetchall()
    return render_template('admin/export_log_details_modal.html', details=details)

@bp.route('/admin/usage_statistics', methods=['GET'])
@login_required
def usage_statistics():
    if not getattr(g.user, 'isAdmin', False):
        return abort(403)

    db = get_db()
    dbc = db.cursor()

    # Calculate current week start (week starts on Monday, weekday_start=0)
    from datetime import datetime, timedelta
    now = datetime.now()
    current_week_start = get_week_start(now.date(), week_start_day=0)
    previous_week_start = current_week_start - timedelta(days=7)

    # Fetch distinct values for dropdowns
    empid_choices = dbc.execute(
            "SELECT DISTINCT ExportLog.EmpID, Employee.EmpName FROM ExportLog LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID ORDER BY ExportLog.EmpID"
        ).fetchall()
    status_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportStatus FROM ExportLog ORDER BY exportStatus").fetchall()]
    type_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportType FROM ExportLog ORDER BY exportType").fetchall()]
    weekstart_choices = [row[0] for row in dbc.execute("SELECT DISTINCT exportWorkWeek FROM ExportLog ORDER BY exportWorkWeek DESC").fetchall()]

    # Filtering options
    emp_id = request.args.getlist('emp_id')
    status = request.args.getlist('status')
    export_type = request.args.getlist('type')
    week_start_param = request.args.get('week_start', 'CURRENT_WEEK')  # Default to current week
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Handle special week filter values
    week_start = week_start_param
    week_start_filter_type = 'exact'  # Can be 'exact', 'month', 'year', or None
    display_title = ""
    
    if week_start_param == 'ALL':
        week_start = None  # Don't filter by week
        display_title = "All Time"
    elif week_start_param == 'CURRENT_WEEK':
        week_start = str(current_week_start)
        week_end = current_week_start + timedelta(days=6)
        display_title = f"Current Week ({current_week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')})"
    elif week_start_param == 'PREVIOUS_WEEK':
        week_start = str(previous_week_start)
        week_end = previous_week_start + timedelta(days=6)
        display_title = f"Previous Week ({previous_week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')})"
    elif week_start_param == 'CURRENT_MONTH':
        week_start_filter_type = 'month'
        week_start = now  # Store datetime for month/year extraction
        display_title = now.strftime('%B %Y')
    elif week_start_param == 'CURRENT_YEAR':
        week_start_filter_type = 'year'
        week_start = now  # Store datetime for year extraction
        display_title = now.strftime('%Y')
    else:
        # Specific week selected
        try:
            from datetime import datetime as dt
            week_date = dt.strptime(week_start_param, '%Y-%m-%d').date()
            week_end = week_date + timedelta(days=6)
            display_title = f"Week of {week_date.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        except:
            display_title = f"Week of {week_start_param}"

    # Build WHERE clause dynamically
    where_clauses = []
    params = []

    if emp_id:
        where_clauses.append(f"ExportLog.EmpID IN ({','.join(['?']*len(emp_id))})")
        params.extend(emp_id)
    if status:
        where_clauses.append(f"exportStatus IN ({','.join(['?']*len(status))})")
        params.extend(status)
    if export_type:
        where_clauses.append(f"exportType IN ({','.join(['?']*len(export_type))})")
        params.extend(export_type)
    if week_start:
        if week_start_filter_type == 'exact':
            where_clauses.append("exportWorkWeek = ?")
            params.append(week_start)
        elif week_start_filter_type == 'month':
            where_clauses.append("MONTH(exportWorkWeek) = ? AND YEAR(exportWorkWeek) = ?")
            params.append(week_start.month)
            params.append(week_start.year)
        elif week_start_filter_type == 'year':
            where_clauses.append("YEAR(exportWorkWeek) = ?")
            params.append(week_start.year)
    if date_from:
        where_clauses.append("exportDate >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("exportDate <= ?")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get overall export statistics by type
    export_stats = dbc.execute(
        f"""
        SELECT exportType, COUNT(*) as count
        FROM ExportLog
        {where_sql}
        GROUP BY exportType
        ORDER BY exportType
        """,
        params
    ).fetchall()

    # Get unique employee counts by type
    unique_employee_stats = dbc.execute(
        f"""
        SELECT exportType, COUNT(DISTINCT EmpID) as unique_employees
        FROM ExportLog
        {where_sql}
        GROUP BY exportType
        ORDER BY exportType
        """,
        params
    ).fetchall()

    # Get export statistics by employee and type
    employee_stats = dbc.execute(
        f"""
        SELECT ExportLog.EmpID, Employee.EmpName,
               SUM(CASE WHEN exportType = 'JobTimeEntry' THEN 1 ELSE 0 END) as timesheet_count,
               SUM(CASE WHEN exportType = 'Payroll' THEN 1 ELSE 0 END) as payroll_count,
               COUNT(*) as total_count,
               SUM(CASE WHEN exportType = 'Comments' THEN 1 ELSE 0 END) as comments_count
        FROM ExportLog
        LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID
        {where_sql}
        GROUP BY ExportLog.EmpID, Employee.EmpName
        ORDER BY Employee.EmpName
        """,
        params
    ).fetchall()

    # Get export statistics by week
    weekly_stats = dbc.execute(
        f"""
        SELECT exportWorkWeek,
               SUM(CASE WHEN exportType = 'JobTimeEntry' THEN 1 ELSE 0 END) as timesheet_count,
               SUM(CASE WHEN exportType = 'Payroll' THEN 1 ELSE 0 END) as payroll_count,
               COUNT(*) as total_count,
               SUM(CASE WHEN exportType = 'Comments' THEN 1 ELSE 0 END) as comments_count
        FROM ExportLog
        {where_sql}
        GROUP BY exportWorkWeek
        ORDER BY exportWorkWeek DESC
        """,
        params
    ).fetchall()

    # Get time entry statistics - employees who submitted timesheets (distinct by week)
    timesheet_where_clauses = []
    timesheet_params = []
    
    # Add base filter for JobTimeEntry type
    timesheet_where_clauses.append("exportType = ?")
    timesheet_params.append('JobTimeEntry')
    
    if emp_id:
        timesheet_where_clauses.append(f"ExportLog.EmpID IN ({','.join(['?']*len(emp_id))})")
        timesheet_params.extend(emp_id)
    if week_start:
        if week_start_filter_type == 'exact':
            timesheet_where_clauses.append("exportWorkWeek = ?")
            timesheet_params.append(week_start)
        elif week_start_filter_type == 'month':
            timesheet_where_clauses.append("MONTH(exportWorkWeek) = ? AND YEAR(exportWorkWeek) = ?")
            timesheet_params.append(week_start.month)
            timesheet_params.append(week_start.year)
        elif week_start_filter_type == 'year':
            timesheet_where_clauses.append("YEAR(exportWorkWeek) = ?")
            timesheet_params.append(week_start.year)
    if date_from:
        timesheet_where_clauses.append("exportDate >= ?")
        timesheet_params.append(date_from)
    if date_to:
        timesheet_where_clauses.append("exportDate <= ?")
        timesheet_params.append(date_to)
    
    timesheet_where_sql = "WHERE " + " AND ".join(timesheet_where_clauses)

    timesheet_entries = dbc.execute(
        f"""
        SELECT ExportLog.EmpID, Employee.EmpName, ExportLog.exportWorkWeek, 
               COUNT(DISTINCT ExportLog.exportID) as export_count
        FROM ExportLog
        LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID
        {timesheet_where_sql}
        GROUP BY ExportLog.EmpID, Employee.EmpName, ExportLog.exportWorkWeek
        ORDER BY ExportLog.exportWorkWeek DESC, Employee.EmpName
        """,
        timesheet_params
    ).fetchall()

    # Get payroll statistics - employees who submitted payroll (distinct by week)
    payroll_where_clauses = []
    payroll_params = []
    
    # Add base filter for payroll type (case-insensitive)
    payroll_where_clauses.append("LOWER(exportType) LIKE ?")
    payroll_params.append('%payroll%')
    
    if emp_id:
        payroll_where_clauses.append(f"ExportLog.EmpID IN ({','.join(['?']*len(emp_id))})")
        payroll_params.extend(emp_id)
    if week_start:
        if week_start_filter_type == 'exact':
            payroll_where_clauses.append("exportWorkWeek = ?")
            payroll_params.append(week_start)
        elif week_start_filter_type == 'month':
            payroll_where_clauses.append("MONTH(exportWorkWeek) = ? AND YEAR(exportWorkWeek) = ?")
            payroll_params.append(week_start.month)
            payroll_params.append(week_start.year)
        elif week_start_filter_type == 'year':
            payroll_where_clauses.append("YEAR(exportWorkWeek) = ?")
            payroll_params.append(week_start.year)
    if date_from:
        payroll_where_clauses.append("exportDate >= ?")
        payroll_params.append(date_from)
    if date_to:
        payroll_where_clauses.append("exportDate <= ?")
        payroll_params.append(date_to)
    
    payroll_where_sql = "WHERE " + " AND ".join(payroll_where_clauses)

    payroll_entries = dbc.execute(
        f"""
        SELECT ExportLog.EmpID, Employee.EmpName, ExportLog.exportWorkWeek,
               COUNT(DISTINCT ExportLog.exportID) as export_count
        FROM ExportLog
        LEFT JOIN Employee ON ExportLog.EmpID = Employee.EmpID
        {payroll_where_sql}
        GROUP BY ExportLog.EmpID, Employee.EmpName, ExportLog.exportWorkWeek
        ORDER BY ExportLog.exportWorkWeek DESC, Employee.EmpName
        """,
        payroll_params
    ).fetchall()

    return render_template(
        'admin/usage_statistics.html',
        export_stats=export_stats,
        unique_employee_stats=unique_employee_stats,
        employee_stats=employee_stats,
        weekly_stats=weekly_stats,
        timesheet_entries=timesheet_entries,
        payroll_entries=payroll_entries,
        filters={
            "emp_id": emp_id,
            "status": status,
            "type": export_type,
            "date_from": date_from,
            "date_to": date_to,
            "week_start": week_start_param
        },
        empid_choices=empid_choices,
        status_choices=status_choices,
        type_choices=type_choices,
        weekstart_choices=weekstart_choices,
        current_week_start=str(current_week_start),
        display_title=display_title
    )

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