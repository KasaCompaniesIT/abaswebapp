import os, sys, time, logging
import pandas as pd
import pyodbc
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from config import DB_URL

# Configuration
log_file = 'app.log'
# 'midnight' rotates at midnight of each day, 'W0' for weekly on Monday, 'S' for every second, etc.
when = 'midnight'
# interval for 'when' (1 for daily if 'when' is 'midnight', 7 for weekly if 'when' is 'W0', etc.)
interval = 1
# Number of backup log files to keep
backup_count = 7
# Create logger
logger = logging.getLogger('Timed Rotating Log')
logger.setLevel(logging.INFO)
# Create handler for rotating log files by date
handler = TimedRotatingFileHandler(
    log_file,
    when=when,
    interval=interval,
    backupCount=backup_count,
    # Optionally, use UTC time for consistency across timezones
    # utc=True
)
# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
# Add the handler to the logger
logger.addHandler(handler)

# # Configure the logging
# log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log.txt')
# logging.basicConfig(filename=log_file_path, level=logging.INFO, 
#                     format='%(asctime)s - %(levelname)s - %(message)s')

ALLOWED_EXTENSIONS = set(['csv'])

# CSV file paths
OPS_CSV = r"\\abas\keserp\LABOR_OPS"
EMP_CSV = r"\\abas\keserp\EMPLOYEES"
LABOR_CSV = r"\\abas\keserp\LABOR_ACTCC"
PROJSTAT_CSV = r"\\abas\keserp\PROJSTATUS"

def main():
    argPath = ""

    # sys.argv is a list in Python, where sys.argv[0] is the script name itself
    if len(sys.argv) < 2:
        sys.exit(1)
    
    argument = sys.argv[1]  # First parameter after the script name
    if len(sys.argv) == 3:
        argPath = sys.argv[2]  # Second parameter after the script name
    
    logger.info(f"Usage: python abaswebapp-import.py {argument}")

    if argument.upper() == "OPS":
        importOpsCSV()

    elif argument.upper() == "EMP":
        importEmpCSV() 

    elif argument.upper() == "LABOR":
        importLaborCSV(argPath) 

    elif argument.upper() == "PRJSTAT":
        importProjStatusCSV(argPath)  
    

def get_db():
    db = pyodbc.connect(DB_URL)
    return db

def importLaborCSV(fPath):
    skippedCount = 0
    newCount = 0

    startTime = time.time()

    try:
        print("Connecting to sqlserver...")
        logger.info("Connecting to sqlserver...")

        db = get_db()
        dbc = db.cursor()
        
        print("Connected")
        logger.info("Connected")

        print("Accessing the latest Timesheet file...")
        logger.info("Accessing the latest Timesheet file...")
        
        if fPath == "":
            laborfile = get_newest_file(LABOR_CSV)
        else:
            laborfile = fPath
        
        print(f"Latest Employee file is: {laborfile}")
        logger.info(f"Latest Employee file is: {laborfile}")
        
        df = pd.read_csv(laborfile, keep_default_na=False)          
        
        print("Importing Employee Data...")
        logger.info("Importing Employee Data......Starting")
        
        for index, row in df.iterrows():
            if not existingLaborEntry(row['OBJID']):
                # insert new timesheet record
                dbc.execute(
                    "INSERT INTO TimeEntryAbas (EmpID, WorkDate, TimeWorked, WSNumber, AbasEntryID) VALUES (?, ?, ?, ?, ?)",
                    (row['EMPNUM'], row['DATE'], row['TIME'], row['WRKSLP'], row['OBJID'])
                )
                dbc.commit()
                print(f"Inserting new timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']} - {row['OBJID']}")
                logger.info(f"Inserting new timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']} - {row['OBJID']}")
                newCount += 1
            else:
                # skip dupilcate record
                print(f"Skipping duplicate timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']} - {row['OBJID']}")
                logger.info(f"Skipping duplicate timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']} - {row['OBJID']}")
                skippedCount += 1
            #     # update existing timesheet record
            #     dbc.execute(
            #         "UPDATE TimeEntryAbas SET TimeWorked=? WHERE empid=? and workdate=? and wsnumber=?",
            #         (row['TIME'], row['EMPNUM'], row['DATE'] , row['WRKSLP'])
            #     )
            #     dbc.commit()
            #     print(f"Updating timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']}")
            #     logger.info(f"Updating timesheet record: Emp: {row['EMPNUM']} Date: {row['DATE']} WS: {row['WRKSLP']}")
            #     updateCount += 1

        currentTime = time.time()
        elapsedSeconds = currentTime - startTime
        print(f"Importing Timesheet Data......Finished in {elapsedSeconds:.2f} seconds")
        logger.info(f"Importing Timesheet Data......Finished in {elapsedSeconds:.2f} seconds")
        print(f"{newCount} new timesheet records.  {skippedCount} duplicate timesheet records skipped.")
        logger.info(f"{newCount} new timesheet records.  {skippedCount} duplicate timesheet records skipped.")
        print(f"Import Complete for {laborfile}.")
        logger.info(f"Import Complete for {laborfile}.")
        return True
    except IOError:
        print(IOError)
        logger.error(IOError)
        pass         
    except pyodbc.DatabaseError as err:
            error = err
            print("Importing Timesheet Data......Incomplete")
            logger.info("Importing Timesheet Data......Incomplete")
            print(error)
            logger.error(error)
            print(f"{newCount} new timesheet records.  {skippedCount} duplicate timesheet records skipped.")
            logger.info(f"{newCount} new timesheet records.  {skippedCount} duplicate timesheet records skipped.")
            print(f"Import Error for {laborfile}.")
            logger.error(f"Import Error for {laborfile}.")
            return str(error)


def importProjStatusCSV(fPath):
    updateCount = 0

    startTime = time.time()

    try:
        print("Connecting to sqlserver...")
        logger.info("Connecting to sqlserver...")

        db = get_db()
        dbc = db.cursor()
        
        print("Connected")
        logger.info("Connected")

        print("Accessing the latest Project Status file...")
        logger.info("Accessing the latest Project Status file...")
        
        if fPath ==  "":
            projstatfile = get_newest_file(PROJSTAT_CSV)
        else:
            projstatfile = fPath
        
        print(f"Latest Project Status file is: {projstatfile}")
        logger.info(f"Latest Project Status file is: {projstatfile}")
        
        df = pd.read_csv(projstatfile, keep_default_na=False)          
        
        print("Importing Project Status Data...")
        logger.info("Importing Project Status Data......Starting")
        
        for index, row in df.iterrows():
            if row['SUCH'].startswith("P"):
                projectID = row['SUCH'].replace("P", "")
                if existingProject(projectID):                
                    # update project status record
                    if (row['COMPLETE'] == 'Yes'):                
                        dbc.execute(
                            "UPDATE Projects SET ProjectComplete=?, ProjectCompleteDate=? WHERE ProjectID=?",
                            (True, row['MODIFIED'], projectID)
                        )
                        dbc.commit()

                        print(f"Updating project complete record: {projectID}")
                        logger.info(f"Updating project complete record: {projectID}")
                        updateCount += 1

                    if (row['CLOSED'] == 'Yes'):                
                        dbc.execute(
                            "UPDATE Projects SET ProjectClosed=?, ProjectClosedDate=? WHERE ProjectID=?",
                            (True, row['MODIFIED'], projectID)
                        )
                        dbc.commit()
                        
                        print(f"Updating project closed record: {projectID}")
                        logger.info(f"Updating project closed record: {projectID}")
                        updateCount += 1

        currentTime = time.time()
        elapsedSeconds = currentTime - startTime
        print(f"Importing Project Status Data......Finished in {elapsedSeconds:.2f} seconds")
        logger.info(f"Importing Project Status Data......Finished in {elapsedSeconds:.2f} seconds")
        print(f"{updateCount} updated project status records.")
        logger.info(f"{updateCount} updated project status records.")
        print(f"Import Complete for {projstatfile}.")
        logger.info(f"Import Complete for {projstatfile}.")
        return True
    except IOError:
        print(IOError)
        logger.error(IOError)
        pass         
    except pyodbc.DatabaseError as err:
            error = err
            print("Importing Project Status Data......Incomplete")
            logger.info("Importing Project Status Data......Incomplete")
            print(error)
            logger.error(error)
            print(f"{updateCount} updated project status records.")
            logger.info(f"{updateCount} updated project status records.")
            print(f"Import Error for {projstatfile}.")
            logger.error(f"Import Error for {projstatfile}.")
            return str(error)

