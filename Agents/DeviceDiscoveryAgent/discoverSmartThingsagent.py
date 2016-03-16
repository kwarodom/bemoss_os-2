import importlib
import psycopg2 #PostgresQL database adapter
import sys
import urllib2
import json
import datetime
import time
import logging
import os
import re
import random
from xml.dom import minidom
from volttron.lite.agent import BaseAgent, PublishMixin, periodic
from volttron.lite.agent import utils, matching
from volttron.lite.messaging import headers as headers_mod
import settings

utils.setup_logging()  # setup logger for debugging
_log = logging.getLogger(__name__)

#Step1: Agent Initialization
def DeviceDiscoveryAgent(config_path, **kwargs):
    config = utils.load_config(config_path)  # load the config_path from devicediscoveryagent.launch.json
    def get_config(name):
        try:
            value = kwargs.pop(name)  # from the **kwargs when call this function
        except KeyError:
            return config.get(name, '')

    #1. @params agent
    agent_id = get_config('agent_id')
    device_scan_time = get_config('device_scan_time')
    device_scan_time_multiplier = get_config('device_scan_time_multiplier')
    headers = {headers_mod.FROM: agent_id}
    publish_address = 'ipc:///tmp/volttron-lite-agent-publish'
    subscribe_address = 'ipc:///tmp/volttron-lite-agent-subscribe'
    topic_delim = '/'  # topic delimiter

    #2. @params device_info
    #List of all supported devices
    WiFiThermostats = ["CT30", "CT50", "Ecobee", "Nest"]
    WiFiLights = ["Philips", "LightSwitch"]
    WiFiSwitchs = ["Socket"]
    BACnetLights=["LMRC-212"]
    WiFiHubs=["SmartThings"]
    #Create a dictionary classifying types of the supported devices #warodom
    supportDevices=dict(WiFiThermostat=WiFiThermostats, WiFiLight=WiFiLights, WiFiSwitch=WiFiSwitchs, BACnetLight=BACnetLights, WiFiHub=WiFiHubs)
    #Create a dictionary classifying API of supported devices #warodom
    deviceAPIDocuments=dict(API1=["CT30", "CT50"], API2=["Ecobee"], API3=["Nest"], API4=["Philips Hue"],
                            API5=["Digi_SmartPlug", "Digi_SmartSensor"], API6="Z100", API7="SmartThings")

    #3. @params agent & DB interfaces
    #@params DB interfaces
    db_database = settings.DATABASES['default']['NAME']
    db_host = settings.DATABASES['default']['HOST']
    db_port = settings.DATABASES['default']['PORT']
    db_user = settings.DATABASES['default']['USER']
    db_password = settings.DATABASES['default']['PASSWORD']
    db_table_dashboard_device_info = settings.DATABASES['default']['TABLE_dashboard_device_info']
    db_table_dashboard_current_status = settings.DATABASES['default']['TABLE_dashboard_current_status']
    db_table_device_info = settings.DATABASES['default']['TABLE_device_info']

    #4. @params devicediscovery agent setting
    findWiFi = False
    WiFi_discovery_module = "discoverAPI.WiFi"
    WiFi_device_monitor_time = 20
    findWiFiHue = False
    Hue_discovery_module = "discoverAPI.WiFi"
    Hue_device_monitor_time = 20
    findWiFiWeMo = False
    WeMo_device_monitor_time = 10
    WeMo_discovery_module = "discoverAPI.WiFi"
    findBACnet = False
    BACnet_device_monitor_time = 20
    BACnet_discovery_module = "discoverAPI.BACnet"
    findSmartThingsHub = False
    SmartThings_username = 'kwarodom@hotmail.com'
    SmartThings_password = 'w3300136'
    SmartThings_auth_header = 'Bearer 59d232be-bf95-4d53-bd9a-df5e4d6dea96'
    SmartThings_end_point_url = 'https://graph.api.smartthings.com/api/smartapps/' \
                                'installations/be64201d-8a74-47b5-9126-b1a18a9d8488/'
    SmartThings_discovery_module = "testAPI.classAPI_SmartThings"
    SmartThings_device_monitor_time = 2

    #@paths
    PROJECT_DIR = settings.PROJECT_DIR
    Loaded_Agents_DIR = settings.Loaded_Agents_DIR
    Autostart_Agents_DIR = settings.Autostart_Agents_DIR
    Applications_Launch_DIR = settings.Applications_Launch_DIR
    Agents_Launch_DIR = settings.Agents_Launch_DIR

    class Agent(PublishMixin, BaseAgent):

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            # Connect to database
            self.con = psycopg2.connect(host=db_host, port=db_port, database=db_database,
                                        user=db_user, password=db_password)
            self.cur = self.con.cursor()  # open a cursor to perform database operations

            #launch AppLauncher Agent
            self.launch_agent(Applications_Launch_DIR, "applauncheragent.launch.json")

            self.device_scan_time = device_scan_time
            self.device_discovery_start_time = datetime.datetime.now()
            self.scan_for_devices = True
            self.findWiFi = findWiFi
            self.findWiFiHue = findWiFiHue
            self.findWiFiWeMo = findWiFiWeMo
            self.findBACnet = findBACnet
            self.findSmartThingsHub = findSmartThingsHub
            self.device_num = 0

            try:
                # Find total number of devices in the dashboard_device_info table
                self.cur.execute("SELECT * FROM "+db_table_dashboard_device_info)
                self.device_num = self.cur.rowcount  # count no. of devices discovered by Device Discovery Agent
                print "{} >> there are existing {} device(s) in database".format(agent_id, self.device_num)
                if self.device_num != 0:  # change network status of devices to OFF (OFFLINE)
                    rows = self.cur.fetchall()
                    for row in rows:
                        self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s", ("OFF",))
                        self.con.commit()
            except:
                self.device_num = 0

        def setup(self):
            super(Agent, self).setup()
            self.valid_data = False
            '''Discovery Processes'''
            while True:
                if self.scan_for_devices:
                    self.deviceScannerBehavior()
                    self.device_scan_time *= device_scan_time_multiplier
                    time.sleep(self.device_scan_time)
                else:
                    pass

        #deviceScannerBehavior (TickerBehavior)
        def deviceScannerBehavior(self):
            print "Start Discovery Processes--------------------------------------------------"
            print "{} >> device next scan time in {} sec".format(agent_id, str(self.device_scan_time ))
            print "{} >> start_time {}".format(agent_id, str(self.device_discovery_start_time))
            self.device_discovery_time_now = datetime.datetime.now()
            print "{} >> current time {}".format(agent_id, str(self.device_discovery_time_now))
            print "{} >> is trying to discover all available devices\n".format(agent_id)
            if self.findWiFi: self.findWiFiDevices()
            if self.findWiFiWeMo: self.findWeMoDevices()
            if self.findWiFiHue: self.findHueDevices()
            if self.findBACnet: self.findBACnetDevices()
            if self.findSmartThingsHub: self.findSmartThingsHubDevices()
            print "Stop Discovery Processes---------------------------------------------------"

        def findWiFiDevices(self):
            #******************************************************************************************************
            #1. WiFi (USNAP module) Discovery service for WiFi Thermostat (USNAP module) 3M50 and CT30
            #Step1: discover WiFi devices
            self.newWiFiDevices = list()  # create a list of WiFi Devices to store all WiFi devices discovered
            newmacaddress = dict()
            if findWiFi:
                print "{} >> is finding available WiFi devices ...".format(agent_id)
                discovery_module = importlib.import_module(WiFi_discovery_module)
                discovered_ips = discovery_module.discover("thermostat")
                print discovered_ips
                deviceTypeID ='1TH'

                for ip_address in discovered_ips:
                    # print 'discovered_ips'+ip_address #for debug purpose only
                    _device_has_macaddress = False
                    onlyipaddress=ip_address.replace('/sys', '')

                    try:
                        macaddress = discovery_module.getMACaddress("Thermostat", ip_address)
                        _device_has_macaddress = True
                        # print 'ip_address ' + ip_address + ' macaddress ' + macaddress
                    except:
                        _device_has_macaddress = False
                        # macaddress = '88308a2224dd'  #TODO try to find device macaddress again

                    if _device_has_macaddress and macaddress is not None:
                        #check whether macaddress is already in database
                        #case1: device has already been discovered: check whether corresponding agent is running
                        if self.checkMACinDB(self.con, macaddress):
                            sys.path.append(PROJECT_DIR)
                            os.system("bin/volttron-ctrl list-agent > running_agents.txt")
                            infile = open('running_agents.txt', 'r')
                            agent_still_running = False
                            reg_search_term = deviceTypeID+macaddress+'.launch.json'
                            deviceID = deviceTypeID+macaddress
                            for line in infile:
                                #print(line, end='') #write to a next file name outfile
                                match = re.search(reg_search_term, line) and re.search('running', line)
                                if match:  # The agent for this device is running
                                    agent_still_running = True
                                    agent_launch_file = reg_search_term
                                    agent_mac_address = macaddress
                                    agent_ip_address = onlyipaddress
                                else:
                                    pass
                            infile.close()
                            if agent_still_running:
                                print "{} >> {} for device with MAC address {} and ip address {} is still running"\
                                        .format(agent_id, agent_launch_file, agent_mac_address, agent_ip_address)
                                self.cur.execute("SELECT device_status from "+db_table_dashboard_device_info
                                                 +" where id=%s",(deviceID,))
                                device_status = self.cur.fetchone()[0]
                                # print 'device_status '+ str(device_status)
                                if device_status == "OFF":
                                    self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                              "id=%s", ("ON", deviceID))
                                    self.con.commit()
                                else:
                                    pass
                            else:
                                print "{} >> {} for device with MAC address {} and ip address {} is not running"\
                                        .format(agent_id, reg_search_term, macaddress, ip_address)
                                #restart agent
                                self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                                self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                          "id=%s", ("ON", deviceID))
                                self.con.commit()
                            #case2: new device has been discovered
                        else:
                            print '{} >> new device found with ip_address {} and macaddress {}'\
                                .format(agent_id, ip_address, macaddress)
                            self.newWiFiDevices.append(ip_address)
                            newmacaddress[ip_address] = macaddress
                    else:
                        print "{} >> cannot find MAC address for device with ip address {}"\
                            .format(agent_id, ip_address)

                self.cur.execute("SELECT device_type_id FROM "+db_table_dashboard_device_info +
                                 " WHERE device_type_id=%(id)s", {'id': '1TH'})
                num_WiFiUSNAPDevices = self.cur.rowcount
                num_new_WiFiUSNAPDevices = 0

                #Step2: After discover all available devices, query the model number
                for ipaddress in self.newWiFiDevices:
                    macaddress = newmacaddress[ipaddress]
                    try:
                        modelinfo = discovery_module.getmodelvendor("Thermostat", ipaddress)
                        deviceModel = modelinfo['model']
                        deviceVendor = modelinfo['vendor']
                    except:
                        deviceModel = "CT50"
                        deviceVendor = "RadioThermostat"
                    print {'model':deviceModel,'vendor':deviceVendor}

                    #Step1: GET Open the URL and obtain a model number of a device
                    apiipaddress=ipaddress.replace('/sys','/tstat')
                    deviceIP = apiipaddress
                    print ipaddress
                    onlyipaddress=ipaddress.replace('/sys','')
                    #2.2 get device type
                    deviceType = self.getDeviceType(deviceModel)
                    deviceTypeID ='1TH'
                    deviceID=deviceTypeID+str(macaddress)
                    #2.3 get API
                    deviceAPI = "classAPI_RadioThermostat"
                    # deviceAPI = self.getDeviceAPI(deviceModel)
                    self.device_num += 1
                    self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, ip_address) VALUES(%s,%s)",
                                     (deviceID, deviceIP))
                    self.con.commit()
                    self.cur.execute("INSERT INTO "+db_table_dashboard_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                     (deviceID,deviceID,deviceType+str(self.device_num),deviceType,deviceTypeID,deviceVendor,deviceModel,macaddress))
                    self.con.commit()
                    num_new_WiFiUSNAPDevices+=1
                    print('Now DeviceDiscoverAgent is assigning a suitable agent to the discovered USNAP '
                          'device to communicate, control, and collect data')
                    self.write_launch_file("thermostatagent", deviceID, WiFi_device_monitor_time, deviceModel,
                                           deviceVendor, deviceType, deviceAPI, deviceIP, db_host, db_port,
                                           db_database, db_user, db_password)
                    self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                #Print how many WiFi devices this DeviceDiscoverAgent found!
                print("DeviceDiscoverAgent: found {} new WiFi USNAP devices".format(num_new_WiFiUSNAPDevices))
                print("DeviceDiscoverAgent: there are existing {} WiFi USNAP devices".format(num_WiFiUSNAPDevices))
                print('')

        def findWeMoDevices(self):
            #******************************************************************************************************
            #2. WeMo switch
            if findWiFiWeMo==True:
                self.wemoDevices=list() #This is a list of Wemo switches
                print('DeviceDiscoverAgent is finding available WiFi WeMo devices ...')

                discovery_module = importlib.import_module(WeMo_discovery_module)

                os.system("./wemo_demo_discover > WiFiwemodevices.txt")
                #WiFiwemoDevices
                infile = open('WiFiwemodevices.txt', 'r')
                for line in infile:
                    #print(line, end='') #write to a next file name outfile
                    match = re.search('http://',line) and (re.search(':49153/setup.xml',line) or re.search(':49154/setup.xml',line)) #have results in match
                    if match:
                        s = line.split()  # create a list object
                        print s
                        for string in s:
                            match = re.search('http://', string) #have results in match
                            if match:
                                #print(string) #for debug purpose only
                                if string in self.wemoDevices:
                                    pass
                                else:
                                    self.wemoDevices.append(string)
                infile.close()

                self.cur.execute("SELECT device_type_id FROM dashboard_device_info WHERE device_type_id=%(id)s", {'id': '3WSP'})
                num_WeMoDevices=self.cur.rowcount
                num_new_WeMoDevices = 0

                for wemoDevice in self.wemoDevices:
                    ip_address = wemoDevice

                    try:
                        macaddress = discovery_module.getMACaddress("WeMo", ip_address)
                        getMACADDR = True
                        _device_has_macaddress = True
                        # print devicemac
                    except:
                        # devicemac='08863B703381' #TODO what is this??
                        _device_has_macaddress = False
                        getMACADDR = False

                    try:
                        modelinfo = discovery_module.getmodelvendor("WeMo", ip_address)
                        #print modelinfo
                        deviceModel = modelinfo['model']
                        deviceVendor = modelinfo['vendor']
                    except: #set to default value
                        #TODO fix this method change the default device model
                        deviceModel = "Socket"
                        deviceVendor ="Belkin International Inc."
                    deviceType = self.getDeviceType(deviceModel)
                    if re.search("Socket", deviceModel):
                        deviceTypeID = '3WSP'
                    elif re.search("LightSwitch", deviceModel):
                        deviceTypeID = '2WL'

                    newdeviceflag = 0  # find whether the newly discovered device is already exist

                    if _device_has_macaddress and macaddress is not None:
                        #check whether macaddress is already in database
                        #case1: device has already been discovered: check whether corresponding agent is running
                        if self.checkMACinDB(self.con, macaddress):
                            sys.path.append(PROJECT_DIR)
                            os.system("bin/volttron-ctrl list-agent > running_agents.txt")
                            infile = open('running_agents.txt', 'r')
                            agent_still_running = False
                            reg_search_term = deviceTypeID+macaddress+'.launch.json'
                            deviceID = deviceTypeID+macaddress
                            for line in infile:
                                #print(line, end='') #write to a next file name outfile
                                match = re.search(reg_search_term, line) and re.search('running', line)
                                if match:  # The agent for this device is running
                                    agent_still_running = True
                                    agent_launch_file = reg_search_term
                                    agent_mac_address = macaddress
                                    agent_ip_address = ip_address
                                else:
                                    pass
                            infile.close()
                            if agent_still_running:
                                print "{} >> {} for device with MAC address {} and ip address {} is still running"\
                                        .format(agent_id, agent_launch_file, agent_mac_address, agent_ip_address)
                                self.cur.execute("SELECT device_status from "+db_table_dashboard_device_info
                                                 +" where id=%s",(deviceID,))
                                device_status = self.cur.fetchone()[0]
                                # print 'device_status '+ str(device_status)
                                if device_status == "OFF":
                                    self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                              "id=%s", ("ON", deviceID))
                                    self.con.commit()
                                else:
                                    pass
                            else:
                                print "{} >> {} for device with MAC address {} and ip address {} is not running"\
                                        .format(agent_id, reg_search_term, macaddress, ip_address)
                                #restart agent
                                self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                                self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                          "id=%s", ("ON", deviceID))
                                self.con.commit()
                            #case2: new device has been discovered
                        else:
                            print '{} >> new device found with ip_address {} and macaddress {}'\
                                .format(agent_id, ip_address, macaddress)
                            newdeviceflag = 1
                    else:
                        print "{} >> cannot find MAC address for device with ip address {}"\
                            .format(agent_id, ip_address)

                    if newdeviceflag == 1:
                        deviceIP = ip_address.replace('/setup.xml', '')
                        self.device_num+=1
                        deviceAPI = "classAPI_WeMo"
                        deviceID = deviceTypeID+macaddress
                        self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, ip_address) VALUES(%s,%s)",
                                         (deviceID, deviceIP))
                        self.con.commit()
                        self.cur.execute("INSERT INTO "+db_table_dashboard_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                         (deviceID, deviceID, deviceType+str(self.device_num), deviceType, deviceTypeID,
                                          deviceVendor, deviceModel, macaddress))
                        self.con.commit()
                        num_new_WeMoDevices+=1
                        #After found new device-> Assign a suitable agent to each device to communicate, control, and collect data
                        print('Now DeviceDiscoverAgent is assigning a suitable agent to the discovered Weme device to communicate, control, and collect data')
                        if deviceTypeID == "3WSP":
                            self.write_launch_file("plugloadagent", deviceID, WeMo_device_monitor_time, deviceModel,
                                           deviceVendor, deviceType, deviceAPI, deviceIP, db_host, db_port,
                                           db_database, db_user, db_password)
                        else:
                            self.write_launch_file("lightingagent", deviceID, WeMo_device_monitor_time, deviceModel,
                                           deviceVendor, deviceType, deviceAPI, deviceIP, db_host, db_port,
                                           db_database, db_user, db_password)
                        self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                #Print how many WiFi devices this DeviceDiscoverAgent found!
                print("DeviceDiscoverAgent: found {} new WiFi WeMo devices".format(num_new_WeMoDevices))
                print("DeviceDiscoverAgent: there are existing {} WiFi WeMo devices\n".format(num_WeMoDevices))
            #******************************************************************************************************

        def findHueDevices(self):
            #3. WiFi Lighting Philips Hue
            self.hueDevices=list() #This is a list of BACnet Devices
            if findWiFiHue==True:
                print('DeviceDiscoverAgent is finding available WiFi Hue devices ...')

                discovery_module = importlib.import_module(Hue_discovery_module)

                os.system("./hue_demo_discover > WiFihuedevices.txt")
                #WiFiDevices
                infile = open('WiFihuedevices.txt', 'r')
                for line in infile:
                    #print(line, end='') #write to a next file name outfile
                    match = re.search('http://',line) and re.search(':80/description.xml',line) #have results in match
                    #step2: replace the matched pattern with another text
                    #pattern = re.compile('/sys/',re.IGNORECASE)
                    if match:
                        s=line.split() #create a list object
                        for string in s:
                            match = re.search('http://',string) #have results in match
                            if match:
                                #print(string) #for debug purpose only
                                if string in self.hueDevices:
                                    pass
                                else:
                                    self.hueDevices.append(string)
                infile.close()
                self.cur.execute("SELECT device_type_id FROM dashboard_device_info WHERE device_type_id=%(id)s",
                                 {'id': '2HUE'})
                num_HueDevices=self.cur.rowcount
                num_new_HueDevices = 0

                for hueDevice in self.hueDevices:
                    ip_address = hueDevice

                    try:
                        macaddress = discovery_module.getMACaddress("Philips", ip_address)
                        _device_has_macaddress = True
                    except:
                        print("{}: error getting MACADDR".format(agent_id))
                        _device_has_macaddress = False

                    deviceTypeID='2HUE'

                    newdeviceflag = 0

                    if _device_has_macaddress and macaddress is not None:
                        #check whether macaddress is already in database
                        #case1: device has already been discovered: check whether corresponding agent is running
                        if self.checkMACinDB(self.con, macaddress):
                            sys.path.append(PROJECT_DIR)
                            os.system("bin/volttron-ctrl list-agent > running_agents.txt")
                            infile = open('running_agents.txt', 'r')
                            agent_still_running = False
                            reg_search_term = deviceTypeID+macaddress+'.launch.json'
                            deviceID = deviceTypeID+macaddress
                            for line in infile:
                                #print(line, end='') #write to a next file name outfile
                                match = re.search(reg_search_term, line) and re.search('running', line)
                                if match:  # The agent for this device is running
                                    agent_still_running = True
                                    agent_launch_file = reg_search_term
                                    agent_mac_address = macaddress
                                    agent_ip_address = ip_address
                                else:
                                    pass
                            infile.close()
                            if agent_still_running:
                                print "{} >> {} for device with MAC address {} and ip address {} is still running"\
                                        .format(agent_id, agent_launch_file, agent_mac_address, agent_ip_address)
                                self.cur.execute("SELECT device_status from "+db_table_dashboard_device_info
                                                 +" where id=%s",(deviceID,))
                                device_status = self.cur.fetchone()[0]
                                # print 'device_status '+ str(device_status)
                                if device_status == "OFF":
                                    self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                              "id=%s", ("ON", deviceID))
                                    self.con.commit()
                                else:
                                    pass
                            else:
                                print "{} >> {} for device with MAC address {} and ip address {} is not running"\
                                        .format(agent_id, reg_search_term, macaddress, ip_address)
                                #restart agent
                                self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                                self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                          "id=%s", ("ON", deviceID))
                                self.con.commit()
                            #case2: new device has been discovered
                        else:
                            print '{} >> new device found with ip_address {} and macaddress {}'\
                                .format(agent_id, ip_address, macaddress)
                            newdeviceflag = 1
                    else:
                        print "{} >> cannot find MAC address for device with ip address {}"\
                            .format(agent_id, ip_address)

                    if newdeviceflag == 1:
                        deviceIPtemp = hueDevice.replace(':80', '/api/newdeveloper/groups/0')
                        deviceIP = deviceIPtemp.replace('description.xml','')
                        print(deviceIP)
                        #print deviceIP
                        modelinfo = discovery_module.getmodelvendor("Philips",ip_address)
                        print modelinfo
                        deviceModel = modelinfo['model']
                        deviceVendor = modelinfo['vendor']
                        deviceID = deviceTypeID+macaddress
                        deviceType = self.getDeviceType(deviceModel)
                        # deviceTypeID='2HUE'
                        # deviceID=deviceTypeID + macaddress
                        deviceAPI = "classAPI_PhilipsHue"
                        self.device_num += 1
                        self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, ip_address) VALUES(%s,%s)",
                                         (deviceID, deviceIP))
                        self.con.commit()
                        self.cur.execute("INSERT INTO dashboard_device_info VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                         (deviceID, deviceID, deviceType+str(self.device_num), deviceType, deviceTypeID,
                                          deviceVendor, deviceModel, macaddress))
                        self.con.commit()
                        num_new_HueDevices += 1
                        #After found new device-> Assign a suitable agent to each device to communicate, control, and collect data
                        print('Now DeviceDiscoverAgent is assigning a suitable agent to a discovered WiFi Hue device to communicate, control, and collect data')
                        self.write_launch_file("lightingagent", deviceID, Hue_device_monitor_time, deviceModel,
                                           deviceVendor, deviceType, deviceAPI, deviceIP, db_host, db_port,
                                           db_database, db_user, db_password)
                        self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                #Print how many WiFi devices this DeviceDiscoverAgent found!
                print("DeviceDiscoverAgent: found {} new WiFi Hue devices".format(num_new_HueDevices))
                print("DeviceDiscoverAgent: there are existing {} WiFi Hue devices\n".format(num_HueDevices))

        def findBACnetDevices(self):
            #4. BACnet Devices
            self.newBACnetDevices=list() #This is a list of BACnet Devices

            if findBACnet:
                print "{} >> is finding available BACnet devices ...".format(agent_id)
                discovery_module = importlib.import_module(BACnet_discovery_module)
                discovered_macs = discovery_module.discover()
                print discovered_macs
                deviceTypeID ='2WSL'

                for macaddress in discovered_macs:
                    #check whether macaddress is already in database
                    #case1: device has already been discovered: check whether corresponding agent is running
                    if self.checkMACinDB(self.con, macaddress):
                        sys.path.append(PROJECT_DIR)
                        os.system("bin/volttron-ctrl list-agent > running_agents.txt")
                        infile = open('running_agents.txt', 'r')
                        agent_still_running = False
                        reg_search_term = deviceTypeID+macaddress+'.launch.json'
                        deviceID = deviceTypeID+macaddress
                        for line in infile:
                            #print(line, end='') #write to a next file name outfile
                            match = re.search(reg_search_term, line) and re.search('running', line)
                            if match:  # The agent for this device is running
                                agent_still_running = True
                                agent_launch_file = reg_search_term
                                agent_mac_address = macaddress
                            else:
                                pass
                        infile.close()
                        if agent_still_running:
                            print "{} >> {} for device with MAC address {} is still running"\
                                    .format(agent_id, agent_launch_file, agent_mac_address)
                            self.cur.execute("SELECT device_status from "+db_table_dashboard_device_info
                                             +" where id=%s",(deviceID,))
                            device_status = self.cur.fetchone()[0]
                            # print 'device_status '+ str(device_status)
                            if device_status == "OFF":
                                self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                          "id=%s", ("ON", deviceID))
                                self.con.commit()
                            else:
                                pass
                        else:
                            print "{} >> {} for device with MAC address {} is not running"\
                                    .format(agent_id, reg_search_term, macaddress)
                            #restart agent
                            self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                            self.cur.execute("UPDATE "+db_table_dashboard_device_info+" SET device_status=%s where "
                                                                                      "id=%s", ("ON", deviceID))
                            self.con.commit()
                        #case2: new device has been discovered
                    else:
                        print '{} >> new device found with macaddress {}'\
                            .format(agent_id, macaddress)
                        self.newBACnetDevices.append(macaddress)

                self.cur.execute("SELECT device_type_id FROM "+db_table_dashboard_device_info +
                                 " WHERE device_type_id=%(id)s", {'id': '2WSL'})
                num_BACnetDevices = self.cur.rowcount
                num_new_BACnetDevices = 0

                #Step2: After discover all available devices, query the model number
                for macaddress in self.newBACnetDevices:
                    bacnet_comm_failure=True
                    modelinfo=discovery_module.getmodelvendor(macaddress)
                    if modelinfo != None:
                        deviceModel = modelinfo['model']
                        deviceVendor = modelinfo['vendor']
                        print {'model':deviceModel,'vendor':deviceVendor}
                        bacnet_comm_failure=False

                    if bacnet_comm_failure == False:
                        #2.2 get device type
                        deviceType = self.getDeviceType(deviceModel)
                        deviceTypeID='2WSL'
                        deviceID=deviceTypeID+str(macaddress)

                        #2.3 get API
                        deviceAPI = "classAPI_BACnet_WattStopper"
                        # deviceAPI = self.getDeviceAPI(deviceModel)
                        self.device_num += 1
                        self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, on_off_status) VALUES(%s,%s)",
                                         (deviceID, 'OFF'))
                        self.con.commit()
                        self.cur.execute("INSERT INTO "+db_table_dashboard_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                         (deviceID,deviceID,deviceType+str(self.device_num),deviceType,deviceTypeID,deviceVendor,deviceModel,macaddress))
                        self.con.commit()
                        num_new_BACnetDevices+=1
                        print('Now DeviceDiscoverAgent is assigning a suitable agent to the discovered BACnet '
                              'device to communicate, control, and collect data')
                        self.write_launch_file("lightingagent", deviceID, BACnet_device_monitor_time, deviceModel,
                                               deviceVendor, deviceType, deviceAPI, macaddress, db_host, db_port,
                                               db_database, db_user, db_password)
                        self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                #Print how many BACnet devices this DeviceDiscoverAgent found!
                print("DeviceDiscoverAgent: found {} new BACnet devices".format(num_new_BACnetDevices))
                print("DeviceDiscoverAgent: there are existing {} BACnet devices".format(num_BACnetDevices))
                print('')

        def findSmartThingsHubDevices(self):
            #******************************************************************************************************
            #1. Discovery service for WiFi SmartThings Hub
            #Step1: discover WiFi SmartThings Hub
            self.newSmartThingsHubs = list()  # create a list of discovered SmartThings Hubs
            self.newSmartThingsDevices = list()
            newmacaddress = dict()
            if findSmartThingsHub:
                print "{} >> is finding available SmartThings Hub ...".format(agent_id)
                apiLib = importlib.import_module(SmartThings_discovery_module)
                SmartThingsHub = apiLib.API(model='SmartThings', agent_id='SmartThingsHub', api='API7',
                                            auth_header=SmartThings_auth_header,
                                            address=SmartThings_end_point_url)
                SmartThingsHub.discoverHub(SmartThings_username, SmartThings_password)
                #TODO add method to discover more than one hub
                discovered_ips = [SmartThingsHub.get_variable('hub_ip_address')]
                hub_model_id ='7ST'
                hub_type = 'hub'
                hub_vendor = 'SmartThings'
                hub_model = 'SmartThings Hub'
                hub_communication = 'WiFi'
                hub_identifiable = False

                for ip_address in discovered_ips:
                    # print 'discovered_ips'+ip_address #for debug purpose only
                    _device_has_macaddress = False
                    # onlyipaddress=ip_address.replace('/sys', '')
                    try:
                        macaddress = SmartThingsHub.get_variable('hub_macaddress')
                        _device_has_macaddress = True
                        # print 'ip_address ' + ip_address + ' macaddress ' + macaddress
                    except:
                        _device_has_macaddress = False
                        # macaddress = '88308a2224dd'  #TODO try to find device macaddress again
                    if _device_has_macaddress and macaddress is not None:
                        #check whether macaddress is already in database
                        #case1: device has already been discovered: check whether corresponding agent is running
                        if self.checkMACinDB(self.con, macaddress):
                            pass
                            #case2: new device has been discovered
                        else:
                            print '{} >> new device found with ip_address {} and macaddress {}'\
                                .format(agent_id, ip_address, macaddress)
                            self.newSmartThingsHubs.append(ip_address)
                            newmacaddress[ip_address] = macaddress
                    else:
                        print "{} >> cannot find MAC address for device with ip address {}"\
                            .format(agent_id, ip_address)

                self.cur.execute("SELECT device_type_id FROM "+db_table_dashboard_device_info +
                                 " WHERE device_type_id=%(id)s", {'id': hub_model_id})
                num_SmartThingsHubs = self.cur.rowcount
                num_new_SmartThingsHubs = 0

                #Step2: After discover all available devices, query the model number
                for ip_address in self.newSmartThingsHubs:
                    macaddress = newmacaddress[ip_address]
                    #Step1: GET Open the URL and obtain a model number of a device
                    device_ip = ip_address
                    hub_location = SmartThingsHub.get_variable('hub_locationId')
                    hub_firmwareVersion = SmartThingsHub.get_variable('hub_firmwareVersion')
                    hub_id = SmartThingsHub.get_variable('hub_id')
                    hub_firmwareUpdateAvailable = SmartThingsHub.get_variable('hub_firmwareUpdateAvailable')
                    hub_battery = SmartThingsHub.get_variable('hub_batteryLevel')
                    hub_signal_strength = SmartThingsHub.get_variable('hub_signalStrength')
                    hub_nickname = SmartThingsHub.get_variable('hub_name')
                    zone_id = 999  # initial given zone id
                    if SmartThingsHub.get_variable('hub_status') == 'ACTIVE':
                        hub_network_status = 'ONLINE'
                    else:
                        hub_network_status = 'OFFLINE'
                    # other_parameters -> save hub_type,hub_role,hub_onlineSince,hub_zigbeeId,hub_virtual
                    last_scanned_time = datetime.datetime.now()
                    # last_offline_time

                    device_id = hub_model_id+str(macaddress)
                    #TODO find zone_id of bemoss_core from building_zone table

                    #2.3 get API
                    device_api = "classAPI_SmartThings"
                    # deviceAPI = self.getDeviceAPI(deviceModel)
                    self.device_num += 1
                    self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, ip_address) VALUES(%s,%s)",
                                     (device_id, device_ip))
                    self.con.commit()
                    self.cur.execute("INSERT INTO "+db_table_dashboard_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                     (device_id, device_id, hub_type+str(self.device_num), hub_type, hub_model_id,
                                      hub_vendor, hub_model, macaddress))
                    self.con.commit()
                    self.cur.execute("INSERT INTO device_info(device_id,device_type,vendor_name,device_model,device_model_id,"
                                     "mac_address,identifiable,communication,date_added,factory_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                     (device_id, hub_type, hub_vendor, hub_model, hub_model_id,
                                      macaddress, hub_identifiable, hub_communication, datetime.datetime.now(),hub_id))
                    self.con.commit()
                    self.cur.execute("INSERT INTO hub(hub_id,location,firmware_version,factory_id,firmware_update_available,"
                                     "battery,signal_strength,ip_address,nickname,zone_id,network_status,last_scanned_time)"
                                     " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                     (device_id, hub_location, hub_firmwareVersion, hub_id, hub_firmwareUpdateAvailable,
                                      hub_battery, hub_signal_strength, ip_address, hub_nickname, zone_id, hub_network_status,
                                     last_scanned_time))
                    self.con.commit()
                    num_new_SmartThingsHubs += 1
                    print('Now DeviceDiscoverAgent is assigning a suitable agent to the discovered SmartThings Hub'
                          'to communicate, control, and collect data')
                    # self.write_launch_file("thermostatagent", deviceID, WiFi_device_monitor_time, deviceModel,
                    #                        deviceVendor, deviceType, deviceAPI, deviceIP, db_host, db_port,
                    #                        db_database, db_user, db_password)
                    # self.launch_agent(Agents_Launch_DIR, deviceID+".launch.json")
                #Print how many WiFi devices this DeviceDiscoverAgent found!
                print("DeviceDiscoverAgent: found {} new SmartThing Hub".format(num_new_SmartThingsHubs))
                print("DeviceDiscoverAgent: there are existing {} SmartThing Hub".format(num_SmartThingsHubs))
                print('')

                # self.cur.execute("SELECT device_type_id FROM "+db_table_dashboard_device_info +
                #                  " WHERE device_type_id=%(id)s", {'id': '2WSL'})
                # num_BACnetDevices = self.cur.rowcount
                # num_new_BACnetDevices = 0

                #Step2: discover WiFi SmartThings devices
                self.newSmartThingsDevices = SmartThingsHub.getHubDevices(SmartThings_username, SmartThings_password)
                for index in range(0, len(self.newSmartThingsDevices)):
                    # print self.newSmartThingsDevices[index]
                    # find type of devices
                    device_id = self.newSmartThingsDevices[index]
                    device_type = SmartThingsHub.get_variable('hub_device_'+device_id+'_name')
                    self.cur.execute("SELECT device_id FROM device_info WHERE factory_id=%(id)s", {'id': device_id})
                    if bool(self.cur.rowcount):
                        print "SmartThings device {} with device_id {} has already discovered and launched!"\
                            .format(device_type, device_id)
                    else:
                        print "DeviceDiscovery Agent discovered SmartThings device {} with device_id {}"\
                            .format(device_type, device_id)
                        device_network_status = SmartThingsHub.get_variable('hub_device_'+device_id+'_status')
                        device_nickname = SmartThingsHub.get_variable('hub_device_'+device_id+'_label')
                        zone_id = 999  # initial given zone id
                        if device_network_status == 'ACTIVE':
                            _device_network_status = 'ONLINE'
                            device_monitor_time = SmartThings_device_monitor_time
                            device_vendor = 'SmartThings'
                            device_api = "classAPI_SmartThings"
                            address_get = 'https://graph.api.smartthings.com/api/devices/'+device_id
                            device_ip = SmartThingsHub.get_variable('hub_ip_address')
                            agent_exec = "Null"
                            #Step3: base on type of device found launch agent for that device
                            if device_type == 'CentraLite Switch':
                                device_type = 'plugload'
                                device_model_id = '3STS'
                                print '{} device_type is {}'.format(device_id, device_type)
                                _agent_id = device_model_id+device_id
                                if SmartThingsHub.get_variable('hub_device_'+device_id+'_currentStates_switch')=='on':
                                    device_status = 'ON'
                                elif SmartThingsHub.get_variable('hub_device_'+device_id+'_currentStates_switch')=='off':
                                    device_status = 'OFF'
                                else:
                                    device_status = 'N/A'
                                device_model = 'CentraLite Switch'
                                address_put = SmartThings_end_point_url+'switches/'+device_id
                                device_identifiable = True
                                device_communication = 'Zigbee'
                                macaddress = self.getRandomMAC()  # FIXXX This
                                agent_exec = "plugloadagent"
                                self.device_num += 1
                                device_table = "plugload"
                                device_table_id = "plugload_id"
                                # self.cur.execute("INSERT INTO plugload(plugload_id, status, ip_address, nickname,zone_id,network_status,"
                                #                  "last_scanned_time,last_offline_time)"
                                #                  " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                                #                  (_agent_id, device_status, device_ip, device_nickname, zone_id, _device_network_status,
                                #                  datetime.datetime.now(), datetime.datetime.now()))
                                # self.con.commit()
                            elif device_type == 'SmartSense Motion':
                                device_model_id = '4STMS'
                                print '{} device_type is {}'.format(device_id, device_type)
                                _agent_id = device_model_id+device_id
                                if SmartThingsHub.get_variable('hub_device_'+device_id+'_currentStates_motion')=='active':
                                    device_status = True
                                elif SmartThingsHub.get_variable('hub_device_'+device_id+'_currentStates_switch')=='inactive':
                                    device_status = False
                                else:
                                    device_status = 'N/A'
                                device_model = 'SmartSense Motion'
                                address_put = SmartThings_end_point_url+'motions/'+device_id
                                device_identifiable = False
                                device_communication = 'Zigbee'
                                macaddress = self.getRandomMAC()
                                agent_exec = "motionsensoragent"
                                self.device_num += 1
                                device_table = "motion_sensor"
                                device_table_id = "motion_sensor_id"
                                # self.cur.execute("INSERT INTO motion_sensor(motion_sensor_id, motion, ip_address, nickname,zone_id,network_status,"
                                #                  "last_scanned_time,last_offline_time)"
                                #                  " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                                #                  (_agent_id, device_status, device_ip, device_nickname, zone_id, _device_network_status,
                                #                  datetime.datetime.now(), datetime.datetime.now()))
                                # self.con.commit()
                            elif device_type == 'SmartSense Multi':
                                device_model_id = '4STML'
                                print '{} device_type is {}'.format(device_id, device_type)
                                _agent_id = device_model_id+device_id
                                device_model = 'SmartSense Multi'
                                address_put = SmartThings_end_point_url+'multis/'+device_id
                                device_identifiable = False
                                device_communication = 'Zigbee'
                                macaddress = self.getRandomMAC()
                                agent_exec = "multisensoragent"
                                self.device_num += 1
                                device_table = "multi_sensor"
                                device_table_id = "multi_sensor_id"
                                # self.cur.execute("INSERT INTO multi_sensor(multi_sensor_id, ip_address, nickname,zone_id,network_status,"
                                #                  "last_scanned_time,last_offline_time)"
                                #                  " VALUES(%s,%s,%s,%s,%s,%s,%s)",
                                #                  (_agent_id, device_ip, device_nickname, zone_id, _device_network_status,
                                #                  datetime.datetime.now(), datetime.datetime.now()))
                                # self.con.commit()
                            elif device_type == 'SmartSense Presence':
                                device_model_id = '4STPS'
                                print '{} device_type is {}'.format(device_id, device_type)
                                _agent_id = device_model_id+device_id
                                device_model = 'SmartSense Presence'
                                address_put = SmartThings_end_point_url+'presences/'+device_id
                                device_identifiable = False
                                device_communication = 'Zigbee'
                                macaddress = self.getRandomMAC()
                                agent_exec = "presencesensoragent"
                                self.device_num += 1
                                device_table = "presence_sensor"
                                device_table_id = "presence_sensor_id"
                            else:
                                pass

                            if agent_exec != "Null":
                                self.write_launch_file(agent_exec, _agent_id, device_monitor_time, device_model, device_vendor,
                                                       device_type, device_api, device_ip, db_host, db_port, db_database, db_user,
                                                       db_password, address_get, address_put, "None", SmartThings_auth_header,
                                                       SmartThings_username, SmartThings_password)
                                #TODO launch motionsensoragent
                                # self.launch_agent(Agents_Launch_DIR, _agent_id+".launch.json")

                                print("DeviceDiscoverAgent: launched new SmartThings {} for {}".format(device_model, _agent_id))
                                # print("DeviceDiscoverAgent: found {} new BACnet devices".format(num_new_BACnetDevices))
                                # print("DeviceDiscoverAgent: there are existing {} BACnet devices".format(num_BACnetDevices))
                                print('')


                                self.cur.execute("INSERT INTO "+db_table_dashboard_current_status+" (id, ip_address) VALUES(%s,%s)",
                                             (_agent_id, device_ip))
                                self.con.commit()

                                self.cur.execute("INSERT INTO "+db_table_dashboard_device_info+" VALUES(%s,%s,%s,%s,%s,%s,%s,999,%s,'ON')",
                                                 (_agent_id, _agent_id, device_type+str(self.device_num), device_type, device_model_id,
                                                  device_vendor, device_model, macaddress))
                                self.con.commit()

                                self.cur.execute("INSERT INTO device_info(device_id,device_type,vendor_name,device_model,device_model_id,"
                                                 "mac_address,identifiable,communication,date_added,factory_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                                 (_agent_id, device_type, device_vendor, device_model, device_model_id,
                                                  macaddress, device_identifiable, device_communication, datetime.datetime.now(),device_id))
                                self.con.commit()

                                self.cur.execute("INSERT INTO device_metadata(device_id,device_type,vendor_name,device_model,device_model_id,"
                                                 "mac_address,identifiable,communication,date_added) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                                 (_agent_id, device_type, device_vendor, device_model, device_model_id,
                                                  macaddress, device_identifiable, device_communication, datetime.datetime.now()))
                                self.con.commit()

                                self.cur.execute("INSERT INTO "+device_table+"("+device_table_id+", ip_address, nickname,zone_id,network_status,"
                                                 "last_scanned_time,last_offline_time)"
                                                 " VALUES(%s,%s,%s,%s,%s,%s,%s)",
                                                 (_agent_id, device_ip, device_nickname, zone_id, _device_network_status,
                                                 datetime.datetime.now(), datetime.datetime.now()))
                                self.con.commit()
                            else:
                                pass
                        else:
                            pass

        def launch_agent(self, dir, launch_file):
            _launch_file = os.path.join(dir, launch_file)
            os.system("bin/volttron-ctrl stop-agent " + launch_file)
            os.system("bin/volttron-ctrl load-agent " + _launch_file)
            os.system("bin/volttron-ctrl start-agent " + os.path.basename(_launch_file))
            os.system("bin/volttron-ctrl list-agent")
            print "{} >> has successfully launched {} located in {}".format(agent_id, launch_file, dir)

        def parseJSONresponse(self, data, key):
            theJSON = json.loads(data)
            return theJSON[key]

        def checkMACinDB(self, conn, macaddr):
            cur = conn.cursor()
            cur.execute("SELECT device_status FROM "+db_table_dashboard_device_info+" WHERE mac_address=%(id)s",
                        {'id': macaddr})
            if cur.rowcount != 0:
                mac_already_in_db = True
            else:
                mac_already_in_db = False
            return mac_already_in_db

        def getDeviceModel(self, data):
            theJSON = json.loads(data)
            return theJSON["model"]

        def getDeviceType(self, deviceModel):
            flag=0
            for queryvalue in deviceModel.split():
                for k,v in supportDevices.items(): #look up for catagory of the queryvalue
                    if queryvalue in supportDevices[k]:
                        #print(k)
                        flag=1
                        break #break for k,v loop
                    else:
                        flag = 0
                if flag == 1:
                    break #break for queryvalue loop
            if flag == 0:
                return 'Device model not found, Currently we don''t support this device'
            else:
                return k

        def getDeviceAPI(self, deviceModel):
            for queryvalue in deviceModel.split():
                for k,v in deviceAPIDocuments.items(): #look up for catagory of the queryvalue
                    if queryvalue in deviceAPIDocuments[k]:
                        flag=1
                        break #break for k,v loop
                    else:
                        flag = 0
                if flag == 1:
                    break #break for queryvalue loop
            if flag == 0:
                return 'Device API documentation not found, Currently we don''t support this device'
            else:
                return k

        def publish_subtopic(self, publish_item, topic_prefix):
            #TODO: Update to use the new topic templates
            if type(publish_item) is dict:
                # Publish an "all" property, converting item to json

                headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
                self.publish_json(topic_prefix + topic_delim + "all", headers, json.dumps(publish_item))
                print "WiFiTherAgent got"+str(type(publish_item))
                os.system("date");
                # Loop over contents, call publish_subtopic on each
                for topic in publish_item.keys():
                    self.publish_subtopic(publish_item[topic], topic_prefix + topic_delim + topic)

            else:
                # Item is a scalar type, publish it as is
                headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.PLAIN_TEXT
                self.publish(topic_prefix, headers, str(publish_item))
                print "Topic:{topic}={message}".format(topic=topic_prefix,message=str(publish_item))

        def write_launch_file(self, executable, agent_id, device_monitor_time, deviceModel, deviceVendor, deviceType,
                              api, deviceIP, db_host, db_port, db_database, db_user, db_password, address_get, address_put,
                              address_post, auth_header, smt_username, smt_password):
            data= {
                    "agent": {
                        "exec": executable+"-0.1-py2.7.egg --config \"%c\" --sub \"%s\" --pub \"%p\""
                    },
                    "agent_id": agent_id,
                    "device_monitor_time": device_monitor_time,
                    "model": deviceModel,
                    "vendor":deviceVendor,
                    "type": deviceType,
                    "api": api,
                    "address": deviceIP,
                    "db_host": db_host,
                    "db_port": db_port,
                    "db_database": db_database,
                    "db_user": db_user,
                    "db_password": db_password,
                    "address_get": address_get,
                    "address_put": address_put,
                    "address_post": address_post,
                    "auth_header": auth_header,
                    "smt_username": smt_username,
                    "smt_password": smt_password
                }
            __launch_file = os.path.join(Agents_Launch_DIR+agent_id+".launch.json")
            #print(__launch_file)
            with open(__launch_file, 'w') as outfile:
                json.dump(data, outfile, indent=4, sort_keys=True)

        def getRandomMAC(self):
            mac = [random.randint(0x00, 0x7f),
                    random.randint(0x00, 0x7f),
                    random.randint(0x00, 0x7f),
                    random.randint(0x00, 0x7f),
                    random.randint(0x00, 0xff),
                    random.randint(0x00, 0xff) ]
            return ''.join(map(lambda x: "%02x" % x, mac))

    Agent.__name__ = 'DeviceDiscoveryAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DeviceDiscoveryAgent, description='Device Discovery agent', argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass