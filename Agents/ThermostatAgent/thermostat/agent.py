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

import sys
import json
import importlib
import logging
import os
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
import datetime
from bemoss_lib.communication.Email import EmailService
from bemoss_lib.communication.sms import SMSService
import psycopg2
import psycopg2.extras
import settings
import socket
from bemoss_lib.databases.cassandraAPI import cassandraDB
from bemoss_lib.utils.catcherror import catcherror

utils.setup_logging()
_log = logging.getLogger(__name__)

# Step1: Agent Initialization
def ThermostatAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            kwargs.pop(name)
        except KeyError:
            return config.get(name, '')

    # 1. @params agent
    agent_id = get_config('agent_id')
    device_monitor_time = get_config('device_monitor_time')
    max_monitor_time = int(settings.DEVICES['max_monitor_time'])
    debug_agent = False
    log_variables = dict(temperature='double', thermostat_mode='text', battery='double',fan_mode='text', heat_setpoint='double',
                           cool_setpoint='double', thermostat_state='text', fan_state='text', hold='int',offline_count='int')

    # 2. @params device_info
    building_name = get_config('building_name')
    zone_id = get_config('zone_id')
    model = get_config('model')
    device_type = get_config('type')
    address = get_config('address')
    macaddress = get_config('macaddress')
    _address = address
    _address = _address.replace('http://', '')
    _address = _address.replace('https://', '')
    try:  # validate whether or not address is an ip address
        socket.inet_pton(socket.AF_INET, _address)
        ip_address = _address
    except socket.error:
        ip_address = None
    identifiable = get_config('identifiable')

    # 3. @params agent & DB interfaces
    db_host = get_config('db_host')
    db_port = get_config('db_port')
    db_database = get_config('db_database')
    db_user = get_config('db_user')
    db_password = get_config('db_password')
    db_table_thermostat = settings.DATABASES['default']['TABLE_thermostat']
    db_id_column_name = "thermostat_id"
    db_table_bemoss_notify = settings.DATABASES['default']['TABLE_bemoss_notify']
    db_table_active_alert = settings.DATABASES['default']['TABLE_active_alert']
    db_table_device_type = settings.DATABASES['default']['TABLE_device_type']
    db_table_alerts_notificationchanneladdress = settings.DATABASES['default']['TABLE_alerts_notificationchanneladdress']
    db_table_temp_time_counter = settings.DATABASES['default']['TABLE_temp_time_counter']
    db_table_temp_failure_time = settings.DATABASES['default']['TABLE_temp_failure_time']
    db_table_priority = settings.DATABASES['default']['TABLE_priority']

    #construct _topic_Agent_UI based on data obtained from DB
    _topic_Agent_UI_tail = building_name + '/' + str(zone_id) + '/' + agent_id

    app_name = "thermostat_scheduler"
    topic_ui_app = '/ui/app/' + app_name + '/' + agent_id + '/' + 'update'  # TODO revise app

    # 4. @params device_api
    api = get_config('api')
    apiLib = importlib.import_module("DeviceAPI.classAPI." + api)

    # 4.1 initialize thermostat device object
    Thermostat = apiLib.API(model=model, device_type=device_type, api=api, address=address,macaddress = macaddress,
                            agent_id=agent_id, db_host=db_host, db_port=db_port, db_user=db_user, db_password=db_password,
                            db_database=db_database, config_path=config_path)
    connection_renew_interval = Thermostat.variables['connection_renew_interval']

    print("{0}agent is initialized for {1} using API={2} at {3}".format(agent_id, Thermostat.get_variable('model'),
                                                                        Thermostat.get_variable('api'),
                                                                        Thermostat.get_variable('address')))

    # 5. @params notification_info
    send_notification = False
    email_fromaddr = settings.NOTIFICATION['email']['fromaddr']
    email_recipients = settings.NOTIFICATION['email']['recipients']
    email_username = settings.NOTIFICATION['email']['username']
    email_password = settings.NOTIFICATION['email']['password']
    email_mailServer = settings.NOTIFICATION['email']['mailServer']
    notify_heartbeat = settings.NOTIFICATION['heartbeat']

    class Agent(PublishMixin, BaseAgent):

        # 1. agent initialization
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            # 1. initialize all agent variables
            self.variables = kwargs
            self.valid_data = False
            self._keep_alive = True
            self.first_time_update = True
            self.ip_address = ip_address if ip_address != None else None
            self.flag = 1
            self.authorized_thermostat_mode = None
            self.authorized_fan_mode = None
            self.authorized_heat_setpoint = None
            self.authorized_cool_setpoint = None
            self.authorized_scheduleData = list()
            self.device_supports_schedule = False
            if hasattr(Thermostat, 'getDeviceSchedule'):
                self.device_supports_schedule = True
            self.authorized_active_schedule = []
            self.time_sent_notifications_device_tampering = datetime.datetime.now()
            self.first_time_detect_device_tampering = True
            self.event_ids = list()
            self.time_sent_notifications = {}
            self.notify_heartbeat = notify_heartbeat
            self.changed_variables = None
            self.lastUpdateTime = datetime.datetime.now()
            self.runningSeconds = 0
            self._override = True
            self.get_sch_day = datetime.datetime.now().day
            self.already_offline = False
            # Get the schedule from device for the first time.
            try:
                Thermostat.getDeviceSchedule()
            except:
                print('Failure @ thermostatagent init getDeviceSchedule.')
            # 2. setup connection with db -> Connect to bemossdb database
            try:
                self.con = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user,
                                            password=db_password)
                self.cur = self.con.cursor()  # open a cursor to perform database operations
                print("{} connects to the database name {} successfully".format(agent_id, db_database))
            except:
                print("ERROR: {} fails to connect to the database name {}".format(agent_id, db_database))
            # 3. send notification to notify building admin
            self.send_notification = send_notification
            self.subject = 'Message from ' + agent_id

        # These set and get methods allow scalability
        def set_variable(self, k, v):  # k=key, v=value
            self.variables[k] = v

        def get_variable(self, k):
            return self.variables.get(k, None)  # default of get_variable is none

        # 2. agent setup method
        def setup(self):
            super(Agent, self).setup()
            # 1. Do a one time push when we start up so we don't have to wait for the periodic
            self.timer(1, self.deviceMonitorBehavior)
            if identifiable == "True": Thermostat.identifyDevice()
            try:
                self.cur.execute("SELECT override FROM " + db_table_thermostat + " WHERE thermostat_id=%s", (agent_id,))
                override_status = self.cur.fetchone()[0]
                if override_status is None:
                    # update initial value of override column of a thermostat to True
                    self._override = True
                    self.cur.execute("UPDATE " + db_table_thermostat + " SET override=%s WHERE thermostat_id=%s",
                                     (self._override, agent_id))
                    self.con.commit()
                else:
                    self._override = override_status
            except:
                print "{} >> cannot update override column of thermostat".format(agent_id)

        @matching.match_exact(topic_ui_app)
        def updateScheduleMsgFromUI(self, topic, headers, message, match):
            _data = json.loads(message[0])
            schedule = json.loads(_data['content'])
            if self.device_supports_schedule:
                self.updateScheduleToDevice(schedule=schedule)

        def updateScheduleToDevice(self,schedule=None):

            _time_receive_update_from_ui = datetime.datetime.now()
            print "Agent {} Speaking:  >> got new update from UI at {}".format(agent_id,
                                                                               _time_receive_update_from_ui)
            try:
                # 1. get schedule from UI
                _new_schedule_object = schedule

                # set self.current_schedule_object to be the new schedule
                self.current_schedule_object = _new_schedule_object['thermostat']
                weeklySchedule = self.current_schedule_object[agent_id]['schedulers']['everyday']

                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                newSchedule = dict()
                for day in days:
                    newSchedule[day] = [
                        [x['nickname'], int(x['at']), int(float(x['cool_setpoint'])), int(float(x['heat_setpoint']))]
                        for x in weeklySchedule[day]]

                newSchedule['Enabled'] = 'everyday' in self.current_schedule_object[agent_id]['active']

                self.authorized_scheduleData = newSchedule
                self.set_variable('scheduleData', newSchedule)
                Thermostat.setDeviceSchedule(newSchedule)
                # 3. get currently active schedule

            except Exception as er:
                print "Update Schedule to device failed"
                print er

        def updateScheduleFromDevice(self):

            Thermostat.getDeviceSchedule()
            scheduleData = Thermostat.get_variable('scheduleData')
            _file_name = os.path.expanduser(
                '~/workspace/bemoss_web_ui/') + 'resources/scheduler_data/thermostat/' + agent_id + '_schedule.json'
            scheduleData = Thermostat.get_variable('scheduleData')
            node_file_name = os.path.expanduser(
                '~/workspace/bemoss_web_ui/') + '.temp/' + agent_id + '_schedule.json'

            if scheduleData is None or len(scheduleData) == 0:
                raise ValueError("Scheduledata is empty")

            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            index = 0
            everyday = dict()
            for day in days:
                everyday[day] = list()
                id = 0
                for entry in scheduleData[day]:
                    everyday[day].append(dict(
                        {"at": str(entry[1]), "id": str(id), "nickname": entry[0], "cool_setpoint": str(entry[2]),
                         "heat_setpoint": str(entry[3])}))
                    id += 1

            if os.path.isfile(_file_name):
                # file already exists
                _launch_file = _file_name
                try:
                    with open(_launch_file) as json_data:
                        _old_schedule_object = json.load(json_data)
                except Exception as er:
                    print er, "opening old file failed. Going to override"

                old_active = _old_schedule_object['thermostat'][agent_id]['active']
                if scheduleData['Enabled'] == False:
                    if 'everyday' in old_active:
                        _old_schedule_object['thermostat'][agent_id]['active'].remove('everyday')
                else:
                    if 'everyday' not in old_active:
                        _old_schedule_object['thermostat'][agent_id]['active'].append('everyday')

                _old_schedule_object['thermostat'][agent_id]['schedulers']['everyday'] = everyday
                _json_data = _old_schedule_object
            else:
                active_schedule = ['everyday'] if scheduleData['Enabled'] else []

                _json_data = {"thermostat": {
                    agent_id: {
                        "active": active_schedule,
                        "inactive": [],
                        "schedulers": {"everyday": everyday}
                    }}}

            try:
                with open(_file_name, 'w') as _new_file:
                    json.dump(_json_data, _new_file, sort_keys=True, indent=4, ensure_ascii=False)
                with open(node_file_name,'w') as f:
                    json.dump(_json_data, f, sort_keys=True, indent=4, ensure_ascii=False)
            except Exception as er:
                print "error writing to schedule files"

            if settings.PLATFORM['node']['type'] == "node":
                topic = '/agent/networkagent/file_to_core'
                headers = {
                    'AgentID': 'approvalagent',
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                    }

                message = json.dumps({'source_path':node_file_name,'destination_path':_file_name})
                self.publish(topic,headers,message)

        @periodic(connection_renew_interval)
        def renewConnection(self):
            Thermostat.renewConnection()

        @periodic(max_monitor_time)  # save all data every max_monitor_time
        def backupSaveData(self):
            try:
                Thermostat.getDeviceStatus()
                cassandraDB.insert(agent_id, Thermostat.variables, log_variables)
                print('Data Pushed to cassandra')
            except Exception as er:
                print("ERROR: {} fails to update cassandra database".format(agent_id))
                print er

        # 3. deviceMonitorBehavior (TickerBehavior)
        @periodic(device_monitor_time)
        def deviceMonitorBehavior(self):
            # step1: get current status of a thermostat, then map keywords and variables to agent knowledge
            try:
                Thermostat.getDeviceStatus()

                if self.device_supports_schedule:
                    # For RadioThermostat, everytime when queried with schedule information,
                    # it will automatically change the setpoint to schedule setpoint from current setpoint back and forth
                    # for several times. This makes temperory hold doesn't work. As a result, we only query RadioThermostat
                    # once a day during mid-night about the schedule on device. This behavior of RadioThermostat
                    # has been reported to the manufacturer to see if this is a device bug.
                    if 'CT30' in model or 'CT50' in model:
                        hour = datetime.datetime.now().hour
                        day = datetime.datetime.now().day
                        if hour == 2 and self.get_sch_day != day:
                            Thermostat.getDeviceSchedule()
                            self.get_sch_day = day
                            if Thermostat.get_variable('thermostat_mode') == 'HEAT':
                                setpoint = "heat_setpoint"
                                setpoint_value = Thermostat.get_variable('heat_setpoint')
                            elif Thermostat.get_variable('thermostat_mode') == 'COOL':
                                setpoint = "cool_setpoint"
                                setpoint_value = Thermostat.get_variable('cool_setpoint')
                            try:
                                Thermostat.setDeviceStatus({"thermostat_mode":Thermostat.get_variable('thermostat_mode'),setpoint:setpoint_value,"hold":Thermostat.get_variable('hold')})
                            except:
                                print('Error @ setDeviceStatus after Radiothermostat getDeviceSchedule')
                    else:
                        Thermostat.getDeviceSchedule()
                else:
                    pass

            except Exception as er:
                print er
                print("device connection is not successful")

            self.changed_variables = dict()
            try:
                self.cur.execute("SELECT override FROM " + db_table_thermostat + " WHERE thermostat_id=%s", (agent_id,))
                if self.cur.rowcount != 0:
                    self._override = self.cur.fetchone()[0]
                else:
                    pass
            except Exception as er:
                print "Error accesing override field", er

            if self.device_supports_schedule:
                if self.get_variable('scheduleData') != Thermostat.get_variable('scheduleData'):
                    self.variables['scheduleData'] = Thermostat.get_variable('scheduleData')
                    if self._override == True or self.first_time_update:
                        self.authorized_scheduleData = self.variables['scheduleData']
                        try:
                            self.updateScheduleFromDevice()
                            print "Device schedule updated from Device", agent_id
                        except Exception as er:
                            print 'Schedule Update failed'
                            print er

                    elif self._override == False:
                        print "Device Schedule Change detected."
                        self.device_tampering_detection()
                        pass  # device tampering will take care to set it back.

            for v in log_variables:
                if v in Thermostat.variables:
                    if v not in self.variables or self.variables[v] != Thermostat.variables[v]:
                        self.variables[v] = Thermostat.variables[v]
                        self.changed_variables[v] = log_variables[v]
                else:
                    if v not in self.variables:  # it won't be in self.variables either (in the first time)
                        self.changed_variables[v] = log_variables[v]
                        self.variables[v] = None
            try:
                #make the device offline if necessary
                if self.get_variable('offline_count')>=3:

                    self.cur.execute("UPDATE "+db_table_thermostat+" SET network_status=%s WHERE thermostat_id=%s",
                                     ('OFFLINE', agent_id))
                    self.con.commit()
                    if self.already_offline is False:
                        self.already_offline = True
                        _time_stamp_last_offline = str(datetime.datetime.now())
                        self.cur.execute("UPDATE "+db_table_thermostat+" SET last_offline_time=%s "
                                         "WHERE thermostat_id=%s",
                                         (_time_stamp_last_offline, agent_id))
                        self.con.commit()
                else:
                    self.already_offline = False
                    self.cur.execute("UPDATE "+db_table_thermostat+" SET network_status=%s WHERE thermostat_id=%s",
                                     ('ONLINE', agent_id))
                    self.con.commit()

                # Step: Check if any Device is OFFLINE
                self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('5',))
                if self.cur.rowcount != 0:
                    self.device_offline_detection()
                # put the last scan time on database
                _time_stamp_last_scanned = str(datetime.datetime.now())
                self.cur.execute("UPDATE "+db_table_thermostat+" SET last_scanned_time=%s "
                                 "WHERE thermostat_id=%s",
                                 (_time_stamp_last_scanned, agent_id))
                self.con.commit()
            except Exception as er:
                print er
                print("ERROR: {} failed to update database name {}".format(agent_id, db_database))

            if len(self.changed_variables) == 0:
                print 'nothing changed'
                return
            else:
                print 'These things changed:'
                print self.changed_variables
            self.updateUI()

            if self.first_time_update:

                if self.get_variable('heat_setpoint') is None:
                    self.set_variable('heat_setpoint', 72) # default when device is in cool mode, no heat_setpoint provided
                else:
                    pass
                if self.get_variable('cool_setpoint') is None:
                    self.set_variable('cool_setpoint', 74) # default when device is in cool mode, no heat_setpoint provided
                else:
                    pass
                if self.get_variable('thermostat_mode') is not None:
                    self.authorized_thermostat_mode = self.get_variable('thermostat_mode')
                else:
                    pass
                if self.get_variable('fan_mode') is not None:
                    self.authorized_fan_mode = self.get_variable('fan_mode')
                else:
                    pass
                if self.get_variable('heat_setpoint') is not None:
                    self.authorized_heat_setpoint = self.get_variable('heat_setpoint')
                else:
                    pass
                if self.get_variable('cool_setpoint') is not None:
                    self.authorized_cool_setpoint = self.get_variable('cool_setpoint')
                else:
                    pass
                self.first_time_update = False
                self.changed_variables = log_variables  # log everything the first time
            else:
                pass

            # step2: determine whether device is tampered by unauthorized action

            if self._override:  # set points of device can be changed if _override setting of a device is true
                print "{} >> allow device override {}".format(agent_id, self._override)
                pass
            else:
                print "{} >> doesn't allow device override {}".format(agent_id, self._override)
                self.device_tampering_detection()

            # step3: update PostgresQL (meta-data) database
            try:
                for k, v in log_variables.items():
                    # check if column exists, then updateDB to corresponding column
                    self.cur.execute("select column_name from information_schema.columns where table_name=%s and column_name=%s",
                             (db_table_thermostat, k,))
                    if bool(self.cur.rowcount):
                        self.updateDB(db_table_thermostat, k, db_id_column_name, self.get_variable(k), agent_id)
                    else:
                        pass
                if self.ip_address != None:
                    psycopg2.extras.register_inet()
                    _ip_address = psycopg2.extras.Inet(self.ip_address)
                    self.cur.execute("UPDATE " + db_table_thermostat + " SET ip_address=%s WHERE thermostat_id=%s",
                                     (_ip_address, agent_id))
                    self.con.commit()
                print("{} updates database name {} during deviceMonitorBehavior successfully".format(agent_id, db_database))
                print(
                "{} updates database name {} during deviceMonitorBehavior successfully".format(agent_id, db_database))
            except Exception as er:
                print er
                print("ERROR: {} failed to update database name {}".format(agent_id, db_database))

            # step4: update cassandra database
            try:
                cassandraDB.insert(agent_id, Thermostat.variables, log_variables)
                print('Data Pushed to cassandra')
            except Exception as er:
                print("ERROR: {} fails to update cassandra database".format(agent_id))
                print er

            # step5: debug agent knowledge
            if debug_agent:
                print("printing agent's knowledge")
                for k, v in self.variables.items():
                    print (k, v)
                print('')

        def updateUI(self):
            topic = '/agent/ui/'+device_type+'/device_status_response/'+ _topic_Agent_UI_tail
            # now = datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                # headers_mod.DATE: now,
                headers_mod.FROM: agent_id,
                headers_mod.TO: 'ui'
            }
            _data = {'temperature': self.get_variable('temperature'), 'thermostat_mode':
                self.get_variable('thermostat_mode'), 'fan_mode': self.get_variable('fan_mode'),
                     'heat_setpoint': self.get_variable('heat_setpoint'),
                     'cool_setpoint': self.get_variable('cool_setpoint'),
                     'thermostat_state': self.get_variable('thermostat_state'),
                     'fan_state': self.get_variable('fan_state'),
                     'override': self._override
                     }
            if self.get_variable('battery') != None:
                _data['battery'] = self.get_variable('battery')
            if self.get_variable('hold') != None:
                _data['hold'] = self.get_variable('hold')
            message = json.dumps(_data)
            message = message.encode(encoding='utf_8')
            self.publish(topic, headers, message)

        # 4. updateUIBehavior (generic behavior)

        @matching.match_exact('/ui/agent/'+device_type+'/device_status/' + _topic_Agent_UI_tail)
        def updateUIBehavior(self, topic, headers, message, match):
            print agent_id + " got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            # reply message
            self.updateUI()

        # 5. deviceControlBehavior (generic behavior)
        @matching.match_exact('/ui/agent/'+device_type+'/update/'+ _topic_Agent_UI_tail)
        @catcherror('Failed to control')
        def deviceControlBehavior(self, topic, headers, message, match):
            print agent_id + " got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            # step1: change device status according to the receive message
            if self.isPostmsgValid(message[0]):  # check if the data is valid
                # _data = json.dumps(message[0])
                _data = json.loads(message[0])
                for k, v in _data.items():
                    if k == 'thermostat_mode':
                        self.authorized_thermostat_mode = _data.get('thermostat_mode')
                        if _data.get('thermostat_mode') == "HEAT":
                            for k, v in _data.items():
                                if k == 'heat_setpoint':
                                    self.authorized_heat_setpoint = _data.get('heat_setpoint')
                                else:
                                    pass
                        elif _data.get('thermostat_mode') == "COOL":
                            for k, v in _data.items():
                                if k == 'cool_setpoint':
                                    self.authorized_cool_setpoint = _data.get('cool_setpoint')
                                else:
                                    pass
                    elif k == 'fan_mode':
                        self.authorized_fan_mode = _data.get('fan_mode')
                    elif k == 'override':
                        self._override = _data.get('override')
                        try:
                            self.cur.execute("UPDATE " + db_table_thermostat + " SET override=%s WHERE thermostat_id=%s",
                                         (self._override, agent_id))
                            self.con.commit()
                        except Exception as er:
                            print 'override value not updated in db ' + str(er)
                    else:
                        pass
                print "{} >> self.authorized_thermostat_mode {}".format(agent_id, self.authorized_thermostat_mode)
                print "{} >> self.authorized_heat_setpoint {}".format(agent_id, self.authorized_heat_setpoint)
                print "{} >> self.authorized_cool_setpoint {}".format(agent_id, self.authorized_cool_setpoint)
                print "{} >> self.authorized_fan_mode {}".format(agent_id, self.authorized_fan_mode)
                try:
                    setDeviceStatusResult = Thermostat.setDeviceStatus(json.loads(message[0]))  # convert received message from string to JSON
                    #TODO need to do additional checking whether the device setting is actually success!!!!!!!!
                except Exception as er:
                    print "Agent id: "+agent_id
                    print "Error accessing device. Error:" + str(er)
                # step3: send reply message back to the UI
                topic = '/agent/ui/'+device_type+'/update_response/'+ _topic_Agent_UI_tail
                # now = datetime.utcnow().isoformat(' ') + 'Z'
                headers = {
                    'AgentID': agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                    # headers_mod.DATE: now,
                }
                if setDeviceStatusResult:
                    message = 'success'
                else:
                    message = 'failure'
            else:
                print("The POST message is invalid, check thermostat_mode, heat_setpoint, cool_setpoint "
                      "setting and try again\n")
                message = 'failure'
            self.publish(topic, headers, message)
            self.deviceMonitorBehavior() #Get device status, and get updated data


        def isPostmsgValid(self, postmsg):  # check validity of postmsg
            dataValidity = True
            try:
                # _data = json.dumps(postmsg)
                _data = json.loads(postmsg)
                for k, v in _data.items():
                    if k == 'thermostat_mode':
                        self.authorized_thermostat_mode = _data.get('thermostat_mode')
                        if _data.get('thermostat_mode') == "HEAT":
                            for k, v in _data.items():
                                if k == 'heat_setpoint':
                                    self.authorized_heat_setpoint = _data.get('heat_setpoint')
                                elif k == 'cool_setpoint':
                                    dataValidity = False
                                    break
                                else:
                                    pass
                        elif _data.get('thermostat_mode') == "COOL":
                            for k, v in _data.items():
                                if k == 'cool_setpoint':
                                    self.authorized_cool_setpoint = _data.get('cool_setpoint')
                                elif k == 'heat_setpoint':
                                    dataValidity = False
                                    break
                                else:
                                    pass
                    elif k == 'fan_mode':
                        self.authorized_fan_mode = _data.get('fan_mode')
                    else:
                        pass
            except:
                dataValidity = True
                print("dataValidity failed to validate data comes from UI")
            return dataValidity

        # 6. deviceIdentifyBehavior (generic behavior)
        @matching.match_exact('/ui/agent/'+device_type+'/identify/'+ _topic_Agent_UI_tail)
        def deviceIdentifyBehavior(self, topic, headers, message, match):
            print agent_id + " got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            # step1: change device status according to the receive message
            identifyDeviceResult = Thermostat.identifyDevice()
            # step2: send reply message back to the UI
            topic = '/agent/ui/identify_response/'+device_type+'/'+_topic_Agent_UI_tail
            # now = datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                # headers_mod.DATE: now,
            }
            if identifyDeviceResult:
                message = 'success'
            else:
                message = 'failure'
            self.publish(topic, headers, message)

        #9. update Postgres database
        def updateDB(self, table, column, column_ref, column_data, column_ref_data):
            self.cur.execute("UPDATE "+table+" SET "+column+"=%s "
                                 "WHERE "+column_ref+"=%s",
                                 (column_data, column_ref_data))
            self.con.commit()

        def device_offline_detection(self):
            _db_notification_subject = 'BEMOSS Device {} went OFFLINE!!!'.format(agent_id)
            _email_subject = '#Attention: BEMOSS Device {} went OFFLINE!!!'.format(agent_id)
            _email_text = '#Attention: BEMOSS Device {} went OFFLINE!!!'.format(agent_id)
            self.cur.execute("SELECT network_status FROM " + db_table_thermostat + " WHERE thermostat_id=%s",
                             (agent_id,))
            self.network_status = self.cur.fetchone()[0]
            print self.network_status
            if self.network_status == "OFFLINE":
                print "Found Device OFFLINE"
                self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('5',))
                self._active_alert_id = self.cur.fetchone()[0]
                self.cur.execute(
                    "SELECT id FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                    (str(self._active_alert_id), agent_id,))
                # If this is the first detected violation
                if self.cur.rowcount == 0:
                    print "first device offline detected"
                    self.cur.execute(
                        "INSERT INTO " + db_table_temp_time_counter + " VALUES(DEFAULT,%s,%s,%s,%s,%s)",
                        (self._active_alert_id, agent_id, '0', '0', '0'))
                    self.con.commit()
                    self.send_device_notification_db_device(_db_notification_subject, self._active_alert_id)
                    self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'1'))
                    # Send email if exist
                    if self.cur.rowcount != 0:
                        self._offline_alert_email = self.cur.fetchall()
                        for single_email_1 in self._offline_alert_email:
                            print single_email_1[0]
                            self.send_device_notification_email_all(single_email_1[0], _email_text, _email_subject)

                    # Send SMS if provided by user
                    self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'2'))
                    if self.cur.rowcount != 0:
                        self._offline_alert_sms = self.cur.fetchall()
                        for single_number_ in self._offline_alert_email:
                            print single_number_[0]
                            self.send_device_notification_sms(single_number_[0])
                else:
                        self.priority_counter(self._active_alert_id, _db_notification_subject)
            else:
                print "The Device is ONLINE"

        # TODO refactor this one
        def send_device_notification_db(self, device_msg, _active_alert_id):
            print " INSIDE send_device_notification_db"
            # Find the priority id
            self.cur.execute(
                "SELECT priority_id FROM " + db_table_active_alert + " WHERE id=%s",
                (str(_active_alert_id),))
            self.priority_id = self.cur.fetchone()[0]

            # Find the priority level
            self.cur.execute(
                "SELECT priority_level FROM " + db_table_priority + " WHERE id=%s",
                str(self.priority_id))
            self.priority_level = self.cur.fetchone()[0]

            # Insert the notification into DB
            self.cur.execute("INSERT INTO " + db_table_bemoss_notify + " VALUES(DEFAULT,%s,%s,%s,%s)",
                             (device_msg,
                              str(datetime.datetime.now()), 'Alert', str(self.priority_level)))
            self.con.commit()

        # TODO refactor this one
        def send_device_notification_db_device(self, device_msg, _active_alert_id):
            print " INSIDE send_device_notification_db_device"
            # Find the priority id
            self.cur.execute(
                "SELECT priority_id FROM " + db_table_active_alert + " WHERE id=%s",
                (str(_active_alert_id),))
            self.priority_id = self.cur.fetchone()[0]

            # Find the priority level
            self.cur.execute(
                "SELECT priority_level FROM " + db_table_priority + " WHERE id=%s",
                str(self.priority_id))
            self.priority_level = self.cur.fetchone()[0]

            # Insert the notification into DB
            self.cur.execute("INSERT INTO " + db_table_bemoss_notify + " VALUES(DEFAULT,%s,%s,%s,%s)",
                             (device_msg,
                              str(datetime.datetime.now()), 'Alert', str(self.priority_level)))
            self.con.commit()

            # Find the number of total number notifications sent for the same alert and device
            self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('5',))
            if self.cur.rowcount != 0:
                self.cur.execute(
                    "SELECT no_notifications_sent FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                    (str(_active_alert_id), agent_id,))
                if self.cur.rowcount != 0:
                    self._no_notifications_sent = self.cur.fetchone()[0]
                    self.con.commit()
                    print self._no_notifications_sent
                    self._no_notifications_sent = int(self._no_notifications_sent) + 1
                    self.cur.execute(
                        "UPDATE " + db_table_temp_time_counter + " SET no_notifications_sent=%s WHERE alert_id=%s AND device_id=%s",
                        (str(self._no_notifications_sent), str(_active_alert_id), agent_id,))
                    self.con.commit()

        def send_device_notification_sms(self, _active_alert_phone_number):
            print "INSIDE send_device_notification_sms"
            print _active_alert_phone_number
            _sms_subject = 'Please Check BEMOSS Notifications'
            smsService = SMSService()
            smsService.sendSMS(email_fromaddr, _active_alert_phone_number, email_username, email_password, _sms_subject, email_mailServer)

        def send_device_notification_email_all(self, _active_alert_email, _email_subject, _email_text):
            emailService = EmailService()

            # Send Email
            emailService.sendEmail(email_fromaddr, _active_alert_email, email_username,
                                   email_password, _email_subject, _email_text, email_mailServer)

         # TODO refactor this one

        def priority_counter(self, _active_alert_id, device_msg_1):
            # find the priority counter then compare it with priority_counter in priority table
            # if greater than the counter then send notification and reset the value
            # else just increase the counter
            print "INSIDE the priority_counter"
            self.cur.execute(
                "SELECT priority_counter FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                (str(_active_alert_id), agent_id,))
            self.priority_count = self.cur.fetchone()[0]
            self.con.commit()

            # Find the priority id from active alert table
            self.cur.execute(
                "SELECT priority_id FROM " + db_table_active_alert + " WHERE id=%s",
                (str(_active_alert_id),))
            self.priority_id = self.cur.fetchone()[0]
            self.con.commit()

            # Find the priority limit from the priority counter
            self.cur.execute(
                "SELECT priority_counter FROM " + db_table_priority + " WHERE id=%s",
                (str(self.priority_id),))
            self.priority_limit = self.cur.fetchone()[0]
            self.con.commit()

            if int(self.priority_count) > int(self.priority_limit):
                self.cur.execute(
                    "SELECT no_notifications_sent FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                    (str(_active_alert_id), agent_id,))
                self._no_notifications_sent = self.cur.fetchone()[0]
                self._no_notifications_sent = int(self._no_notifications_sent) + 1
                self.send_device_notification_db(device_msg_1, _active_alert_id)
                self.cur.execute(
                    "UPDATE " + db_table_temp_time_counter + " SET priority_counter=%s WHERE alert_id=%s AND device_id=%s",
                    ('0', str(_active_alert_id), agent_id,))
                self.con.commit()

                print "INSIDE the priority counter exceeded the defined range"
                # send email if checked
                self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'1'))
                # Send email if exist
                if self.cur.rowcount != 0:
                    self._tampering_alert_email_misoperation = self.cur.fetchall()
                    for single_email_1 in self._tampering_alert_email_misoperation:
                        print single_email_1[0]
                        self.send_device_notification_email_all(single_email_1[0], device_msg_1, device_msg_1)

                # Send SMS if provided by user
                self.cur.execute(
                    "SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",
                    (self._active_alert_id,'2'))
                if self.cur.rowcount != 0:
                    self._tampering_alert_sms_misoperation = self.cur.fetchall()
                    for single_number_misoperation in self._tampering_alert_sms_misoperation:
                        print single_number_misoperation[0]
                        self.send_device_notification_sms(single_number_misoperation[0])
            else:
                self.priority_count = int(self.priority_count) + 1
                self.cur.execute(
                    "UPDATE " + db_table_temp_time_counter + " SET priority_counter=%s WHERE alert_id=%s AND device_id=%s",
                    (str(self.priority_count), str(_active_alert_id), agent_id,))


        def device_tampering_detection(self):
            allowance = 0
            self.unauthorized_settings = {}  # dict to store key value of unauthorized setting

            if (self.get_variable(
                    'scheduleData') != self.authorized_scheduleData and self.authorized_scheduleData is not None and len(
                    self.authorized_scheduleData) > 0):
                print "Schedule (mode) has been tampered"
                self._unauthorized_scheduleData = self.get_variable('scheduleData')
                self.unauthorized_settings['scheduleData'] = self.get_variable('scheduleData')
                self.set_variable('scheduleData', self.authorized_scheduleData)
                Thermostat.setDeviceSchedule(self.authorized_scheduleData)
                return
            if self.get_variable('thermostat_mode') != self.authorized_thermostat_mode \
                    and self.authorized_thermostat_mode is not None:
                # collect this result for alarm notification & device control
                _unauthorized_thermostat_mode = self.get_variable('thermostat_mode')
                print_out = "Unauthorized thermostat mode changed to " + str(_unauthorized_thermostat_mode)
                print print_out
                self.set_variable('thermostat_mode', self.authorized_thermostat_mode)
                self.unauthorized_settings['thermostat_mode'] = self.get_variable('thermostat_mode')

            if self.get_variable('fan_mode') != self.authorized_fan_mode \
                    and self.authorized_fan_mode is not None:
                # collect this result for alarm notification & device control
                _unauthorized_fan_mode = self.get_variable('fan_mode')
                print_out = "Unauthorized fan mode changed to " + str(_unauthorized_fan_mode)
                print print_out
                self.set_variable('fan_mode', self.authorized_fan_mode)
                self.unauthorized_settings['fan_mode'] = self.get_variable('fan_mode')

            if self.get_variable(
                    'heat_setpoint') != self.authorized_heat_setpoint and self.authorized_heat_setpoint is not None:
                validChange = False
                if self.get_variable('hold') == 0 or self.get_variable('hold') == 1:
                    #This means run on schedule, or schedule_override, or no hold function
                    current_schedule_setpoints = self.getScheduleSetpoint(datetime.datetime.now())
                    ahead_schedule_setpoints = self.getScheduleSetpoint(datetime.datetime.now()+datetime.timedelta(minutes=10))
                    if self.get_variable('heat_setpoint') in  [current_schedule_setpoints[1], ahead_schedule_setpoints[1]]:
                        self.authorized_heat_setpoint = self.get_variable('heat_setpoint')
                        validChange = True

                if validChange == False:
                    # collect this result for alarm notification & device control
                    _unauthorized_change = self.get_variable('heat_setpoint') - self.authorized_heat_setpoint
                    temp_tolerance = 3
                    if (abs(_unauthorized_change) > temp_tolerance):
                        _unauthorized_heat_setpoint = self.get_variable('heat_setpoint')
                        print_out = "Unauthorized heat setpoint changed to " + str(_unauthorized_heat_setpoint)
                        print print_out
                        if _unauthorized_change > 0:
                            allowance = 2
                            Thermostat.variables['heat_setpoint'] = self.authorized_heat_setpoint + temp_tolerance
                            self.set_variable('heat_setpoint', self.authorized_heat_setpoint + temp_tolerance)
                        else:
                            allowance = -2
                            Thermostat.variables['heat_setpoint'] = self.authorized_heat_setpoint - temp_tolerance
                            self.set_variable('heat_setpoint', self.authorized_heat_setpoint - temp_tolerance)
                            # self.unauthorized_settings['heat_setpoint'] = self.get_variable('heat_setpoint')
                        self.unauthorized_settings['heat_setpoint'] = _unauthorized_heat_setpoint
                    else:
                        # Change within the range, allow the change.
                        pass

            if self.get_variable('cool_setpoint') != self.authorized_cool_setpoint \
                    and self.authorized_cool_setpoint is not None:
                # collect this result for alarm notification & device control
                validChange = False
                if self.get_variable('hold') == 0 or self.get_variable('hold') == 1:
                    #This means run on schedule
                    current_schedule_setpoints = self.getScheduleSetpoint(datetime.datetime.now())
                    ahead_schedule_setpoints = self.getScheduleSetpoint(datetime.datetime.now()+datetime.timedelta(minutes=10))
                    if self.get_variable('cool_setpoint') in  [current_schedule_setpoints[0], ahead_schedule_setpoints[0]]:
                        self.authorized_cool_setpoint = self.get_variable('cool_setpoint')
                        validChange = True

                if validChange == False:
                    temp_tolerance = 3
                    _unauthorized_change = self.get_variable('cool_setpoint') - self.authorized_cool_setpoint
                    if abs(_unauthorized_change) > temp_tolerance:
                        _unauthorized_cool_setpoint = self.get_variable('cool_setpoint')
                        print_out = "Unauthorized cool setpoint changed to " + str(_unauthorized_cool_setpoint)
                        print print_out
                        if _unauthorized_change > 0:
                            allowance = 2
                            Thermostat.variables['cool_setpoint'] = self.authorized_cool_setpoint + temp_tolerance
                            self.set_variable('cool_setpoint', self.authorized_cool_setpoint + temp_tolerance)
                        else:
                            allowance = -2
                            Thermostat.variables['cool_setpoint'] = self.authorized_cool_setpoint - temp_tolerance
                            self.set_variable('cool_setpoint', self.authorized_cool_setpoint - temp_tolerance)
                            # self.unauthorized_settings['cool_setpoint'] = self.get_variable('cool_setpoint')
                        self.unauthorized_settings['cool_setpoint'] = _unauthorized_cool_setpoint
                    else:
                        pass

            if len(self.unauthorized_settings) != 0:
                '''

                topic = '/thermostat/lighting/device_tampering'
                headers = {
                    'AgentID': agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                    # headers_mod.DATE: now,
                    headers_mod.FROM: agent_id,
                    headers_mod.TO: 'ui'
                }
                _data = {"status": "ON", "color": (255, 165, 0), "brightness": 30}
                message = json.dumps(_data)
                message = message.encode(encoding='utf_8')
                self.publish(topic, headers, message)
                '''

                _tampering_device_msg = ""
                _device_control_msg = {}
                for k, v in self.unauthorized_settings.items():
                    if k == 'thermostat_mode':
                        _tampering_device_msg += 'set point: {}, authorized setting: {}, tampering setting: {}\n' \
                            .format(k, self.authorized_thermostat_mode, _unauthorized_thermostat_mode)
                        _device_control_msg[k] = self.authorized_thermostat_mode
                        if self.authorized_thermostat_mode == 'HEAT':
                            if self.authorized_heat_setpoint != None:
                                _device_control_msg['heat_setpoint'] = self.authorized_heat_setpoint + allowance
                        elif self.authorized_thermostat_mode == 'COOL':
                            if self.authorized_cool_setpoint != None:
                                _device_control_msg['cool_setpoint'] = self.authorized_cool_setpoint + allowance
                        else:
                            pass
                    elif k == 'heat_setpoint':
                        _tampering_device_msg += 'tampered parameter: {}, authorized setting: {}, tampering setting: {}\n' \
                            .format(k, self.authorized_heat_setpoint, _unauthorized_heat_setpoint)
                        if 'thermostat_mode' not in self.unauthorized_settings:
                            _device_control_msg[k] = self.authorized_heat_setpoint + allowance
                    elif k == 'cool_setpoint':
                        _tampering_device_msg += 'tampered parameter: {}, authorized setting: {}, tampering setting: {}\n' \
                            .format(k, self.authorized_cool_setpoint, _unauthorized_cool_setpoint)
                        if 'thermostat_mode' not in self.unauthorized_settings:
                            _device_control_msg[k] = self.authorized_cool_setpoint + allowance
                    elif k == 'fan_mode':
                        _tampering_device_msg += 'tampered parameter: {}, authorized setting: {}, tampering setting: {}\n' \
                            .format(k, self.authorized_fan_mode, _unauthorized_fan_mode)
                        _device_control_msg[k] = self.authorized_fan_mode
                    elif k == 'activeSchedule':
                        _tampering_device_msg += 'tampered parameter: {}, authorized setting: {}, tampering setting:\
                         {}\n'.format(k,self.authorized_scheduleData,self._unauthorized_scheduleData)
                    else:
                        pass
                # TODO 1 set all settings back to previous state
                print "type(_device_control_msg)" + str(type(_device_control_msg))
                print "_device_control_msg " + str(_device_control_msg)
                Thermostat.setDeviceStatus(json.loads(json.dumps(_device_control_msg)))
                print "{} >> set points have been tampered but already set back to the authorized settings" \
                    .format(agent_id)

                '''
                time.sleep(2)
                topic = '/thermostat/lighting/device_tampering'
                headers = {
                    'AgentID': agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                    # headers_mod.DATE: now,
                    headers_mod.FROM: agent_id,
                    headers_mod.TO: 'ui'
                }
                _data = {"status": "OFF"}
                message = json.dumps(_data)
                message = message.encode(encoding='utf_8')
                self.publish(topic, headers, message)
                '''

                # TODO 2 notify admin for device tampering action
                self._email_subject = '#Attention: BEMOSS Device {} has been tampered!!!'.format(agent_id)
                self._email_text = 'Here is the detail of device status\n' + str('1') \
                          + 'All set points have been set back to the authorized settings'

                self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('1',))

                if self.cur.rowcount != 0:
                    self._active_alert_id = self.cur.fetchone()[0]
                    self.con.commit()
                    print self._active_alert_id

                    self.cur.execute(
                        "SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",
                        (self._active_alert_id,'1'))
                    if self.cur.rowcount != 0:
                        self._tampering_alert_email_2 = self.cur.fetchall()
                        for single_email in self._tampering_alert_email_2:
                            print single_email[0]
                            self.send_device_notification_email_all(single_email[0], self._email_subject, self._email_text)

                    # Send SMS if provided by user
                    self.cur.execute(
                        "SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",
                        (self._active_alert_id,'2'))
                    if self.cur.rowcount != 0:
                        self._tampering_alert_sms = self.cur.fetchall()
                        for single_number in self._tampering_alert_sms:
                            print single_number[0]
                            self.send_device_notification_sms(single_number[0])
                    # Send the notification to the DB
                    self.send_device_notification_db(_tampering_device_msg, self._active_alert_id)



                # reset params

                # self.send_device_notification(_tampering_device_msg)
                self.time_sent_notifications_device_tampering = datetime.datetime.now()
                # self.first_time_detect_device_tampering = False
            else:
                pass

        def getScheduleSetpoint(self,testDate):
            schData = self.get_variable('scheduleData')
            daysofweek=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            todayDay = daysofweek[testDate.weekday()]
            if todayDay != 'monday':
                yesterdayDay = daysofweek[testDate.weekday()-1]
            else:
                yesterdayDay = 'sunday'

            TodaysSchedule = schData[todayDay]
            YesterdaysSchedule = schData[yesterdayDay]
            setPoints = YesterdaysSchedule[-1][2:] #yesterday's last setpoint
            nowminute = testDate.hour*60+testDate.minute
            for entries in TodaysSchedule:
                if int(entries[1]) <= nowminute:
                    setPoints = [int(entries[2]), int(entries[3])]
                else:
                    break
            return setPoints

    Agent.__name__ = 'Thermostat Agent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(ThermostatAgent,
                       description='Thermostat agent',
                       argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
