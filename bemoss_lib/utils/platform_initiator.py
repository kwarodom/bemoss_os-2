# -*- coding: utf-8 -*-
'''
Copyright (c) 2016, Virginia Tech
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
 following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the authors and should not be
interpreted as representing official policies, either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the United States Government. Neither the
United States Government nor the United States Department of Energy, nor Virginia Tech, nor any of their employees,
nor any jurisdiction or organization that has cooperated in the development of these materials, makes any warranty,
express or implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or represents that its use would not infringe
privately owned rights.

Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer, or
otherwise does not necessarily constitute or imply its endorsement, recommendation, favoring by the United States
Government or any agency thereof, or Virginia Tech - Advanced Research Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the United States Government or any agency thereof.

VIRGINIA TECH – ADVANCED RESEARCH INSTITUTE
under Contract DE-EE0006352

#__author__ = "BEMOSS Team"
#__credits__ = ""
#__version__ = "2.0"
#__maintainer__ = "BEMOSS Team"
#__email__ = "aribemoss@gmail.com"
#__website__ = "www.bemoss.org"
#__created__ = "2014-09-12 12:04:50"
#__lastUpdated__ = "2016-03-14 11:23:33"
'''

import os
import sys
import json
os.chdir(os.path.expanduser("~/workspace/bemoss_os/"))  # = ~/workspace/bemoss_os
os.system("service postgresql restart")
current_working_directory = os.getcwd()
sys.path.append(current_working_directory)
import settings
import psycopg2
import datetime
# CONFIGURATION ---------------------------------------------------------------------------------------------
#@params agent
agent_id = 'PlatformInitiator'

# @params DB interfaces
db_database = settings.DATABASES['default']['NAME']
db_host = settings.DATABASES['default']['HOST']
db_port = settings.DATABASES['default']['PORT']
db_user = settings.DATABASES['default']['USER']
db_password = settings.DATABASES['default']['PASSWORD']
db_table_building_zone = settings.DATABASES['default']['TABLE_building_zone']
db_table_global_zone_setting = settings.DATABASES['default']['TABLE_global_zone_setting']
db_table_holiday = settings.DATABASES['default']['TABLE_holiday']
db_table_device_info = settings.DATABASES['default']['TABLE_device_info']
db_table_device_model = settings.DATABASES['default']['TABLE_device_model']
db_table_application_running = settings.DATABASES['default']['TABLE_application_running']
db_table_application_registered = settings.DATABASES['default']['TABLE_application_registered']
db_table_plugload = settings.DATABASES['default']['TABLE_plugload']
db_table_thermostat = settings.DATABASES['default']['TABLE_thermostat']
db_table_lighting = settings.DATABASES['default']['TABLE_lighting']
db_table_device_metadata = settings.DATABASES['default']['TABLE_device_metadata']
db_table_vav = settings.DATABASES['default']['TABLE_vav']
db_table_rtu = settings.DATABASES['default']['TABLE_rtu']
db_table_alerts_notificationchanneladdress = settings.DATABASES['default'][
        'TABLE_alerts_notificationchanneladdress']
db_table_active_alert = settings.DATABASES['default']['TABLE_active_alert']
db_table_temp_time_counter = settings.DATABASES['default']['TABLE_temp_time_counter']
db_table_seen_notifications_counter = settings.DATABASES['default']['TABLE_seen_notifications_counter']
db_table_bemoss_notify = settings.DATABASES['default']['TABLE_bemoss_notify']
db_table_node_info = settings.DATABASES['default']['TABLE_node_info']

PROJECT_DIR = settings.PROJECT_DIR
Agents_Launch_DIR = settings.Agents_Launch_DIR
Loaded_Agents_DIR = settings.Loaded_Agents_DIR

# Autostart_Agents_DIR = settings.Autostart_Agents_DIR
Applications_Launch_DIR = settings.Applications_Launch_DIR
#----------------------------------------------------------------------------------------------------------
os.system("clear")
#1. Connect to bemossdb database
conn = psycopg2.connect(host=db_host, port=db_port, database=db_database,
                            user=db_user, password=db_password)
cur = conn.cursor()  # open a cursor to perform database operations
print "{} >> Done 1: connect to database name {}".format(agent_id, db_database)

#2. clean tables
cur.execute("DELETE FROM "+db_table_thermostat)
cur.execute("DELETE FROM "+db_table_lighting)
cur.execute("DELETE FROM "+db_table_plugload)
cur.execute("DELETE FROM "+db_table_vav)
cur.execute("DELETE FROM "+db_table_rtu)
cur.execute("DELETE FROM "+db_table_device_info)
cur.execute("DELETE FROM "+db_table_global_zone_setting)
cur.execute("DELETE FROM "+db_table_node_info)
cur.execute("DELETE FROM "+db_table_building_zone)
conn.commit()


cur.execute("select * from information_schema.tables where table_name=%s", (db_table_alerts_notificationchanneladdress,))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_alerts_notificationchanneladdress)
    conn.commit()
else:
    pass

