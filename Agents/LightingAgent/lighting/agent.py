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
import logging
import importlib
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
import datetime
from bemoss_lib.communication.Email import EmailService
from bemoss_lib.communication.sms import SMSService
import psycopg2
import psycopg2.extras
import socket
import settings

from bemoss_lib.databases.cassandraAPI import cassandraDB
utils.setup_logging()
_log = logging.getLogger(__name__)

# Step1: Agent Initialization
def LightingAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            kwargs.pop(name)
        except KeyError:
            return config.get(name, '')

    #1. @params agent
    agent_id = get_config('agent_id')
    device_monitor_time = get_config('device_monitor_time')
    max_monitor_time = int(settings.DEVICES['max_monitor_time'])

    debug_agent = False
    #List of all keywords for a lighting agent
    agentAPImapping = dict(status=[], brightness=[], color=[], saturation=[],power=[])
    log_variables = dict(status='text',brightness='double',hexcolor='text',power='double',offline_count='int')
    #2. @params device_info
    #TODO correct the launchfile in Device Discovery Agent
    building_name = get_config('building_name')
    zone_id = get_config('zone_id')
    model = get_config('model')
    if model == "Philips hue bridge 2012":
        hue_username = get_config('username')
    else:
        hue_username = ''
    device_type = get_config('type')
    address = get_config('address')
    _address = address
    _address = _address.replace('http://', '')
    _address = _address.replace('https://', '')
    try:  # validate whether or not address is an ip address
        socket.inet_aton(_address)
        ip_address = _address
    except socket.error:
        ip_address = None
    identifiable = get_config('identifiable')

    #3. @params agent & DB interfaces
    #TODO delete variable topic
    topic = get_config('topic')

    #TODO get database parameters from settings.py, add db_table for specific table
    db_host = get_config('db_host')
    db_port = get_config('db_port')
    db_database = get_config('db_database')
    db_user = get_config('db_user')
    db_password = get_config('db_password')
    db_table_lighting = settings.DATABASES['default']['TABLE_lighting']
    db_table_active_alert = settings.DATABASES['default']['TABLE_active_alert']
    db_table_bemoss_notify = settings.DATABASES['default']['TABLE_bemoss_notify']
    db_table_alerts_notificationchanneladdress = settings.DATABASES['default'][
        'TABLE_alerts_notificationchanneladdress']
    db_table_temp_time_counter = settings.DATABASES['default']['TABLE_temp_time_counter']
    db_table_priority = settings.DATABASES['default']['TABLE_priority']

    #construct _topic_Agent_UI based on data obtained from DB
    _topic_Agent_UI_tail = building_name + '/' + str(zone_id) + '/' + agent_id

    #4. @params device_api
    api = get_config('api')
    apiLib = importlib.import_module("DeviceAPI.classAPI."+api)

    #4.1 initialize device object
    Light = apiLib.API(model=model, device_type=device_type, api=api, address=address, username = hue_username, agent_id=agent_id, db_host=db_host, db_port=db_port, db_user=db_user, db_password=db_password, db_database=db_database)
    print("{0}agent is initialized for {1} using API={2} at {3}".format(agent_id, Light.get_variable('model'),
                                                                        Light.get_variable('api'),
                                                                        Light.get_variable('address')))

    #5. @params notification_info
    send_notification = True
    email_fromaddr = settings.NOTIFICATION['email']['fromaddr']
    email_username = settings.NOTIFICATION['email']['username']
    email_password = settings.NOTIFICATION['email']['password']
    email_mailServer = settings.NOTIFICATION['email']['mailServer']
    notify_heartbeat = settings.NOTIFICATION['heartbeat']

    class Agent(PublishMixin, BaseAgent):
        """Agent for querying WeatherUndergrounds API"""

        #1. agent initialization    
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            #1. initialize all agent variables
            self.variables = kwargs
            self.valid_data = False
            self._keep_alive = True
            self.flag = 1
            self.topic = topic
            self.time_send_notification = 0
            self.event_ids = list()
            self.time_sent_notifications = {}
            self.notify_heartbeat = notify_heartbeat
            self.ip_address = ip_address if ip_address != None else None
            self.changed_variables = None
            self.lastUpdateTime = None
            self.already_offline = False

            #2. setup connection with db -> Connect to bemossdb database
            try:
                self.con = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user,
                                            password=db_password)
                self.cur = self.con.cursor()  # open a cursor to perfomm database operations
                print("{} connects to the database name {} successfully".format(agent_id, db_database))
            except:
                print("ERROR: {} fails to connect to the database name {}".format(agent_id, db_database))
            #3. send notification to notify building admin
            self.send_notification = send_notification
            self.subject = 'Message from ' + agent_id

        #These set and get methods allow scalability 
        def set_variable(self,k,v):  # k=key, v=value
            self.variables[k] = v
    
        def get_variable(self,k):
            return self.variables.get(k, None)  # default of get_variable is none
        
        #2. agent setup method
        def setup(self):
            super(Agent, self).setup()
            #Do a one time push when we start up so we don't have to wait for the periodic
            self.timer(1, self.deviceMonitorBehavior)
            if identifiable == "True": Light.identifyDevice()

        @periodic(max_monitor_time) #save all data every max_monitor_time
        def backupSaveData(self):
            try:
                Light.getDeviceStatus()
                cassandraDB.insert(agent_id,Light.variables,log_variables)
                print('Every Data Pushed to cassandra')
            except Exception as er:
                print("ERROR: {} fails to update cassandra database".format(agent_id))
                print er

        #3. deviceMonitorBehavior (TickerBehavior)
        @periodic(device_monitor_time)
        def deviceMonitorBehavior(self):
            #step1: get current status of a thermostat, then map keywords and variables to agent knowledge
            try:
                Light.getDeviceStatus()
            except:
                print("device connection is not successful")

            self.changed_variables = dict()
            for v in log_variables:
                if v in Light.variables:
                    if not v in self.variables or self.variables[v] != Light.variables[v]:
                        self.variables[v] = Light.variables[v]
                        self.changed_variables[v] = log_variables[v]
                else:
                    if v not in self.variables: #it won't be in self.variables either (in the first time)
                        self.changed_variables[v] = log_variables[v]
                        self.variables[v] = None
            try:
                # Step: Check if any Device is OFFLINE
                self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('5',))
                if self.cur.rowcount != 0:
                    self.device_offline_detection()

                # Put scan time in database
                _time_stamp_last_scanned = datetime.datetime.now()
                self.cur.execute("UPDATE "+db_table_lighting+" SET last_scanned_time=%s "
                                 "WHERE lighting_id=%s",
                                 (_time_stamp_last_scanned, agent_id))
                self.con.commit()
            except Exception as er:
                print er
                print("ERROR: {} failed to update last scanned time".format(agent_id))

            if len(self.changed_variables) == 0:
                print 'nothing changed'
                return

            self.updateUI()
            #step4: update PostgresQL (meta-data) database
            try:
                self.cur.execute("UPDATE "+db_table_lighting+" SET status=%s WHERE lighting_id=%s",
                                 (self.get_variable('status'), agent_id))
                self.con.commit()
                self.cur.execute("UPDATE "+db_table_lighting+" SET brightness=%s WHERE lighting_id=%s",
                                 (self.get_variable('brightness'), agent_id))
                self.con.commit()
                self.cur.execute("UPDATE "+db_table_lighting+" SET color=%s WHERE lighting_id=%s",
                                 (self.get_variable('hexcolor'), agent_id))
                self.con.commit()
                try:
                    if self.get_variable('status') == "ON":
                        multiple_on_off_status = ""
                        for dummyvar in range(self.get_variable('number_lights')):
                            multiple_on_off_status += "1"
                        self.cur.execute("UPDATE "+db_table_lighting+" SET multiple_on_off=%s WHERE lighting_id=%s",
                                        (multiple_on_off_status, agent_id))
                        self.con.commit()
                    else:  # status is off
                        multiple_on_off_status = ""
                        for dummyvar in range(self.get_variable('number_lights')):
                            multiple_on_off_status += "0"
                        self.cur.execute("UPDATE "+db_table_lighting+" SET multiple_on_off=%s WHERE lighting_id=%s",
                                        (multiple_on_off_status, agent_id))
                        self.con.commit()
                except:
                    print("{} this agent has no multiple_on_off_status".format(agent_id))
                #TODO check ip_address
                if self.ip_address != None:
                    psycopg2.extras.register_inet()
                    _ip_address = psycopg2.extras.Inet(self.ip_address)
                    self.cur.execute("UPDATE "+db_table_lighting+" SET ip_address=%s WHERE lighting_id=%s",
                                     (_ip_address, agent_id))
                    self.con.commit()


                if self.get_variable('offline_count') >= 3:
                    self.cur.execute("UPDATE "+db_table_lighting+" SET network_status=%s WHERE lighting_id=%s",
                                     ('OFFLINE', agent_id))
                    self.con.commit()
                    if self.already_offline is False:
                        self.already_offline = True
                        _time_stamp_last_offline = str(datetime.datetime.now())
                        self.cur.execute("UPDATE "+db_table_lighting+" SET last_offline_time=%s WHERE lighting_id=%s",
                                         (_time_stamp_last_offline, agent_id))
                        self.con.commit()
                else:
                    self.already_offline = False
                    self.cur.execute("UPDATE "+db_table_lighting+" SET network_status=%s WHERE lighting_id=%s",
                                     ('ONLINE', agent_id))
                    self.con.commit()
                print("{} updates database name {} during deviceMonitorBehavior successfully".format(agent_id, db_database))
            except:
                print("ERROR: {} fails to update the database name {}".format(agent_id,db_database))

            #step5: update Cassandra (time-series) database
            try:
                cassandraDB.insert(agent_id,self.variables,log_variables)
                print('Data Pushed to cassandra')
                print "{} success update".format(agent_id)
            except Exception as er:
                print("ERROR: {} fails to update cassandra database".format(agent_id))
                print er
            #step6: debug agent knowledge
            if debug_agent:
                print("printing agent's knowledge")
                for k,v in self.variables.items():
                    print (k,v)
                print('')

            if debug_agent:
                print("printing agentAPImapping's fields")
                for k, v in agentAPImapping.items():
                    if k is None:
                        agentAPImapping.update({v: v})
                        agentAPImapping.pop(k)
                for k, v in agentAPImapping.items():
                    print (k, v)

        def device_offline_detection(self):
            self.cur.execute("SELECT nickname FROM " + db_table_lighting + " WHERE lighting_id=%s",
                             (agent_id,))
            print agent_id
            if self.cur.rowcount != 0:
                device_nickname=self.cur.fetchone()[0]
                print device_nickname
            else:
                device_nickname = ''
            _db_notification_subject = 'BEMOSS Device {} {} went OFFLINE!!!'.format(device_nickname,agent_id)
            _email_subject = '#Attention: BEMOSS Device {} {} went OFFLINE!!!'.format(device_nickname,agent_id)
            _email_text = '#Attention: BEMOSS Device {}  {} went OFFLINE!!!'.format(device_nickname,agent_id)
            self.cur.execute("SELECT network_status FROM " + db_table_lighting + " WHERE lighting_id=%s",
                             (agent_id,))
            self.network_status = self.cur.fetchone()[0]
            print self.network_status
            if self.network_status=="OFFLINE":
                print "Found Device OFFLINE"
                self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('5',))
                self._active_alert_id = self.cur.fetchone()[0]
                self.cur.execute(
                    "SELECT id FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                    (str(self._active_alert_id), agent_id,))
                # If this is the first detected violation
                if self.cur.rowcount == 0:
                    print "first device offline detected"
                    # create counter in DB
                    self.cur.execute(
                        "INSERT INTO " + db_table_temp_time_counter + " VALUES(DEFAULT,%s,%s,%s,%s,%s)",
                        (self._active_alert_id, agent_id, '0', '0', '0'))
                    self.con.commit()
                    self.send_device_notification_db(_db_notification_subject, self._active_alert_id)

                    # Send email if exist
                    self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'1'))
                    if self.cur.rowcount != 0:
                        self._alert_email = self.cur.fetchall()
                        for single_email_1 in self._alert_email:
                            print single_email_1[0]
                            self.send_device_notification_email(single_email_1[0], _email_subject, _email_text)

                    # Send SMS if provided by user
                    self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'2'))
                    if self.cur.rowcount != 0:
                        self._alert_sms_phone_no = self.cur.fetchall()
                        for single_number in self._alert_sms_phone_no:
                            print single_number[0]
                            self.send_device_notification_sms(single_number[0], _email_subject)
                else:
                    self.priority_counter(self._active_alert_id, _db_notification_subject)
            else:
                print "The Device is ONLINE"

        def send_device_notification_db(self, _tampering_device_msg, _active_alert_id):
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

            # Insert into DB the notification
            self.cur.execute("INSERT INTO " + db_table_bemoss_notify + " VALUES(DEFAULT,%s,%s,%s,%s)",
                             (_tampering_device_msg,
                              str(datetime.datetime.now()), 'Alert', str(self.priority_level)))
            self.con.commit()

            # Find the number of notifications sent for the same alert and device
            self.cur.execute(
                "SELECT no_notifications_sent FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                (str(_active_alert_id), agent_id,))
            self._no_notifications_sent = self.cur.fetchone()[0]
            self.con.commit()
            print self._no_notifications_sent
            self._no_notifications_sent = int(self._no_notifications_sent) + 1
            print self._no_notifications_sent
            self.cur.execute(
                "UPDATE " + db_table_temp_time_counter + " SET no_notifications_sent=%s WHERE alert_id=%s AND device_id=%s",
                (str(self._no_notifications_sent), str(_active_alert_id), agent_id,))
            self.con.commit()

        def send_device_notification_email(self, _active_alert_email, _email_subject, _email_text):
            emailService = EmailService()
            # Send Email
            emailService.sendEmail(email_fromaddr, _active_alert_email, email_username,
                                   email_password, _email_subject, _email_text, email_mailServer)

        def send_device_notification_sms(self, _active_alert_phone_number_misoperation, _sms_subject):
            print "INSIDE send_device_notification_sms"
            print _active_alert_phone_number_misoperation
            smsService = SMSService()
            smsService.sendSMS(email_fromaddr, _active_alert_phone_number_misoperation, email_username, email_password, _sms_subject, email_mailServer)

        # TODO: this function is in all other agents, need to get rid of those redundent codes.
        def priority_counter(self, _active_alert_id, _tampering_device_msg_1):
            # Find the priority counter limit then compare it with priority_counter in priority table
            # if greater than the counter limit then send notification and reset the value
            # else just increase the counter
            print "INSIDE the priority_counter"
            _email_subject = '#Attention: BEMOSS Device {} went OFFLINE!!!'.format(agent_id)
            _email_text = '#Attention: BEMOSS Device {} went OFFLINE!!!'.format(agent_id)
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

            # Find the priority limit from the priority table
            self.cur.execute(
                "SELECT priority_counter FROM " + db_table_priority + " WHERE id=%s",
                (str(self.priority_id),))
            self.priority_limit = self.cur.fetchone()[0]
            self.con.commit()

            # If the counter reaches the limit
            if int(self.priority_count) > int(self.priority_limit):
                self.send_device_notification_db(_tampering_device_msg_1, _active_alert_id)
                self.cur.execute(
                    "UPDATE " + db_table_temp_time_counter + " SET priority_counter=%s WHERE alert_id=%s AND device_id=%s",
                    ('0', str(_active_alert_id), agent_id,))
                self.con.commit()

                print "INSIDE the priority counter exceeded the defined range"
                # Send email if exist
                self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'1'))
                if self.cur.rowcount != 0:
                    self._alert_email = self.cur.fetchall()
                    for single_email_1 in self._alert_email:
                        print single_email_1[0]
                        self.send_device_notification_email(single_email_1[0], _email_subject, _email_text)

                # Send SMS if provided by user
                self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'2'))
                if self.cur.rowcount != 0:
                    self._alert_sms_phone_no = self.cur.fetchall()
                    for single_number in self._alert_sms_phone_no:
                        print single_number[0]
                        self.send_device_notification_sms(single_number[0], _email_subject)
            else:
                self.priority_count = int(self.priority_count) + 1
                self.cur.execute(
                    "UPDATE " + db_table_temp_time_counter + " SET priority_counter=%s WHERE alert_id=%s AND device_id=%s",
                    (str(self.priority_count), str(_active_alert_id), agent_id,))

        def updateUI(self):
            topic = '/agent/ui/'+device_type+'/device_status_response/'+_topic_Agent_UI_tail
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                headers_mod.FROM: agent_id,
                headers_mod.TO: 'ui'
            }
            _data={'status': self.get_variable('status'),
                   'brightness': self.get_variable('brightness'), 'color': self.get_variable('hexcolor'),
                   'saturation': self.get_variable('saturation')}
            message = json.dumps(_data)
            message = message.encode(encoding='utf_8')
            self.publish(topic, headers, message)

        #4. updateUIBehavior (generic behavior)
        @matching.match_exact('/ui/agent/'+device_type+'/device_status/'+_topic_Agent_UI_tail)
        def updateUIBehavior(self,topic,headers,message,match):
            print "{} agent got\nTopic: {topic}".format(self.get_variable("agent_id"),topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            #reply message
            self.updateUI()


        #5. deviceControlBehavior (generic behavior)
        @matching.match_exact('/ui/agent/'+device_type+'/update/'+_topic_Agent_UI_tail)
        def deviceControlBehavior(self,topic,headers,message,match):
            #print received message from UI
            print "{} agent got\nTopic: {topic}".format(self.get_variable("agent_id"),topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)

            #prepare message content for response
            topic = '/agent/ui/'+device_type+'/update_response/'+_topic_Agent_UI_tail
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                headers_mod.FROM: agent_id,
                headers_mod.TO: 'ui'
            }
            #step1: change device status according to the receive message
            if self.isPostmsgValid(message[0]):
                setDeviceStatusResult = Light.setDeviceStatus(json.loads(message[0])) #convert received message from string to JSON
                #TODO need to do additional checking whether the device setting is actually success!!!!!!!!
                #step3: send reply message back to the UI
                if setDeviceStatusResult:
                    message = 'success'
                else:
                    message = 'failure'
            else:
                print("The POST message is invalid, check brightness, status or color setting and try again\n")
                message = 'failure'
            self.publish(topic, headers, message)
            self.deviceMonitorBehavior()

        def isPostmsgValid(self, postmsg):  # check validity of postmsg
            dataValidity = True
            try:
                _data = json.loads(postmsg)
                if ("brightness" in _data.keys()) or ("status" in _data.keys()) or ("color" in _data.keys()):
                    dataValidity = True
                else:
                    dataValidity = False
            except:
                dataValidity = False
                print("dataValidity failed to validate data coming from UI")
            return dataValidity

        #6. deviceIdentifyBehavior(generic behavior)
        @matching.match_exact('/ui/agent/'+device_type+'/identify/'+_topic_Agent_UI_tail)
        def deviceIdentifyBehavior(self,topic,headers,message,match):
            print "{} agent got\nTopic: {topic}".format(self.get_variable("agent_id"),topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            #step1: change device status according to the receive message
            identifyDeviceResult = Light.identifyDevice()
            #TODO need to do additional checking whether the device setting is actually success!!!!!!!!
            #step2: send reply message back to the UI
            topic = '/agent/ui/identify_response/'+device_type+'/'+_topic_Agent_UI_tail
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            }
            if identifyDeviceResult:
                message = 'success'
            else:
                message = 'failure'
            self.publish(topic, headers, message)



    Agent.__name__ = 'LightingAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(LightingAgent,
                       description='Lighting agent',
                       argv=argv)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