def importEmpCSV():          
    updateCount = 0
    newCount = 0

    startTime = time.time()

    try:
        print("Connecting to sqlserver...")
        logger.info("Connecting to sqlserver...")

        db = get_db()
        dbc = db.cursor()
        
        print("Connected")
        logger.info("Connected")

        print("Accessing the latest Employee file...")
        logger.info("Accessing the latest Employee file...")
        
        empfile = get_newest_file(EMP_CSV)
        
        print(f"Latest Employee file is: {empfile}")
        logger.info(f"Latest Employee file is: {empfile}")
        
        df = pd.read_csv(empfile, keep_default_na=False)          
        
        print("Importing Employee Data...")
        logger.info("Importing Employee Data......Starting")
        
        for index, row in df.iterrows():
            if not existingEmployee(row['ID']):
                # insert new employee record
                dbc.execute(
                    "INSERT INTO Employee (EmpID, Emp, EmpName, Dept, Supervisor, Wagegroup) VALUES (?, ?, ?, ?, ?, ?)",
                    (row['ID'], row['EMP'], row['NAME'], row['DEPT'], row['SUPERVISOR'], row['WG'])
                )
                dbc.commit()
                print(f"Inserting new employee record: {row['EMP']}")
                logger.info(f"Inserting new employee record: {row['EMP']}")
                newCount += 1
            else:
                # update existing employee record
                dbc.execute(
                    "UPDATE Employee SET Emp=?, EmpName=?, Dept=?, Supervisor=?, Wagegroup=? WHERE empid=?",
                    (row['EMP'], row['NAME'], row['DEPT'], row['SUPERVISOR'], row['WG'], row['ID'])
                )
                dbc.commit()
                print(f"Updating employee record: {row['EMP']}")
                logger.info(f"Updating employee record: {row['EMP']}")
                updateCount += 1

        currentTime = time.time()
        elapsedSeconds = currentTime - startTime
        print(f"Importing Employee Data......Finished in {elapsedSeconds:.2f} seconds")
        logger.info(f"Importing Employee Data......Finished in {elapsedSeconds:.2f} seconds")
        print(f"{newCount} new employee records.  {updateCount} updated employee records.")
        logger.info(f"{newCount} new employee records.  {updateCount} updated employee records.")
        return True
    except IOError:
        print(IOError)
        logger.error(IOError)
        pass         
    except pyodbc.DatabaseError as err:
            error = err
            print("Importing Employee Data......Incomplete")
            logger.info("Importing Employee Data......Incomplete")
            print(error)
            logger.error(error)
            print(f"{newCount} new employee records.  {updateCount} updated employee records.")
            logger.info(f"{newCount} new employee records.  {updateCount} updated employee records.")
            return str(error)

def importOpsCSV():           
    updateProjectCount = 0
    newProjectCount = 0

    updateWOCount = 0
    newWOCount = 0

    updateWSCount = 0
    newWSCount = 0

    startTime = time.time()

    try:
        print("Connecting to sqlserver...")
        logger.info("Connecting to sqlserver...")
        
        db = get_db()
        dbc = db.cursor()
        
        print("Connected")
        logger.info("Connected")

        print("Accessing the latest Labor Ops file...")
        logger.info("Accessing the latest Labor Ops file...")
        
        opsfile = get_newest_file(OPS_CSV)
        
        print(f"Latest Labor Ops file is: {opsfile}")
        logger.info(f"Latest Labor Ops file is: {opsfile}")

        df = pd.read_csv(opsfile, keep_default_na=False)        
        
        print("Importing Labor Ops Data...")
        logger.info("Importing Labor Ops Data......Starting")
        
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
                    logger.info(f"Inserting new project record: {row['project']}")
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
                    logger.info(f"Updating project record: {row['project']}")
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
                    logger.info(f"Inserting new workorder record: {row['wo']}")
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
                    logger.info(f"Updating workorder record: {row['wo']}")
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
                    logger.info(f"Inserting new workslip record: {row['wrkslp']}")
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
                    logger.info(f"Updating workslip record: {row['wrkslp']}")
                    updateWSCount += 1
                    currentWS = workslipID
        
        currentTime = time.time()
        elapsedSeconds = currentTime - startTime
        print(f"Importing Labor Ops Data......Finished in {elapsedSeconds:.2f} seconds")
        logger.info(f"Importing Labor Ops Data......Finished in {elapsedSeconds:.2f} seconds")
        print(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
        logger.info(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
        print(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")
        logger.info(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")
        print(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")
        logger.info(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")

        return True
    except IOError:
        print(IOError)
        logger.error(IOError)
        pass         
    except pyodbc.DatabaseError as err:
            error = err
            print("Importing Labor Ops Data......Incomplete")
            logger.info("Importing Labor Ops Data......Incomplete")
            print(error)
            logger.error(error)
            print(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
            logger.info(f"{newProjectCount} new project records.  {updateProjectCount} updated project records.")
            print(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")
            logger.info(f"{newWOCount} new workorder records.  {updateWOCount} updated workorder records.")
            print(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")
            logger.info(f"{newWSCount} new workslip records.  {updateWSCount} updated workslip records.")
            return str(error)

def existingLaborEntry(objid):
    db = get_db()
    dbc = db.cursor()
    row  = dbc.execute(f"select * from TimeEntryAbas where abasentryid = '{objid}'").fetchone()
    if row:
        return True
    else:
        return False

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

def get_newest_file(network_path):
    # Convert the path to a Path object for easier manipulation
    share_path = Path(network_path)
    
    # Check if the path exists
    if not share_path.exists():
        raise FileNotFoundError(f"The path {network_path} does not exist.")
    # List all files in the directory, sorting by modification time
    # Here we use reverse=True to get the latest file first
    files = sorted(share_path.glob('*'), key=os.path.getmtime, reverse=True)
    
    # If there are no files, return None
    if not files:
        return None
    
    # Return the newest file
    return files[0]

if __name__ == "__main__":
    main()

