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

import logging
import sys
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
import os
import json
import settings
import datetime
import psycopg2
from bemoss_lib.communication.Email import EmailService
from bemoss_lib.communication.sms import SMSService
import ast
import re
from bemoss_lib.utils import find_own_ip
import subprocess
import base64

utils.setup_logging()
_log = logging.getLogger(__name__)
Agents_DIR = settings.Agents_DIR
clock_time = 20 #frequency of polling nodes
Agents_Launch_DIR = settings.Agents_Launch_DIR
building_name = settings.PLATFORM['node']['building_name']
db_database = settings.DATABASES['default']['NAME']

host_ip_address = find_own_ip.getIPs()[-1] #use the last IP in the list for host ip

debug_agent = False
host_name = settings.PLATFORM['node']['name']
db_host = settings.DATABASES['default']['HOST']
db_port = settings.DATABASES['default']['PORT']
db_user = settings.DATABASES['default']['USER']
db_password = settings.DATABASES['default']['PASSWORD']
db_table_node_info = settings.DATABASES['default']['TABLE_node_info']
db_table_node_device = settings.DATABASES['default']['TABLE_node_device']
db_table_device_info = settings.DATABASES['default']['TABLE_device_info']
db_table_active_alert = settings.DATABASES['default']['TABLE_active_alert']
db_table_device_type = settings.DATABASES['default']['TABLE_device_type']
db_table_bemoss_notify = settings.DATABASES['default']['TABLE_bemoss_notify']
db_table_alerts_notificationchanneladdress = settings.DATABASES['default']['TABLE_alerts_notificationchanneladdress']
db_table_temp_time_counter = settings.DATABASES['default']['TABLE_temp_time_counter']
db_table_temp_failure_time = settings.DATABASES['default']['TABLE_temp_failure_time']
db_table_priority = settings.DATABASES['default']['TABLE_priority']
if settings.PLATFORM['node']['type'] == "core": node_monitor_time = settings.PLATFORM['node']['node_monitor_time']
else: node_monitor_time = 60000000  # arbitrary large number since it's not required for type "node"
if settings.PLATFORM['node']['type'] == "core": node_offline_timeout = settings.PLATFORM['node']['node_offline_timeout']
else: node_offline_timeout = 60000000  # arbitrary large number since it's not required for type "node"

# 5. @params notification_info
send_notification = True
email_fromaddr = settings.NOTIFICATION['email']['fromaddr']
email_recipients = settings.NOTIFICATION['email']['recipients']
email_username = settings.NOTIFICATION['email']['username']
email_password = settings.NOTIFICATION['email']['password']
email_mailServer = settings.NOTIFICATION['email']['mailServer']
notify_heartbeat = settings.NOTIFICATION['heartbeat']