cur.execute("select * from information_schema.tables where table_name=%s", (db_table_active_alert,))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_active_alert)
    conn.commit()
else:
    pass


cur.execute("select * from information_schema.tables where table_name=%s", (db_table_seen_notifications_counter,))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_seen_notifications_counter)
    conn.commit()
else:
    pass

cur.execute("select * from information_schema.tables where table_name=%s", (db_table_bemoss_notify,))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_bemoss_notify)
    conn.commit()
else:
    pass

cur.execute("select * from information_schema.tables where table_name=%s", (db_table_temp_time_counter,))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_temp_time_counter)
    conn.commit()
else:
    pass

cur.execute("select * from information_schema.tables where table_name=%s", ('holiday',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM "+db_table_holiday)
    conn.commit()
else:
    pass


#3. adding holidays ref www.archieves.gov/news/federal-holidays.html
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (1, datetime.datetime(2014, 01, 01).date(), "New Year's Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (2, datetime.datetime(2014, 1, 20).date(), "Birthday of Martin Luther King Jr."))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (3, datetime.datetime(2014, 2, 17).date(), "Washington's Birthday"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (4, datetime.datetime(2014, 5, 26).date(), "Memorial Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (5, datetime.datetime(2014, 7, 4).date(), "Independence Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (6, datetime.datetime(2014, 9, 1).date(), "Labor Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (7, datetime.datetime(2014, 10, 13).date(), "Columbus Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (8, datetime.datetime(2014, 11, 11).date(), "Veterans Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (9, datetime.datetime(2014, 11, 27).date(), "Thanksgiving Day"))
cur.execute("INSERT INTO "+db_table_holiday+" VALUES(%s,%s,%s)",
            (10, datetime.datetime(2014, 12, 25).date(), "Christmas Day"))
conn.commit()
print "{} >> Done 3: added holidays to {}".format(agent_id, db_table_holiday)

#. Initialize the seen notification counter
cur.execute("INSERT INTO "+db_table_seen_notifications_counter+" VALUES(%s,%s)",
            (1, '0'))
conn.commit()


#4. clear all previous agent launch files
loaded_agents = os.listdir(Loaded_Agents_DIR)
if len(loaded_agents) != 0:
    os.system("rm -rf "+Loaded_Agents_DIR+"*.json")
    print "{} >> Done 4: agent launch files are removed from {}".format(agent_id, Loaded_Agents_DIR)
else:
    pass

agent_launch_files = os.listdir(Agents_Launch_DIR)
if len(agent_launch_files) != 0:
    os.system("rm "+Agents_Launch_DIR+"*.json")
    print "{} >> Done 6: agent launch files are removed from {}".format(agent_id, Agents_Launch_DIR)
else:
    pass

#7. check and confirm zone id:999 (unassigned for newly discovered devices) is in table
cur.execute("SELECT zone_id FROM "+db_table_building_zone+" WHERE zone_id=999")
if cur.rowcount == 0:
    cur.execute("INSERT INTO "+db_table_building_zone+" VALUES(%s, %s)", (999, "BEMOSS Core"))
    conn.commit()
    print "{} >> Done 7: default columns zone_id 999 and zone_nickname BEMOSS Core " \
          "is inserted into {} successfully".format(agent_id, db_table_building_zone)
else:
    print "{} >> Warning: default zone 999 already exists".format(agent_id)

#7. check and confirm zone id:999 (BEMOSS Core for newly discovered devices) is in table
cur.execute("SELECT id FROM "+db_table_global_zone_setting+" WHERE zone_id=%s", (999,))
if cur.rowcount == 0:  # this APP used to be launched before
    cur.execute("INSERT INTO "+db_table_global_zone_setting+"(id, zone_id, heat_setpoint, cool_setpoint, illuminance)"
                                                            " VALUES(%s,%s,%s,%s,%s)", (999,999,70,78,80,))
    conn.commit()

#8. create tables
cur.execute("select * from information_schema.tables where table_name=%s", ('application_running',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DROP TABLE application_running")
    conn.commit()
else:
    pass

cur.execute('''CREATE TABLE application_running
       (APPLICATION_ID SERIAL   PRIMARY KEY   NOT NULL,
       APP_AGENT_ID   VARCHAR(50)   NOT NULL,
       START_TIME     TIMESTAMP,
       STATUS        VARCHAR(10),
       APP_SETTING   VARCHAR(200));''')
print "Table application_running created successfully"
conn.commit()

cur.execute("select * from information_schema.tables where table_name=%s", ('application_registered',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DROP TABLE application_registered")
    conn.commit()
else:
    pass

cur.execute('''CREATE TABLE application_registered
       (APPLICATION_ID SERIAL   PRIMARY KEY   NOT NULL,
       APP_NAME VARCHAR (30) NOT NULL,
       EXECUTABLE VARCHAR (35) NOT NULL,
       AUTH_TOKEN VARCHAR (20) NOT NULL,
       APP_USER TEXT,
       DESCRIPTION  VARCHAR (200) NOT NULL,
       REGISTERED_TIME  TIMESTAMP  NOT NULL,
       LAST_UPDATED_TIME  TIMESTAMP NOT NULL);''')
print "Table application_registered created successfully"
conn.commit()

cur.execute("select * from information_schema.tables where table_name=%s", ('passwords_manager',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    print "table already exits. Clearing"
    cur.execute("DELETE FROM passwords_manager")
    conn.commit()

cur.execute("select * from information_schema.tables where table_name=%s", ('supported_devices',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    print "table already exits. Dropping"
    cur.execute("DELETE FROM supported_devices")
    conn.commit()
else:
    cur.execute('''CREATE TABLE supported_devices
           (DEVICE_MODEL VARCHAR(30) PRIMARY KEY   NOT NULL,
           VENDOR_NAME  VARCHAR(50),
           COMMUNICATION VARCHAR(10),
           DEVICE_TYPE VARCHAR(20),
           DISCOVERY_TYPE VARCHAR(20),
           DEVICE_MODEL_ID  VARCHAR(5),
           API_NAME VARCHAR(50),
           IDENTIFIABLE BOOLEAN);''')
    print "Table supported_devices created successfully"
    conn.commit()

cur.execute("select * from information_schema.tables where table_name=%s", ('node_device',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM node_device")
    conn.commit()
else:
    pass

    cur.execute('''CREATE TABLE node_device
           (TRANS_NO SERIAL PRIMARY KEY   NOT NULL,
           DEVICE_ID  VARCHAR(50),
           PREVIOUS_ZONE_ID INT,
           CURRENT_ZONE_ID INT,
           DATE_MOVE TIMESTAMP);''')
    print "Table node_device created successfully"
conn.commit()

cur.execute("select * from information_schema.tables where table_name=%s", ('notification_event',))
print bool(cur.rowcount)
if bool(cur.rowcount):
    cur.execute("DELETE FROM notification_event")
    conn.commit()
else:
    pass
    cur.execute('''CREATE TABLE notification_event
           (EVENT_ID SERIAL PRIMARY KEY   NOT NULL,
           EVENT_NAME  VARCHAR(30) NOT NULL,
           NOTIFY_DEVICE_ID  VARCHAR(50) NOT NULL,
           TRIGGERED_PARAMETER VARCHAR(20) NOT NULL,
           COMPARATOR VARCHAR(10) NOT NULL,
           THRESHOLD VARCHAR(10) NOT NULL,
           NOTIFY_CHANNEL VARCHAR(20) NOT NULL,
           NOTIFY_ADDRESS VARCHAR(30),
           NOTIFY_HEARTBEAT INT,
           DATE_ADDED TIMESTAMP,
           LAST_UPDATED TIMESTAMP);''')
    print "Table notification_event created successfully"
conn.commit()


cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("CT30 V1.94","RadioThermostat","WiFi","thermostat","thermostat","1TH","classAPI_RadioThermostat",True,False,4,4,False))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("CT50 V1.94","RadioThermostat","WiFi","thermostat","thermostat","1TH","classAPI_RadioThermostat",True,False,4,4,False))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Socket","Belkin International Inc.","WiFi","plugload","WeMo","3WSP","classAPI_WeMo",True,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("LightSwitch","Belkin International Inc.","WiFi","lighting","WeMo","2WL","classAPI_WeMo",True,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Philips hue bridge 2012","Royal Philips Electronics","WiFi","lighting","Philips","2HUE","classAPI_PhilipsHue",True,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("LMRC-212","WattStopper","BACnet","lighting","WattStopper","2WSL","classAPI_BACnet_WattStopper",True,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("LMPL-201","WattStopper","BACnet","plugload","WattStopper","3WP","classAPI_BACnet_WattStopper",True,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("VC1000","Prolon","Modbus","vav","Prolon_VAV","1VAV","classAPI_vav_rtu",False,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("M1000","Prolon","Modbus","rtu","Prolon_RTU","1RTU","classAPI_vav_rtu",False,False,4,4,True))
cur.execute("INSERT INTO supported_devices VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Insight","Belkin International Inc.","WiFi","plugload","WeMo","3WIS","classAPI_WeMo",True,False,4,4,True))
conn.commit()

print "Table supported_devices populated successfully!"

#8. close database connection
try:
    if conn:
        conn.close()
        print "{} >> Done 8: database {} connection is closed".format(agent_id, db_database)
except:
    print "{} >> database {} connection has already closed".format(agent_id, db_database)

#9. clear volttron log file, kill volttron process, kill all BEMOSS processes
os.system("sudo chmod 777 -R ~/workspace/bemoss_os")

#TODO make a backup of log files
os.system("sudo rm ~/workspace/bemoss_os/log/volttron.log")
os.system("sudo rm ~/workspace/bemoss_os/log/cassandra.log")

os.system("sudo killall volttron")
os.system("sudo kill $(cat ~/workspace/bemoss_os/.temp/BEMOSS.pid)")
os.system("sudo rm ~/workspace/bemoss_os/.temp/BEMOSS.pid")
print "{} >> Done 9: clear volttron log file, kill volttron process, kill all " \
      "BEMOSS processes".format(agent_id)

