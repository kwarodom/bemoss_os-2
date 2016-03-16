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
import importlib
import psycopg2
import sys
import json
import datetime
import time
import logging
import os
import re
from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
from urlparse import urlparse
import settings
import netifaces as ni
import ast
import subprocess

utils.setup_logging()  # setup logger for debugging
_log = logging.getLogger(__name__)

# Step1: Agent Initialization
def DeviceDiscoveryAgent(config_path, **kwargs):
    config = utils.load_config(config_path)  # load the config_path from devicediscoveryagent.launch.json
    def get_config(name):
        try:
            value = kwargs.pop(name)  # from the **kwargs when call this function
        except KeyError as er:
            print "keyError", er
            return config.get(name, '')

    # 1. @params agent
    agent_id = get_config('agent_id')
    device_scan_time = get_config('device_scan_time')
    device_scan_time_multiplier = get_config('device_scan_time_multiplier')
    headers = {headers_mod.FROM: agent_id}
    topic_delim = '/'  # topic delimiter

    # 3. @params agent & DB interfaces
    # @params DB interfaces
    db_database = settings.DATABASES['default']['NAME']
    db_host = settings.DATABASES['default']['HOST']
    db_port = settings.DATABASES['default']['PORT']
    db_user = settings.DATABASES['default']['USER']
    db_password = settings.DATABASES['default']['PASSWORD']
    db_table_device_info = settings.DATABASES['default']['TABLE_device_info']
    db_table_supported_devices = settings.DATABASES['default']['TABLE_supported_devices']


    # 4. @params devicediscovery agent setting
    device_monitor_time = settings.DEVICES['device_monitor_time']
    findWiFi = settings.FIND_DEVICE_SETTINGS['findWiFi']
    findWiFiHue = settings.FIND_DEVICE_SETTINGS['findWiFiHue']
    findWiFiWeMo = settings.FIND_DEVICE_SETTINGS['findWiFiWeMo']
    findBACnet = settings.FIND_DEVICE_SETTINGS['findBACnet']
    findModbus = settings.FIND_DEVICE_SETTINGS['findModbus']

    # @paths
    PROJECT_DIR = settings.PROJECT_DIR
    # Loaded_Agents_DIR = settings.Loaded_Agents_DIR
    # Autostart_Agents_DIR = settings.Autostart_Agents_DIR
    Applications_Launch_DIR = settings.Applications_Launch_DIR
    Agents_Launch_DIR = settings.Agents_Launch_DIR

    class Agent(PublishMixin, BaseAgent):

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            # Connect to database
            self.con = psycopg2.connect(host=db_host, port=db_port, database=db_database,
                                        user=db_user, password=db_password)
            self.cur = self.con.cursor()  # open a cursor to perform database operations

            sys.path.append(PROJECT_DIR)

            self.device_scan_time = device_scan_time
            self.device_discovery_start_time = datetime.datetime.now()
            self.scan_for_devices = True

            self.findWiFi = findWiFi
            self.findWiFiHue = findWiFiHue
            self.findWiFiWeMo = findWiFiWeMo
            self.findBACnet = findBACnet
            self.findModbus = findModbus

            self.discovery_list = list()

            # Finding devices by type:

            if self.findWiFi:
                self.discovery_list.append('CT30 V1.94')
                self.discovery_list.append('CT50 V1.94')
            if self.findWiFiWeMo:
                self.discovery_list.append('Socket')
                self.discovery_list.append('LightSwitch')
                self.discovery_list.append('Insight')
            if self.findWiFiHue: self.discovery_list.append('Philips hue bridge 2012')
            if self.findBACnet:
                self.discovery_list.append('LMPL-201')
                self.discovery_list.append('LMRC-212')
            if self.findModbus:
                self.discovery_list.append('VC1000')
                self.discovery_list.append('M1000')

            self.new_discovery=True
            self.no_new_discovery_count=0

            try:
                # Find total number of devices in the dashboard_device_info table
                self.cur.execute("SELECT * FROM "+db_table_device_info)
                self.device_num = self.cur.rowcount  # count no. of devices discovered by Device Discovery Agent
                print "{} >> there are existing {} device(s) in database".format(agent_id, self.device_num)

            except Exception as er:
                print "exception: ",er
                self.device_num = 0

        def setup(self):
            super(Agent, self).setup()
            self.valid_data = False
            '''Discovery Processes'''
            self.deviceDiscoveryBehavior(self.discovery_list)


        def deviceDiscoveryBehavior(self,discoverylist):
            print "Start Discovery Process--------------------------------------------------"
            # Update bemossdb miscellaneous and bemoss_notify tables with discovery start
            self.cur.execute("UPDATE miscellaneous SET value = 'ON' WHERE key = 'auto_discovery'")
            self.con.commit()
            self.cur.execute("INSERT INTO bemoss_notify VALUES(DEFAULT,%s,%s,%s)",('Plug and Play discovery process started',str(datetime.datetime.now()),'Discovery'))
            self.con.commit()

            # Send message to UI about discovery start
            topic = '/agent/ui/misc/bemoss/discovery_request_response'
            headers = {
                'AgentID': agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                # headers_mod.DATE: now,
                headers_mod.FROM: agent_id,
                headers_mod.TO: 'UI'
            }
            message = 'ON'
            message = message.encode(encoding='utf_8')
            self.publish(topic, headers, message)

            # Run Discovery Process
            while self.scan_for_devices:
                #run one discovery cycle for selected devices
                self.deviceScannerCycle(discoverylist)
                # keep track of consecutive discovery cycles with no new discovered device
                if not self.new_discovery:
                    self.no_new_discovery_count +=1
                else:
                    self.no_new_discovery_count = 0
                # Stop after some cycles
                if self.no_new_discovery_count >= 10:
                    self.scan_for_devices = False

                    # Update bemossdb miscellaneous and bemoss_notify tables with discovery end
                    self.cur.execute("UPDATE miscellaneous SET value = 'OFF' WHERE key = 'auto_discovery'")
                    self.con.commit()
                    self.cur.execute("INSERT INTO bemoss_notify VALUES(DEFAULT,%s,%s)",('Plug and Play discovery process complete',str(datetime.datetime.now())))
                    self.con.commit()

                    # Send message to UI about discovery end
                    topic = '/agent/ui/misc/bemoss/discovery_request_response'
                    headers = {
                        'AgentID': agent_id,
                        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                        # headers_mod.DATE: now,
                        headers_mod.FROM: agent_id,
                        headers_mod.TO: 'UI'
                    }
                    message = 'OFF'
                    message = message.encode(encoding='utf_8')
                    self.publish(topic, headers, message)

                    print "Stop Discovery Process--------------------------------------------------"
                    #self.device_scan_time *= device_scan_time_multiplier
                time.sleep(self.device_scan_time)


        #deviceScannerBehavior (TickerBehavior)
        def deviceScannerCycle(self,discoverylist):
            self.new_discovery=False
            print "Start Discovery Cycle--------------------------------------------------"
            print "{} >> device next scan time in {} sec".format(agent_id, str(self.device_scan_time ))
            print "{} >> start_time {}".format(agent_id, str(self.device_discovery_start_time))
            self.device_discovery_time_now = datetime.datetime.now()
            print "{} >> current time {}".format(agent_id, str(self.device_discovery_time_now))
            print "{} >> is trying to discover all available devices\n".format(agent_id)

            for discover_device_model in discoverylist:
                self.cur.execute("SELECT * from "+db_table_supported_devices
                                             +" where device_model=%s",(discover_device_model,))
                devicedetails = self.cur.fetchone()
                self.findDevicesbytype(devicedetails[2],devicedetails[3],devicedetails[4])

            print "Stop Discovery Cycle---------------------------------------------------"

        def findDevicesbytype(self, com_type, controller_type, discovery_type):
            #******************************************************************************************************

            self.cur.execute("SELECT device_type FROM "+db_table_device_info
                             +" WHERE device_type=%s", (controller_type,))
            num_Devices=self.cur.rowcount
            num_new_Devices = 0

            print "{} >> is finding available {} {} devices ...".format(agent_id,com_type,discovery_type)
            discovery_module = importlib.import_module("DeviceAPI.discoverAPI."+com_type)
            if (com_type == 'BACnet'):
                discovery_returns_ip = False
            else:
                discovery_returns_ip = True
            print "discovery_returns_ip {}".format(discovery_returns_ip)

            discovered_address = discovery_module.discover(discovery_type)
            if discovered_address == None:
                discovered_address = list()


            print discovered_address

            for address in discovered_address:

                print "address !!!!!!!!!!!!!!!!!!!!!!!!!! {}".format(address)
                if discovery_returns_ip:
                    ip_address = address
                    try:
                        macaddress = discovery_module.getMACaddress(discovery_type, ip_address)
                        print "macaddress: !!!!!!!!!!!! {}".format(macaddress)
                        if macaddress is not None:
                            _valid_macaddress = True
                        else:
                            _valid_macaddress = False
                    except Exception as er:
                        print "exception: ",er
                        _valid_macaddress = False
                else:  # this device does not return IP, wait until it get the right mac
                    try:

                        ip_address = ''  # specifically for cloud devices
                        macaddress = discovery_module.getMACaddress(discovery_type, ip_address)

                        # print 'type macaddress: {} and macaddress: {}'.format(type(macaddress),macaddress)
                        ip_address = None


                        if macaddress != 'None' and macaddress is not None:
                            _valid_macaddress = True
                        else:
                            _valid_macaddress = False
                    except Exception as er:
                        print "exception: ",er
                        ip_address = None
                        macaddress = address
                        if discovery_type == "Nest":
                            _valid_macaddress = False
                        else:
                            _valid_macaddress = True

                if _valid_macaddress:
                    if self.checkMACinDB(self.con, macaddress):
                        newdeviceflag = False
                        self.cur.execute("SELECT device_id from "+db_table_device_info
                                         +" where mac_address=%s",(macaddress,))
                        deviceID = self.cur.fetchone()[0]
                        # agent_launch_file=deviceID+".launch.json"
                        agent_launch_file=deviceID
                        self.cur.execute("SELECT approval_status from "+db_table_device_info
                                         +" where device_id=%s",(deviceID,))
                        bemoss_status = self.cur.fetchone()[0]
                        if self.device_agent_still_running(agent_launch_file):
                            print "{} >> {} for device with MAC address {} is still running"\
                                    .format(agent_id, agent_launch_file, macaddress)
                            if bemoss_status == 'NBD':
                                print '{} >> Device with MAC address {} found to be Non-BEMOSS, Stopping agent {}'\
                                        .format(agent_id, macaddress, agent_launch_file)
                                os.system("volttron-ctl stop --tag " + agent_launch_file)

                        else:
                            print "{} >> {} for device with MAC address {} is not running"\
                                    .format(agent_id, agent_launch_file, macaddress)
                            #restart agent if in BEMOSS Core
                            if bemoss_status == 'APR':
                                self.cur.execute("SELECT device_type from "+db_table_device_info
                                                +" where device_id=%s",(deviceID,))
                                stopped_agent_device_type = self.cur.fetchone()[0]
                                self.cur.execute("SELECT zone_id from "+stopped_agent_device_type
                                                +" where "+stopped_agent_device_type+"_id=%s",(deviceID,))
                                stopped_agent_zone_id = self.cur.fetchone()[0]
                                if stopped_agent_zone_id == 999:
                                    self.launch_agent(Agents_Launch_DIR, agent_launch_file)
                                    print "{} >> {} has been restarted"\
                                            .format(agent_id, agent_launch_file)
                                else:
                                    print "{} >> {} is running on another node, ignoring restart"\
                                            .format(agent_id, agent_launch_file)
                                # self.cur.execute("UPDATE "+db_table_device_info+" SET device_status=%s where "
                                #                                                           "id=%s", ("ON", deviceID))
                                # self.con.commit()
                            elif bemoss_status == 'NBD':
                                print '{} >> Device with MAC address {} found to be Non-BEMOSS'\
                                        .format(agent_id, macaddress)
                            else:
                                print '{} >> Device with MAC address {} is already discovered with pending status'\
                                        .format(agent_id, macaddress)

                        #case2: new device has been discovered
                    else:
                        print '{} >> new device found with macaddress {}'\
                            .format(agent_id, macaddress)
                        newdeviceflag = True
                else:
                    print "Invalid MAC address at: {}"\
                        .format(address)
                    newdeviceflag = False

                if newdeviceflag:
                    model_info_received = False
                    try:
                        modelinfo = discovery_module.getmodelvendor(discovery_type, address)
                        if modelinfo != None:
                            deviceModel = modelinfo['model']
                            deviceVendor = modelinfo['vendor']
                            print 'Model information found: '
                            print {'model':deviceModel,'vendor':deviceVendor}
                            model_info_received = True
                    except Exception as er:
                        print "exception: ",er
                        pass

                    if model_info_received:
                        try:
                            self.cur.execute("SELECT device_type from "+db_table_supported_devices
                                             +" where vendor_name=%s and device_model=%s",(deviceVendor,deviceModel))
                            controller_type_from_model = self.cur.fetchone()[0]
                            supported=True
                        except Exception as er:
                            print "exception: ",er
                            supported=False
                        if (supported):
                            if (controller_type=='All') | (controller_type_from_model == controller_type):
                                self.device_num+=1
                                #deviceType = com_type + controller_type
                                deviceType = controller_type_from_model
                                self.cur.execute("SELECT device_model_id from "+db_table_supported_devices
                                                 +" where vendor_name=%s and device_model=%s",(deviceVendor,deviceModel))
                                device_type_id = self.cur.fetchone()[0]
                                self.cur.execute("SELECT identifiable from "+db_table_supported_devices
                                                 +" where vendor_name=%s and device_model=%s",(deviceVendor,deviceModel))
                                identifiable = self.cur.fetchone()[0]
                                if (ip_address != None):
                                    if ('/' in ip_address):
                                        IPparsed = urlparse(ip_address)
                                        print IPparsed
                                        deviceIP = str(IPparsed.netloc)
                                        if str(IPparsed.scheme) != '':
                                            address= str(IPparsed.scheme)+ "://" + str(IPparsed.netloc)
                                        else:
                                            address = deviceIP
                                        if ':' in deviceIP:
                                            deviceIP = deviceIP.split(':')[0]
                                    else:
                                        if ':' in ip_address:
                                            deviceIP = ip_address.split(':')[0]
                                        else:
                                            deviceIP = ip_address
                                        address = ip_address
                                else:
                                    deviceIP = ip_address
                                self.cur.execute("SELECT api_name from "+db_table_supported_devices
                                                 +" where vendor_name=%s and device_model=%s",(deviceVendor,deviceModel))
                                deviceAPI = self.cur.fetchone()[0]
                                deviceID = device_type_id+macaddress
                                if 'nickname' in modelinfo.keys():
                                    deviceNickname = modelinfo['nickname']
                                else:
                                    deviceNickname = deviceType+str(self.device_num)
                                # self.cur.execute("INSERT INTO "+db_table_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                #                  (deviceID, deviceID, deviceType+str(self.device_num), deviceType, device_type_id,
                                #                   deviceVendor, deviceModel, macaddress))
                                self.cur.execute("INSERT INTO "+db_table_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                                 (deviceID, deviceType, deviceVendor, deviceModel, device_type_id, macaddress,
                                                  None, None, identifiable, com_type, str(datetime.datetime.now()), macaddress, 'PND'))
                                self.con.commit()

                                self.cur.execute("INSERT INTO "+deviceType+" ("+deviceType+"_id, ip_address,nickname,zone_id,network_status) VALUES(%s,%s,%s,%s,%s)",
                                                 (deviceID, deviceIP,deviceNickname,999,'ONLINE'))
                                self.con.commit()
                                agent_name = deviceType.replace('_','')
                                num_new_Devices+=1
                                #After found new device-> Assign a suitable agent to each device to communicate, control, and collect data
                                print('Now DeviceDiscoverAgent is assigning a suitable agent to the discovered device to communicate, control, and collect data')
                                self.write_launch_file(agent_name+"agent", deviceID, device_monitor_time, deviceModel,
                                               deviceVendor, deviceType.replace('_', ''), deviceAPI, address, macaddress, db_host, db_port,
                                               db_database, db_user, db_password)
                                # self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                                #self.launch_agent(Agents_Launch_DIR, deviceID)
                                self.new_discovery=True
                            else:
                                pass
                        else:
                            print "Device currently not supported by BEMOSS"

                    else:
                        print 'Unable to get device model information. Ignoring device...'

            #Print how many WiFi devices this DeviceDiscoverAgent found!
            print("{} >> Found {} new {} {} devices".format(agent_id,num_new_Devices,com_type,controller_type))
            print("{} >> There are existing {} {} {} devices\n".format(agent_id,num_Devices,com_type,controller_type))
            print " "

            self.con.commit()
            return num_new_Devices


        def launch_agent(self, dir, launch_file):
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
                infile.close()
                return agent_installed
            _launch_file = os.path.join(dir, launch_file+".launch.json")

            with open(_launch_file, 'r') as infile:
                data=json.load(infile)
                agent_id = data['agent_id']
            agentname=data["type"]
            os.chdir(os.path.expanduser("~/workspace/bemoss_os"))
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

            print "Discovery Agent has successfully launched {} located in {}".format(agent_id, dir)


        @matching.match_exact('/ui/agent/misc/bemoss/discovery_request')
        def manualDiscoveryBehavior(self, topic, headers, message, match):
            print "DeviceDiscoveryAgent got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)

            discovery_model_names = ast.literal_eval(message[0])
            #print discovery_model_names

            self.scan_for_devices = True
            self.deviceDiscoveryBehavior(discovery_model_names)


        def checkMACinDB(self, conn, macaddr):
            cur = conn.cursor()
            cur.execute("SELECT device_id FROM "+db_table_device_info+" WHERE mac_address=%(id)s",
                        {'id': macaddr})
            if cur.rowcount != 0:
                mac_already_in_db = True
            else:
                mac_already_in_db = False
            return mac_already_in_db

        def device_agent_still_running(self,agent_launch_filename):
            statusreply = subprocess.check_output('~/workspace/bemoss_os/env/bin/volttron-ctl status',shell=True)
            statusreply = statusreply.split('\n')
            agent_still_running = False
            reg_search_term = agent_launch_filename
            for line in statusreply:
                #print(line, end='') #write to a next file name outfile
                match = re.search(reg_search_term, line) and re.search('running', line)
                if match:  # The agent for this device is running
                    agent_still_running = True
                else:
                    pass
            return agent_still_running

        def publish_subtopic(self, publish_item, topic_prefix):
            #TODO: Update to use the new topic templates
            if type(publish_item) is dict:
                # Publish an "all" property, converting item to json

                headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
                self.publish_json(topic_prefix + topic_delim + "all", headers, json.dumps(publish_item))
                print "WiFiTherAgent got"+str(type(publish_item))
                os.system("date")
                # Loop over contents, call publish_subtopic on each
                for topic in publish_item.keys():
                    self.publish_subtopic(publish_item[topic], topic_prefix + topic_delim + topic)

            else:
                # Item is a scalar type, publish it as is
                headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.PLAIN_TEXT
                self.publish(topic_prefix, headers, str(publish_item))
                print "Topic:{topic}={message}".format(topic=topic_prefix,message=str(publish_item))

        def write_launch_file(self, executable, deviceID, device_monitor_time, deviceModel, deviceVendor, deviceType,
                              api, address, macaddress, db_host, db_port, db_database, db_user, db_password):
            try:
                host_ip_address = ni.ifaddresses('eth0')[2][0]['addr']
            except Exception as er:
                print "exception: ",er
                host_ip_address = None
            if host_ip_address is None:
                try:
                    host_ip_address = ni.ifaddresses('wlan0')[2][0]['addr']
                except Exception as er:
                    print "exception: ",er
                    pass

            else: pass
            data= {
                    "agent": {
                        "exec": executable+"-0.1-py2.7.egg --config \"%c\" --sub \"%s\" --pub \"%p\""
                    },
                    "agent_id": deviceID,
                    "device_monitor_time": device_monitor_time,
                    "model": deviceModel,
                    "vendor":deviceVendor,
                    "type": deviceType,
                    "api": api,
                    "address": address,
                    "macaddress": macaddress,
                    "db_host": db_host,
                    # "db_host": host_ip_address,
                    "db_port": db_port,
                    "db_database": db_database,
                    "db_user": db_user,
                    "db_password": db_password,
                    "building_name": "bemoss",
                    "zone_id" : 999
                }

            __launch_file = os.path.join(Agents_Launch_DIR+deviceID+".launch.json")
            #print(__launch_file)
            with open(__launch_file, 'w') as outfile:
                json.dump(data, outfile, indent=4, sort_keys=True)

    Agent.__name__ = 'DeviceDiscoveryAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DeviceDiscoveryAgent, description='Device Discovery agent', argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt as er:
        print "KeyboardInterrupt", er
        pass