class NetworkAgent(PublishMixin, BaseAgent):
    def __init__(self, config_path, **kwargs):
        super(NetworkAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        def get_config(name):
            try:
                kwargs.pop(name)
            except KeyError:
                return self.config.get(name, '')
        self.agent_id = get_config('agent_id')
        self.building_name = building_name
        self.host_ip_address = host_ip_address
        self.db_host = db_host
        self.host_name = host_name
        _launch_file = os.path.join(Agents_DIR+"MultiBuilding/multibuildingagent.launch.json")
        try:
            with open(_launch_file, 'r') as f:
                self.multi_node_data = json.load(f)
        except IOError:
            print "No Multibuilding Launch file yet"
        else:
            self.multi_node_pub_addr = self.multi_node_data['building-publish-address']
            self.multi_node_sub_addr = self.multi_node_data['building-subscribe-address']

            self.connected_nodes = list()
            self.received_nodes_status_reply = list()
            self.first_time_check_node_status = True
            for k, v in self.multi_node_data['hosts'].items():
                if self.multi_node_data['hosts'][k]['pub'] == self.multi_node_pub_addr and \
                   self.multi_node_data['hosts'][k]['sub'] == self.multi_node_sub_addr:
                    # host_name is used to identify this node for multi-node communication
                    self.host_name = k
                    self.host_location = k
                    self.host_building_name = self.multi_node_data['hosts'][k]['building_name']
                    self.host_building_name = self.multi_node_data['hosts'][k]['building_name']
                    self.host_zone_id = int(self.multi_node_data['hosts'][k]['zone_id'])
                    self.host_mac_address = self.multi_node_data['hosts'][k]['mac_address']
                    self.host_type = self.multi_node_data['hosts'][k]['type']

                else:
                    self.connected_nodes.append(k)

                if self.multi_node_data['hosts'][k]['type'] == "core":
                        self.core_location = k
                        self.db_host = self.multi_node_data['hosts'][k]['pub'].split("//")[1].split(":")[0]
                        print "Network Agent >> host name for multi-node communication subscription is {}".format(self.core_location)

        try:
            self.con = psycopg2.connect(host=self.db_host, port=db_port, database=db_database, user=db_user,
                                        password=db_password)
            self.cur = self.con.cursor()  # open a cursor to perfomm database operations
            print("{} connects to the database name {} successfully".format(self.agent_id, db_database))
        except Exception as er:
            print er
            print("ERROR: {} fails to connect to the database name {}".format(self.agent_id, db_database))
        self.cur.execute("SELECT associated_zone, mac_address FROM "+db_table_node_info+" WHERE ip_address=%s", (self.host_ip_address,))
        if self.cur.rowcount != 0:
            row = self.cur.fetchone()
            self.host_zone_id = int(row[0])
            self.host_mac_address = row[1]
            print "host_zone_id "+str(self.host_zone_id)
        else:
            print "no host zone id"
        self.time_sent_notifications = {}
        self.notify_heartbeat = notify_heartbeat

    def setup(self):
        super(NetworkAgent, self).setup()
        self.multi_node_sub_topic("device_move")
        self.multi_node_sub_topic("device_stop")
        self.multi_node_sub_topic("ask_to_move_device")
        self.multi_node_sub_topic("ui_agent")
        self.multi_node_sub_topic("agent_ui")
        self.multi_node_sub_topic("check_status")
        self.multi_node_sub_topic("check_status_response")
        self.multi_node_sub_topic("device_stop")

    @periodic(60)
    def sendScheduleFiles(self):
        if self.host_type == 'node':
            return
        if len(self.connected_nodes) == 0:
            return
        path = os.path.expanduser('~/workspace/bemoss_web_ui')
        os.chdir(path)
        os.system('pg_dump -U admin -h localhost bemossdb -f ./resources/bemossdb.sql')
        os.system('rm -f resources.zip ')
        os.system('zip -r resources.zip  resources')
        for replied_node in self.received_nodes_status_reply:
            print 'BEMOSS CORE >> replied_node {}'.format(replied_node)
            reply_node_mac = self.multi_node_data['hosts'][replied_node]['mac_address']
            self.cur.execute("SELECT node_status, associated_zone FROM "+db_table_node_info+" WHERE mac_address=%s",
                             (reply_node_mac,))
            if self.cur.rowcount != 0:
                row = self.cur.fetchone()
                node_status = row[0]
                replied_node_zone_id = row[1]
                if node_status != "OFFLINE":
                    self.sendFiles(path+'/resources.zip',path+'/resources.zip',replied_node_zone_id)
                else:
                    print "Cannot send file. Node offline"
            else:
                print 'Node status could not be found in database'
                continue

    @matching.match_start('/agent/networkagent/')
    def on_match_agent_networkagent(self, topic, headers, message, match):
        if debug_agent:
            print "{} >> received the message at {}".format(self.agent_id, datetime.datetime.now())
            print "Topic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
        command = topic.split("/")[3]
        if command == "file_to_core":
            data = json.loads(message[0])
            self.sendFiles(data['source_path'],data['destination_path'],'999')

    def sendFiles(self,source_file_path,destination_file_path,zone_id):
        self.cur.execute("SELECT node_type, mac_address, building_name, node_status FROM "+db_table_node_info+" WHERE associated_zone=%s", (zone_id,))
        if self.cur.rowcount == 0:
            print "zone not exits"
            return

        row = self.cur.fetchone()
        new_zone_node_type = row[0]
        new_zone_device_mac = row[1]
        new_zone_building_name = row[2]
        new_zone_node_status = row[3]
        print "{} >> new_zone_node_type: {} new_zone_device_mac {}"\
        .format(self.agent_id, new_zone_node_type, new_zone_device_mac)
        #check status of remote_note before move agent
        if new_zone_node_status == "OFFLINE":
            print "node looks offline. Can't send file"

        print "{} >> File to send is {}".format(self.agent_id, source_file_path)
        #0. update device table to a new zone

        with open(source_file_path, 'r') as f:
            file_content = f.read()


        # 2. gather information for multi-node sending
        message = {'path':destination_file_path,'b64encoded_content':base64.b64encode(file_content)}
        node_location = new_zone_building_name+'/'+"".join(new_zone_device_mac.split(':'))
        topic_to_send = 'building/send/'+node_location+'/file_move'
        print "{}: send file {} to nodes".format(self.agent_id, source_file_path)
        message_to_send = message
        # 3. send launch file to a remote note
        self.publish_multi_node(topic_to_send, message_to_send)
        # 4. stop agent for that device running in this node
        #TODO publish success message back to UI


    def sendStopAgentRequest(self,agent_id,zone_id):
        self.cur.execute("SELECT node_type, mac_address, building_name, node_status FROM "+db_table_node_info+" WHERE associated_zone=%s", (zone_id,))
        if self.cur.rowcount == 0:
            print "zone does not exits"
            return

        row = self.cur.fetchone()
        new_zone_node_type = row[0]
        new_zone_device_mac = row[1]
        new_zone_building_name = row[2]
        new_zone_node_status = row[3]
        if debug_agent:
            print "{} >> new_zone_node_type: {} new_zone_device_mac {}"\
        .format(self.agent_id, new_zone_node_type, new_zone_device_mac)
        #check status of remote_note before move agent
        if new_zone_node_status == "OFFLINE":
            print "node looks offline. Trying to stop agents in it anyway"

        if debug_agent:
            print "{} >> device to stop is {}".format(self.agent_id, agent_id)

        _launch_file_path = os.path.join(Agents_Launch_DIR+agent_id+".launch.json")
        with open(_launch_file_path, 'r') as f:
            launch_file_to_move = json.load(f)

        agent_id = launch_file_to_move['agent_id']
        node_location = new_zone_building_name+'/'+"".join(new_zone_device_mac.split(':'))
        topic_to_send = 'building/send/'+node_location+'/device_stop'
        if debug_agent:
            print "{} send topic {} to stop device".format(self.agent_id, topic_to_send)
        message_to_send = launch_file_to_move
        self.publish_multi_node(topic_to_send, message_to_send)

    def sendStartAgentRequest(self,to_start_agent_id,new_zone_id):
        self.cur.execute("SELECT node_type, mac_address, building_name, node_status FROM "+db_table_node_info+" WHERE associated_zone=%s", (new_zone_id,))
        if self.cur.rowcount == 0:
            print "new zone does not exits"
            return

        row = self.cur.fetchone()
        new_zone_node_type = row[0]
        new_zone_device_mac = row[1]
        new_zone_building_name = row[2]
        new_zone_node_status = row[3]
        if debug_agent:
            print "{} >> new_zone_node_type: {} new_zone_device_mac {}"\
            .format(self.agent_id, new_zone_node_type, new_zone_device_mac)

        #check status of remote_note before move agent
        if new_zone_node_status == "OFFLINE":
            print "{} >> multi-node device agent migration FAILED !!, tried to start agent in OFFLINE node: {}"\
            .format(self.agent_id, new_zone_id)
            #TODO publish fail message back to UI
            return

        if debug_agent:
            print "{} >> device to move is {}".format(self.agent_id, to_start_agent_id)


        _launch_file_path = os.path.join(Agents_Launch_DIR+to_start_agent_id+".launch.json")
        with open(_launch_file_path, 'r') as f:
            launch_file_to_move = json.load(f)
            launch_file_to_move['db_host'] = self.host_ip_address
            launch_file_to_move['zone_id'] = new_zone_id
            #change building_name in launch file to move
            launch_file_to_move['building_name'] = new_zone_building_name

        #gather information for multi-node sending
        agent_id = launch_file_to_move['agent_id']
        node_location = new_zone_building_name+'/'+"".join(new_zone_device_mac.split(':'))
        topic_to_send = 'building/send/'+node_location+'/device_move'
        print "{} send topic {} to start device".format(self.agent_id, topic_to_send)
        message_to_send = launch_file_to_move
        #send launch file to a remote note
        self.publish_multi_node(topic_to_send, message_to_send)
        #TODO publish success message back to UI

    def migrateAgent(self, agent_id, previous_zone, new_zone):

        #first check if the agent_id is valid, and its in the previous zone
        self.cur.execute("SELECT current_zone_id FROM "+db_table_node_device+" WHERE device_id=%s",
                         (agent_id,))
        if self.cur.rowcount != 0:
            current_zone = self.cur.fetchone()[0]

            if str(current_zone) != str(previous_zone):
                print "Agent not found in the said previous zone. Skipping migration"
                return
        else:
            print "Agent Not found in table"
            return

        #Next update its current_zone = new_zone
        #TODO Make this update only if the migration is successful and acknowledgement is got from other node
        self.cur.execute("UPDATE "+db_table_node_device+
        " SET current_zone_id=(%s),"
        "date_move=(%s) WHERE device_id=(%s)",
        (new_zone,datetime.datetime.now(), agent_id))
        self.con.commit()

        #Find the type of device being migrated. Eg. thermostat, plugload etc
        self.cur.execute("SELECT device_type FROM "+db_table_device_info+" WHERE device_id=%s",
                         (agent_id,))
        if self.cur.rowcount != 0:
            _device_to_migrate_type = self.cur.fetchone()[0]
            device_table = _device_to_migrate_type #the device table is named after device type
            if debug_agent:
                print "_device_to_migrate_type "+str(_device_to_migrate_type)

            #Update the current zone of the device on the database
            self.cur.execute("UPDATE "+device_table+
                         " SET zone_id=(%s) WHERE "+device_table+"_id=(%s)",
                         (new_zone, agent_id ))
            self.con.commit()
            if debug_agent:
                print "device_table zone changed"

        if new_zone == self.host_zone_id:
            _launch_file_path = os.path.join(Agents_Launch_DIR+agent_id+".launch.json")
            if debug_agent:
                print "_launch_file_path "+_launch_file_path
            with open(_launch_file_path, 'r') as f:
                launch_file_at_core = json.load(f)
                launch_file_at_core['zone_id'] = self.host_zone_id
                launch_file_at_core['building_name'] = self.host_building_name

            self.launch_agent(Agents_Launch_DIR, agent_id, _launch_file_path)
            if previous_zone != new_zone: #allow for both zones to be the same.
                self.sendStopAgentRequest(agent_id,previous_zone)

        elif previous_zone == self.host_zone_id:
            try:
                self.sendStartAgentRequest(agent_id,new_zone)
            except:
                pass
            else:
                os.system("volttron-ctl stop --tag " + agent_id)
        else:
            try:
                self.sendStartAgentRequest(agent_id,new_zone)
            except:
                pass
            else:
                if previous_zone != new_zone: #allow for plain start of new agent by specifying same start/end zone
                    self.sendStopAgentRequest(agent_id,previous_zone)


    @periodic(clock_time)
    def nodeHeartbeat(self):
        if self.host_type == "core":
            _launch_file = os.path.join(Agents_DIR+"MultiBuilding/multibuildingagent.launch.json")
            with open(_launch_file, 'r') as f:
                self.multi_node_data = json.load(f)
            self.connected_nodes = list()
            for k, v in self.multi_node_data['hosts'].items():
                if self.multi_node_data['hosts'][k]['type'] == "core":
                    pass
                else:
                    self.connected_nodes.append(k)
            for node_location in self.connected_nodes:
                if debug_agent:
                    print 'connected nodes = {}'.format(len(self.connected_nodes))
                    print 'node_location ' + node_location
                topic_to_send = 'building/send/'+node_location+'/check_status'
                message_to_send = "check status"
                self.publish_multi_node(topic_to_send, message_to_send)


    @periodic(node_monitor_time)
    def check_node_status(self):
        #This is the job of core only
        if self.host_type != "core" or  len(self.connected_nodes) == 0:
            if debug_agent:
                print "Nothing to be done. No connected nodes, or I am node"
            return
        #start with the assumption that non-of the nodes have replied to check_status querry
        self.not_replied_nodes = self.connected_nodes

        if debug_agent:
            print 'BEMOSS CORE >> num nodes replied to check node status message = {}'.format(len(self.received_nodes_status_reply))

        for replied_node in self.received_nodes_status_reply:
            self.not_replied_nodes.remove(replied_node)
            if debug_agent:
                print 'BEMOSS CORE >> replied_node {}'.format(replied_node)

            #check the replied node status in database
            reply_node_mac = self.multi_node_data['hosts'][replied_node]['mac_address']
            self.cur.execute("SELECT node_status, associated_zone FROM "+db_table_node_info+" WHERE mac_address=%s",
                             (reply_node_mac,))
            if self.cur.rowcount != 0:
                row = self.cur.fetchone()
                replied_node_old_status = row[0]
                replied_node_zone_id = int(row[1])
            else:
                continue

            if replied_node_old_status == "OFFLINE": #this means it recently became online
                self.cur.execute("UPDATE "+db_table_node_info+" SET node_status=(%s),last_scanned_time=(%s)"
                                 "WHERE mac_address=(%s)",
                                 ("ONLINE", datetime.datetime.now(), reply_node_mac))
                self.con.commit()
                #recently online node. Transfer back the agents
                self.cur.execute("SELECT device_id FROM "+db_table_node_device+" WHERE previous_zone_id=%s",
                             (replied_node_zone_id,))
                if self.cur.rowcount != 0:
                    rows = self.cur.fetchall()
                    for row in rows:
                        if debug_agent:
                            print "BEMOSS CORE >> device to be migrated to recenlty online node is {}".format(row[0])
                        _device_id_to_migrate = row[0]
                        self.migrateAgent(_device_id_to_migrate,self.host_zone_id,replied_node_zone_id)

        for not_replied_node in self.not_replied_nodes:
            if debug_agent:
                print 'BEMOSS CORE >> not_replied_node {}'.format(not_replied_node)
            not_reply_node_mac = self.multi_node_data['hosts'][not_replied_node]['mac_address']
            self.cur.execute("SELECT node_status, associated_zone FROM "+db_table_node_info+" WHERE mac_address=%s",
                             (not_reply_node_mac,))
            if self.cur.rowcount != 0:
                row = self.cur.fetchone()
                not_replied_node_status = row[0]
                not_replied_node_zone_id = int(row[1])
            else:
                print "Node not found"
                continue

            if not_replied_node_status == "ONLINE": #status still online in databse. Make it offline.
                #x = 3/0
                print not_reply_node_mac
                self.agent_connectivity_detection(not_reply_node_mac)
                self.cur.execute("UPDATE "+db_table_node_info+" SET node_status=(%s), last_scanned_time=(%s),"
                                                              "last_offline_time=(%s) WHERE mac_address=(%s)",
                                 ("OFFLINE", datetime.datetime.now(), datetime.datetime.now(), not_reply_node_mac))
                self.con.commit()
                continue #NOTHING more TO BE done on this node

            if not_replied_node_status != "OFFLINE":
                continue #node status must be OFFLINE if not online

            self.cur.execute("UPDATE "+db_table_node_info+" SET last_scanned_time=(%s)"
                                                          "WHERE mac_address=(%s)",
                             (datetime.datetime.now(), not_reply_node_mac))
            self.con.commit()
            self.cur.execute("SELECT last_offline_time FROM "+db_table_node_info+" WHERE mac_address=%s",
                         (not_reply_node_mac,))
            if self.cur.rowcount == 0:
                continue

            row = self.cur.fetchone()
            not_replied_node_last_offline_time = row[0]

            if (datetime.datetime.now() - not_replied_node_last_offline_time.replace(tzinfo=None)).seconds < node_offline_timeout:
                continue #skip if not offline for long enough time
            if debug_agent:
                print "BEMOSS CORE >> node at this location {} has been offline for more than timeout: {} seconds"\
                .format(not_replied_node, node_offline_timeout)

            # core pull offline node devices
            self.cur.execute("SELECT device_id FROM "+db_table_node_device+" WHERE current_zone_id=%s",
                 (not_replied_node_zone_id,))
            if self.cur.rowcount == 0:
                continue

            rows = self.cur.fetchall()
            for row in rows:
                if debug_agent:
                    print "BEMOSS CORE >> device to be migrated from offline node is {}".format(row[0])
                _device_id_to_migrate = row[0]
                self.migrateAgent(_device_id_to_migrate,not_replied_node_zone_id,self.host_zone_id)


        self.received_nodes_status_reply = list()
            # self.status_node_location = {"node_location":node_location, "status":}

    def agent_connectivity_detection(self, agent_id):
        print "INSIDE agent_connectivity_detection"
        _email_subject="Check BEMOSS Notifications"
        self.cur.execute("SELECT id FROM " + db_table_active_alert + " WHERE event_trigger_id=%s", ('4',))
        # Active Alert detected
        if self.cur.rowcount != 0:
            self._active_alert_id = self.cur.fetchone()[0]
            print self._active_alert_id
            print "The Network Agent has Active alert in DB"
            _agent_offline_msg = '#Attention: BEMOSS Node {} has gone OFFLINE!!!'.format(agent_id)
            self.cur.execute(
                "SELECT id FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
                (str(self._active_alert_id), agent_id,))
            # If this is the first detected violation
            print self.cur.rowcount
            if self.cur.rowcount == 0:
                print "first violation detected"
                # create counter in DB
                self.cur.execute(
                    "INSERT INTO " + db_table_temp_time_counter + " VALUES(DEFAULT,%s,%s,%s,%s,%s)",
                    (self._active_alert_id, agent_id, '0', '0', '0'))
                self.con.commit()
                self.send_device_notification_db(_agent_offline_msg, self._active_alert_id, agent_id)

                # Send email if exist
                self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'1'))
                if self.cur.rowcount != 0:
                    self._alert_email = self.cur.fetchall()
                    for single_email_1 in self._alert_email:
                        print single_email_1[0]
                        self.send_device_notification_email(single_email_1[0], agent_id)

                # Send SMS if provided by user
                self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'2'))
                if self.cur.rowcount != 0:
                    self._alert_sms_phone_no = self.cur.fetchall()
                    for single_number in self._alert_sms_phone_no:
                        print single_number[0]
                        self.send_device_notification_sms(single_number[0], _email_subject)
            else:
                self.priority_counter(self._active_alert_id, _agent_offline_msg, agent_id, _email_subject)
        else:
            print "there is no active alert for Network Agent"

    def priority_counter(self, _active_alert_id, _agent_offline_msg, agent_id, email_subject_node):
        # find the priority counter limit then compare it with priority_counter in priority table
        # if greater than the counter limit then send notification and reset the value
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

        # Find the priority limit from the priority table
        self.cur.execute(
            "SELECT priority_counter FROM " + db_table_priority + " WHERE id=%s",
            (str(self.priority_id),))
        self.priority_limit = self.cur.fetchone()[0]
        self.con.commit()

        # If the counter reaches the limit
        if int(self.priority_count) > int(self.priority_limit):
            # self._no_notifications_sent = int(self._no_notifications_sent) + 1
            self.send_device_notification_db(_agent_offline_msg, _active_alert_id, agent_id)
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
                    self.send_device_notification_email(single_email_1[0], agent_id)

            # Send SMS if provided by user
            self.cur.execute("SELECT notify_address FROM " + db_table_alerts_notificationchanneladdress + " WHERE active_alert_id=%s AND notification_channel_id=%s",(self._active_alert_id,'2'))
            if self.cur.rowcount != 0:
                self._alert_sms_phone_no = self.cur.fetchall()
                for single_number in self._alert_sms_phone_no:
                    print single_number[0]
                    self.send_device_notification_sms(single_number[0], email_subject_node)
        else:
            self.priority_count = int(self.priority_count) + 1
            self.cur.execute(
                "UPDATE " + db_table_temp_time_counter + " SET priority_counter=%s WHERE alert_id=%s AND device_id=%s",
                (str(self.priority_count), str(_active_alert_id), agent_id,))

    def send_device_notification_db(self, _agent_offline_msg, _active_alert_id, agent_id):
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
                         (_agent_offline_msg, datetime.datetime.now(), 'Alert', str(self.priority_level)))
        self.con.commit()

        # Find the number of notifications sent for the same alert and device
        self.cur.execute(
            "SELECT no_notifications_sent FROM " + db_table_temp_time_counter + " WHERE alert_id=%s AND device_id=%s",
            (str(_active_alert_id), str(agent_id),))
        self._no_notifications_sent = self.cur.fetchone()[0]
        self.con.commit()
        print self._no_notifications_sent
        self._no_notifications_sent = int(self._no_notifications_sent) + 1
        print self._no_notifications_sent
        self.cur.execute(
            "UPDATE " + db_table_temp_time_counter + " SET no_notifications_sent=%s WHERE alert_id=%s AND device_id=%s",
            (str(self._no_notifications_sent), str(_active_alert_id), agent_id,))
        self.con.commit()

    def send_device_notification_email(self, _active_alert_email, agent_id):
        _email_subject = '#Attention: BEMOSS Device {} has gone OFFLINE!!!'.format(agent_id)
        # _email_text = 'Here is the detail of device status\n' + str(_tampering_device_msg) \
        _email_text = 'The BEMOSS Device {} has gone OFFLINE!!!'.format(agent_id)
        emailService = EmailService()

        # Send Email
        emailService.sendEmail(email_fromaddr, _active_alert_email, email_username,
                               email_password, _email_subject, _email_text, email_mailServer)


    def send_device_notification_sms(self, _active_alert_phone_number_misoperation, _sms_subject):
            print "INSIDE send_device_notification_sms"
            print _active_alert_phone_number_misoperation
            smsService = SMSService()
            smsService.sendSMS(email_fromaddr, _active_alert_phone_number_misoperation, email_username, email_password, _sms_subject, email_mailServer)


    # Behavior to listen to message from UI when user change zone of a device
    @matching.match_start('/ui/networkagent/')
    def on_match_ui_networkagent(self, topic, headers, message, match):
        if debug_agent:
            print "{} >> received the message at {}".format(self.agent_id, datetime.datetime.now())
            print "Topic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
        command = topic.split("/")[6]
        approval_status = topic.split("/")[7]
        if command == "change":
            to_move_device_id = topic.split("/")[3]
            previous_zone_id = int(topic.split("/")[4])
            new_zone_id = int(topic.split("/")[5])
            #delte if already existing entry
            self.cur.execute("SELECT current_zone_id FROM "+db_table_node_device+ " WHERE device_id=%s",  (to_move_device_id,))
            if self.cur.rowcount == 0:
                #No need to delete since the entry doesn't exists. But doing anyway
                self.cur.execute("DELETE FROM "+db_table_node_device+" WHERE device_id=%s", (to_move_device_id,))
                # update node_device_table with the new zone of a device
                self.cur.execute("INSERT INTO "+db_table_node_device+" (device_id, previous_zone_id,current_zone_id,date_move) "
                                                                     "VALUES(%s,%s,%s,%s)",
                                 (to_move_device_id, new_zone_id, previous_zone_id, datetime.datetime.now()))
                self.con.commit()
            else:
                self.cur.execute("UPDATE "+db_table_node_device+
        " SET previous_zone_id=(%s),current_zone_id=(%s),"
        "date_move=(%s) WHERE device_id=(%s)",
        (new_zone_id, previous_zone_id, datetime.datetime.now(), to_move_device_id))
                self.con.commit()
            try:
                if approval_status == "APR":
                    self.migrateAgent(to_move_device_id,previous_zone_id,new_zone_id)
                else:
                    #Not approved, means made pending or made non-bemoss
                    self.sendStopAgentRequest(to_move_device_id,previous_zone_id)
                    pass
                #TODO publish success message back to UI

            except:
                pass
        elif command == "stop":
            to_move_device_id = topic.split("/")[3]
            previous_zone_id = int(topic.split("/")[4])
            new_zone_id = int(topic.split("/")[5])
            #ususally both zone should point to same zone. If not, then both will be stopped.
            self.sendStopAgentRequest(to_move_device_id,previous_zone_id)
            self.sendStopAgentRequest(to_move_device_id,new_zone_id)
        else:
            pass

    # Behavior to listen to message from MultiBuilding Agent
    @matching.match_start('building/recv/')
    def on_match_building_recv(self, topic, headers, message, match):
        if debug_agent:
            print "Topic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
        command = topic.split("/")[4]
        data = json.loads(message[0])
        if command == "device_move":
            agent_id = data['agent_id']
            _launch_file = os.path.join(Agents_Launch_DIR+agent_id+".launch.json")
            with open(_launch_file, 'w') as outfile:
                json.dump(data, outfile, indent=4, sort_keys=True)
            self.launch_agent(Agents_Launch_DIR, agent_id,_launch_file)
        elif command == "device_stop":
            agent_id = data['agent_id']
            os.system("volttron-ctl stop --tag " + agent_id)

        elif command == 'file_move':
            path = data['path']
            content = base64.b64decode(data['b64encoded_content'])
            newpath = os.path.expanduser(re.sub(r'(.*)/workspace','~/workspace',path))
            with open(newpath,'w') as f:
                f.write(content)

            if 'bemoss_web_ui/resources.zip' in newpath:
                folderpath = newpath.replace('/resources.zip','')
                os.chdir(folderpath)
                os.system('unzip -o resources.zip')
                os.system('psql -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid();"')
                os.system('dropdb -U admin -h localhost bemossdb') #This step requires all connections to be closed
                os.system('createdb bemossdb -O admin')
                os.system('psql bemossdb < resources/bemossdb.sql')

        elif command == "check_status_response":
            if debug_agent:
                print "check_status_response"
                print "Message: {message}".format(message=message)
            response_status = data['status']
            response_node = data['node_location']
            if response_node not in self.received_nodes_status_reply and response_status == "ONLINE":
                self.received_nodes_status_reply.append(response_node)
        elif command == "ui_agent":
            ui_message = json.loads(message[0])
            _topic_to_send =  ui_message["topic"]
            try:
                _message_to_send = ast.literal_eval(ui_message["message"])
            except:
                _message_to_send = ui_message["message"]
            if debug_agent:
                print "ui_agent republish message {}".format(_message_to_send)
            self.publish_ipc(_topic_to_send, _message_to_send)

        elif command == "ui_app":

            ui_message = json.loads(message[0])
            _topic_to_send =  ui_message["topic"]
            print "ui_app republish topic {}".format(_topic_to_send)
            try:
                _message_to_send = ast.literal_eval(ui_message["message"])
            except:
                _message_to_send = ui_message["message"]
            print "ui_app republish message {}".format(_message_to_send)
            self.publish_ipc(_topic_to_send, _message_to_send)

        elif command == "agent_ui":
            ui_message = json.loads(message[0])
            _topic_to_send =  ui_message["topic"]
            #convert received message from unicode dict to dict
            try:
                _message_to_send = ast.literal_eval(ui_message["message"])
            except:
                _message_to_send = ui_message["message"]
            if debug_agent:
                print "network agent >> type _message_to_send {}".format(type(_message_to_send))
                print "network agent >> _message_to_send " + str(_message_to_send)
                print "agent_ui republish message {}".format(_message_to_send)
            self.publish_ipc(_topic_to_send, _message_to_send)
        elif command == "check_status":
            if debug_agent:
                print "sending Response"
            _topic_to_send = 'building/send/'+self.core_location+'/check_status_response'
            _message_to_send = {"node_location": self.host_location,"status":"ONLINE"}
            self.publish_multi_node(_topic_to_send, _message_to_send)
        else:
            pass
    @matching.match_start('/ui/app/')
    def on_match_ui_app(self, topic, headers, message, match):
        print "Topic: {topic}".format(topic=topic)
        print "Headers: {headers}".format(headers=headers)
        print "Message: {message}\n".format(message=message)
        app_name = str(topic.split("/")[3])
        device_type = re.match(r'([a-z]*)_scheduler',app_name).groups()[0]
        device_agent_id = str(topic.split("/")[4])


        self.cur.execute("SELECT zone_id FROM "+ device_type + " WHERE "+device_type+"_id=%s",
                                 (device_agent_id,))
        if self.cur.rowcount != 0:
            row = self.cur.fetchone()
            zone_to_send = row[0]

        #check if zone_to_send is actually another node
        self.cur.execute("SELECT building_name, mac_address FROM "+db_table_node_info+" WHERE associated_zone=%s",
                         (zone_to_send,))
        if self.cur.rowcount != 0:
            row = self.cur.fetchone()
            zone_to_send_building_name = row[0]
            zone_to_send_mac = row[1]
            if zone_to_send_mac != self.host_mac_address:
                print "multi-node communication -> forwarding message to another node"
                node_location = zone_to_send_building_name+'/'+"".join(zone_to_send_mac.split(':'))
                topic_to_send = 'building/send/'+node_location+'/ui_app'
                # _message = json.loads(message)
                _message = message[0]
                message_to_send = {
                                    "topic": topic,
                                    # "headers": str(headers),
                                    "message": _message
                                   }
                # forward UI message to another node
                self.publish_multi_node(topic_to_send, message_to_send)
            else:
                print "this message is published in the same node (Macaddress is same). However zone id is different. Check Database"
        else:
            print "Unavailable zone for the app. check device agent table"


    # Behavior to listen to message UI try to communicate with agent
    @matching.match_start('/ui/agent/')
    def on_match_ui_agent(self, topic, headers, message, match):
        if debug_agent:
            print "Topic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
        building_to_send = str(topic.split("/")[3])  # TODO check this
        zone_to_send = str(topic.split("/")[4])
        try:
            command = str(topic.split("/")[7])
            #check if command is correct
            if command == 'device_status' or 'update' or 'identify':
                _correct_passing_command = True
            else: _correct_passing_command = False
            if _correct_passing_command and building_to_send == building_name :
                #check if zone_to_send is actually another node
                if zone_to_send == self.host_zone_id:
                    print "{} this message is published in the same node"
                else:
                    #check if zone_to_send is actually another node
                    self.cur.execute("SELECT building_name, mac_address FROM "+db_table_node_info+" WHERE associated_zone=%s",
                                     (zone_to_send,))
                    if self.cur.rowcount != 0:
                        row = self.cur.fetchone()
                        zone_to_send_building_name = row[0]
                        zone_to_send_mac = row[1]
                        if zone_to_send_mac != self.host_mac_address:
                            print "multi-node communication -> forwarding message to another node"
                            node_location = zone_to_send_building_name+'/'+"".join(zone_to_send_mac.split(':'))
                            topic_to_send = 'building/send/'+node_location+'/ui_agent'
                            # _message = json.loads(message)
                            _message = message[0]
                            message_to_send = {
                                                "topic": topic,
                                                # "headers": str(headers),
                                                "message": _message
                                               }
                            # forward UI message to another node
                            self.publish_multi_node(topic_to_send, message_to_send)
                        else:
                            print "this message is published in the same node"
                    else:
                        print "this message is published in the same node"
            else: pass
        except:
            pass

    # Behavior to listen to message agent try to communicate with UI
    @matching.match_start('/agent/ui/')
    def match_agent_ui(self, topic, headers, message, match):
        building_to_send = str(topic.split("/")[3])  # TODO check this
        zone_to_send = str(topic.split("/")[4])
        # UI resides on core node, find core  and then republish the message
        if self.host_type != "core":
            if debug_agent:
                print "multi-node communication -> forwarding message to UI resides on the core node"
                print topic
            core_location = self.core_location
            topic_to_send = 'building/send/'+core_location+'/agent_ui'
            _message = message[0]
            if _message == "success":
                _message = str({"message": "success"})
            elif _message == "failure":
                _message = str({"message": "failure"})
            else:
                _message = message[0]
            print "agent_ui type(_message) {}".format(type(_message))
            print "agent_ui _message {}".format(_message)
            message_to_send = {
                                "topic": topic,
                                # "headers": str(headers),
                                "message": _message
                               }
            self.publish_multi_node(topic_to_send, message_to_send)
        else:
            # "This is the bemoss core node, there is no need to republish a message"
            pass

    # @periodic(settings.HEARTBEAT_PERIOD)
    def publish_multi_node(self, topic_to_send, message_to_send):
        # now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            'AgentID': self.agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            # headers_mod.DATE: now,
        }
        message = json.dumps(message_to_send)
        self.publish(topic_to_send, headers, message)

    def publish_ipc(self, topic_to_send, message_to_send):
        # now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            'AgentID': self.agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            # headers_mod.DATE: now,
        }
        # message = json.dumps(['foo', {'bar': ('baz', None, 1.0, 2)}])
        # message = json.dumps({"topic": "topic","headers":"headers","message":"message" })
        message = json.dumps(message_to_send)
        # message = json.loads(message_to_send)
        # self.publish('building/send/campus/platform2/test_topic', headers, message)
        self.publish(topic_to_send, headers, message)

    def multi_node_sub_topic(self, topic):
        # now = datetime.utcnow().isoformat(' ') + 'Z'
        # topic = "test_topic"
        headers = {
            'AgentID': self.agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            # headers_mod.DATE: now,
        }
        message = "Multi-node topic subscription message from node"
        host_name = self.host_name
        multi_node_sub_topic = 'subscriptions/add/building/recv/'+host_name+'/'+topic
        # multi_node_sub_topic = 'subscriptions/add/building/recv/campus/platform1/test_topic'
        self.publish(multi_node_sub_topic, headers, message)
        print "Network Agent>> subscribe to multi-node topic: {}".format(topic)

    def launch_agent(self, dir, agent_id, _launch_file):
        #_launch_file = os.path.join(dir, launch_file)
        def is_agent_installed(agent_id):
            statusreply = subprocess.check_output('~/workspace/bemoss_os/env/bin/volttron-ctl status',shell=True)
            statusreply = statusreply.split('\n')
            agent_installed = False
            reg_search_term = " "+agent_id+" "
            for line in statusreply:
                #print(line, end='') #write to a next file name outfile
                match = re.search(reg_search_term, line)
                if match:  # The agent for this device is running
                    agent_installed = True
                else:
                    pass
            return agent_installed

        with open(_launch_file, 'r') as infile:
            data=json.load(infile)
        agentname=data["type"]
        if not is_agent_installed(agent_id):
            os.system(#". env/bin/activate"
                          "volttron-ctl stop --tag " + agent_id+
                          ";volttron-pkg configure /tmp/volttron_wheels/"+agentname+"agent-0.1-py2-none-any.whl "+ _launch_file+
                          ";volttron-ctl install "+agent_id+"=/tmp/volttron_wheels/"+agentname+"agent-0.1-py2-none-any.whl"+
                          ";volttron-ctl start --tag " + agent_id +
                          ";volttron-ctl status")
        else:
            os.system(#". env/bin/activate"
                          "volttron-ctl stop --tag " + agent_id+
                          ";volttron-ctl start --tag " + agent_id +
                          ";volttron-ctl status")

        print "{} >> has successfully launched {} located in {}".format(self.agent_id, agent_id, dir)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.default_main(NetworkAgent,
                           description='network agent',
                           argv=argv)
    except Exception as e:
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass