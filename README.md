# oracle2json Web server

## Script oracle2json
 This script is designed to receive data from the Oracle DBMS and output the result in json form via a web service.

The main method of interaction is GET requests to the web endpoint exposed by the script. Its perfect work with Grafana Plugin: Infinity if you need to get FREE access to your data in Oracle from Grafana.
For speed and to reduce the load on the database, caching of SQL query results is implemented.

## Example of work:
  - Request: curl http://my-server/some-sql
  - Response: [{"ACCOUNT_NAME": "My company", "BALANCE": "811.05", "REQUEST_ID": "7687"}]

## Control:
  The service is configured via the file: config.py
  The password for TUZ is set by placing the base64 hash in the environment variable: pfdwh_token
  SQL queries are configured via the file: sql.lib.json and by adding *.sql files to the sql directory.
  Start/stop: run.sh stop|start|restart|status

## Description of the file structure:
 #### MAIN:
  - run.sh - MAIN service management module. Usage: run.sh stop|start|restart|status
  - server_JSON.py - MAIN web server module.

#### CONFIG:
  - config/config.py - configuration for work.
  - config/sql.lib.json - configuration of executed SQL. Stores both the SQL themselves and links to them in the sql directory.
  
#### OTHER:  
  - cache - directory for storing the query cache
  - logs - directory with logs
  - sql - directory with a set of sql
  - service_check.sh - HA module, provides checking and restart in case of failure.
  - modules/request2oracle.py - the main module responsible for receiving data from Oracle. Separate use via the console is possible.
  - modules/tech_func.py - module with auxiliary functions


#### Base location:
  - root@host:/opt/scripts/ora2json_webserver

#### PS:
   - but you can also run the script in the console mode.
   - Please be free for questions.
