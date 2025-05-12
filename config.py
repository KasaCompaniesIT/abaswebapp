import os

# Determine the environment (default to 'development')
ENV = os.getenv('ENV', 'development')

# Use Microsoft ODBC Driver for SQL Server in all environments
DB_URL = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=kasa-sql.kasa.kasacontrols.com;DATABASE=keserp;UID=abas_webapp;PWD=Autograph-Filtrate8-Fester-Synopsis;Encrypt=no;'

ABAS_SERVER = r"\\abas.kasa.kasacontrols.com\kesdemo\LABOR_IMPORT\\"