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

'''This API class is for an agent that want to communicate/monitor/control
devices that compatible with Radio Thermostat Wi-Fi USNAP Module API Version 1.3 March 22, 2012
http://www.radiothermostat.com/documents/rtcoawifiapiv1_3.pdf'''

import urllib2 
import json
import time
import datetime
from DeviceAPI.discoverAPI import WiFi
from urlparse import urlparse

class API:
    # 1. constructor : gets call every time when create a new class
    # requirements for instantiation1. model, 2.type, 3.api, 4. address
    def __init__(self,**kwargs):  # default color is white
        # Initialized common attributes
        self.variables = kwargs
        self.debug = False
        self.set_variable('connection_renew_interval',6000)
        self.set_variable('offline_count', 0)


    def renewConnection(self):
        pass

    def set_variable(self,k,v):  # k=key, v=value
        self.variables[k] = v

    def get_variable(self,k):
        return self.variables.get(k, None)  #  default of get_variable is none

    # 2. Attributes from Attributes table
    '''
    Attributes: 
    GET: temp, override, tstate, fstate, t_type_post
    GET/POST: time=[day, hour, minute], tmode, t_heat, t_cool, fmode, hold
    POST: energy_led 
    ------------------------------------------------------------------------------------------
    temp            GET              current temp(deg F)
    override        GET              target temp temporary override (0:disabled, 1:enabled) 
    tstate          GET              HVAC operating state (0:OFF,1:HEAT,2:COOL)
    fstate          GET              fan operating state (0:OFF, 1:ON)
    t_type_post
    time            GET    POST      Thermostat's internal time (day:int,hour:int,minute:int)
    tmode           GET    POST      Thermostat operating mode (0:OFF,1:HEAT,2:COOL,3:AUTO)
    t_heat          GET    POST      temporary target heat setpoint (floating point in deg F)
    t_cool          GET    POST      temporary target 
    .cool setpoint (floating point in deg F)
    fmode           GET    POST      fan operating mode (0:AUTO,1:AUTO/CIRCULATE,2:ON)
    hold            GET    POST      target temp hold status (0:disabled, 1:enabled)
    energy_led             POST      energy LED status code (0:OFF,1:Green,2:Yellow,4:Red) 
    ------------------------------------------------------------------------------------------ 
    ''' 

    # 3. Capabilites (methods) from Capabilities table
    '''
    API1 available methods:
    1. getDeviceModel(url) GET
    2. getDeviceStatus(url) GET
    3. setDeviceStatus(url, postmsg) POST
    4. identifyDevice(url, idenmsg) POST
    '''    
    # GET Open the URL and obtain a model number of a device
    def getDeviceModel(self):
        _urlData = self.get_variable("address")

        try:
            _deviceModelUrl = urllib2.urlopen(_urlData+"/tstat/model", timeout=20)  # without data argument this is a GET command
            print(" {0}Agent is querying a model number (status:{1}) please wait ...".format(self.variables.get('agent_id',None), _deviceModelUrl.getcode()))
            if _deviceModelUrl.getcode() == 200:
                _deviceModel = self.getDeviceModelJson(_deviceModelUrl.read().decode("utf-8"))
                self.set_variable("deviceModel", _deviceModel)
                print(" {} model is {}\n".format(self.variables.get('agent_id', None), self.get_variable("deviceModel")))
            else:
                print(" wrong url for getting a device model number\n")
        except:
            print("Connection to {0}:{1} failed".format(self.get_variable("agent_id"),self.get_variable("model")))

    def getDeviceModelJson(self,data):
        _theJSON = json.loads(data)
        self.set_variable("deviceModel", _theJSON["model"])
        return _theJSON["model"]

    def rediscover(self):
        addresses= WiFi.discover('thermostat',timeout=15,retries=1) #rediscover addresses and use the one most similar to last one
        new_address = None
        for address in addresses:
            macaddress = WiFi.getMACaddress('thermostat', address)
            if macaddress == self.get_variable('macaddress'):
                new_address = address
                break

        if new_address != None:
            parsed = urlparse(new_address)
            new_address = parsed.scheme+"://"+parsed.netloc
            self.set_variable('address',new_address)
            with open(self.variables['config_path'],'r') as f:
                k = json.loads(f.read())
            k['address'] = new_address
            with open(self.variables['config_path'], 'w') as outfile:
                json.dump(k, outfile, indent=4, sort_keys=True)

    # GET Open the URL and read the data
    def getDeviceStatus(self):
        getDeviceStatusResult = True
        _urlData = self.get_variable("address")+'/tstat'
        try:
            _deviceUrl = urllib2.urlopen(_urlData, timeout=20)
            print(" {0}Agent is querying its current status (status:{1}) please wait ...".format(self.variables.get('agent_id',None), _deviceUrl.getcode()))
            if (_deviceUrl.getcode() == 200):
                jsonResult = _deviceUrl.read().decode("utf-8")
                self.getDeviceStatusJson(jsonResult)  # convert string data to JSON object
                if self.debug is True:
                    self.printDeviceStatus()
            else:
                getDeviceStatusResult = False
                print (" Received an error from server, cannot retrieve results " + str(_deviceUrl.getcode()))
        except Exception as er:
            print er
            getDeviceStatusResult = False

        if getDeviceStatusResult == True:
            self.set_variable('offline_count', 0)
        else:
            self.set_variable('offline_count', self.get_variable('offline_count') + 1)
            if self.get_variable('offline_count') >= 1:
                self.rediscover()

    def getDeviceStatusJson(self, data):
        # Use the json module to load the string data into a dictionary
        _theJSON = json.loads(data)
        self.set_variable('day',_theJSON["time"]["day"])   
        self.set_variable('hour',_theJSON["time"]["hour"])   
        self.set_variable('minute',_theJSON["time"]["minute"])
        self.set_variable('override',_theJSON["override"])
        # self.set_variable('hold',_theJSON["hold"])
        self.set_variable('t_type_post',_theJSON["t_type_post"])
        # now we can access the contents of the JSON like any other Python object
        # 1. temperature
        if _theJSON["temp"] == -1:
            pass
        else:
            self.set_variable('temperature',_theJSON["temp"])
        # 2. thermostat_mode
        if _theJSON["tmode"] == 0:
            self.set_variable('thermostat_mode', "OFF")
        elif _theJSON["tmode"] == 1:
            self.set_variable('thermostat_mode', "HEAT")
            self.set_variable('heat_setpoint',_theJSON["t_heat"])
        elif _theJSON["tmode"] == 2:
            self.set_variable('thermostat_mode', "COOL")
            self.set_variable('cool_setpoint',_theJSON["t_cool"])
        elif _theJSON["tmode"] == 3:
            self.set_variable('thermostat_mode', "AUTO")
        else: 
            print("Invalid value for device thermostat_mode")
        # 3. fan_mode
        if _theJSON["fmode"] == 0:
            self.set_variable('fan_mode', "AUTO")
        elif _theJSON["fmode"] == 1:
            self.set_variable('fan_mode', "CIRCULATE")
        elif _theJSON["fmode"] == 2:
            self.set_variable('fan_mode', "ON")
        else:
            print(" Invalid value for fan_mode")
        # 4. thermostat_state
        if _theJSON["tstate"] == 0:
            self.set_variable('thermostat_state', "OFF")
        elif _theJSON["tstate"] == 1:
            self.set_variable('thermostat_state', "HEAT")
        elif _theJSON["tstate"] == 2:
            self.set_variable('thermostat_state', "COOL")
        else:
            print(" Invalid value for thermostat_state")
        # 5. fan_state
        if _theJSON["fstate"] == 0:
            self.set_variable('fan_state', "OFF")
        elif _theJSON["fstate"] == 1:
            self.set_variable('fan_state', "ON")
        else:
            print(" Invalid value for fan_state")
        # 6. Follow Schedule/Temporary Hold/Permanent Hold
        if _theJSON["hold"] == 1:
            self.set_variable('hold', 2)
        else:
            schedule_setpoint = self.getScheduleSetpoint(datetime.datetime.now())
            if _theJSON['tmode'] == 1:
                if _theJSON['t_heat'] == schedule_setpoint[1]:
                    self.set_variable('hold', 0)
                else:
                    self.set_variable('hold', 1)
            elif _theJSON['tmode'] == 2:
                if _theJSON['t_cool'] == schedule_setpoint[0]:
                    self.set_variable('hold', 0)
                else:
                    self.set_variable('hold', 1)
        # return _theJSON["model"]

    def getDeviceSchedule(self):
        scheduleData = dict()
        try:
            _urlData = self.get_variable("address")
            _deviceUrl = urllib2.urlopen(_urlData+'/tstat', timeout=20)
            data_str = _deviceUrl.read().encode('utf8')
            data = json.loads(data_str)
            if data['hold']==0:
                scheduleData['Enabled']=True
            else:
                scheduleData['Enabled']=False
            tmode = data['tmode']   # thermostat operation state: 0:OFF, 1:HEAT, 2:COOL
            _getCool = urllib2.urlopen(_urlData+'/tstat/program/cool', timeout=20)
            cool_str = _getCool.read().encode('utf8')
            cool_sch = json.loads(cool_str)
            _getHeat = urllib2.urlopen(_urlData+'/tstat/program/heat', timeout=20)
            heat_str = _getHeat.read().encode('utf8')
            heat_sch = json.loads(heat_str)
            if tmode == 1:
                time_sch = heat_sch
            else:       # If HVAC is off, system shows cool schedule
                time_sch = cool_sch
            Days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            day = 0
            for item in Days:
                list1 = ['Morning']
                list2 = ['Day']
                list3 = ['Evening']
                list4 = ['Night']
                sch_time = time_sch[str(day)]
                cool_set = cool_sch[str(day)]
                heat_set = heat_sch[str(day)]
                list1.append(sch_time[0])
                list1.append(cool_set[1])
                list1.append(heat_set[1])
                list2.append(sch_time[2])
                list2.append(cool_set[3])
                list2.append(heat_set[3])
                list3.append(sch_time[4])
                list3.append(cool_set[5])
                list3.append(heat_set[5])
                list4.append(sch_time[6])
                list4.append(cool_set[7])
                list4.append(heat_set[7])
                listall = [list1, list2, list3, list4]
                scheduleData[item] = listall
                day += 1    # keep day and item the same day
        except Exception as er:
            print er
            print("Get device schedule failed @RadioThermostat API")
            raise er

        self.set_variable('scheduleData', scheduleData)

    def printDeviceStatus(self):
        print(" Day = {0} at {1}:{2}, the current status is as follows:".format(self.get_variable('day'),self.get_variable('hour'),self.get_variable('minute')))
        # 1. temperature
        print(" temperature = {}".format(self.get_variable('temperature')))
        print(" thermostat_mode = {}".format(self.get_variable('thermostat_mode')))
        if self.get_variable('thermostat_mode') == "HEAT":
            print(" heat_setpoint = {}".format(self.get_variable('heat_setpoint')))
        elif self.get_variable('thermostat_mode') == "COOL":
            print(" cool_setpoint = {}".format(self.get_variable('cool_setpoint')))
        print(" fan_mode = {}".format(self.get_variable('fan_mode')))
        print(" thermostat_state = {}".format(self.get_variable('thermostat_state')))
        print(" fan_state = {}".format(self.get_variable('fan_state')))
        # print(" override = {}".format(self.get_variable('override')))
        print(" hold = {}".format(self.get_variable('hold')))

    # POST Change thermostat parameters
    def setDeviceStatus(self, postmsg):
        setDeviceStatusResult = True
        # Ex. postmsg = {"tmode":1,"t_heat":85})
        # Ex. postmsg = {"thermostatmode":"HEAT","heat_setpoint":85})
        # step1: parse postmsg
        _urlData = self.get_variable("address")+'/tstat'
        # step2: send message to change status of the device
        if self.isPostmsgValid(postmsg) == True:  # check if the data is valid
            _data = json.dumps(self.convertPostMsg(postmsg))
            _data = _data.encode(encoding='utf_8')
            _request = urllib2.Request(_urlData)
            _request.add_header('Content-Type','application/json')
            try:
                _f = urllib2.urlopen(_request, _data, timeout=20)  # when include data this become a POST command
                print(" {0}Agent for {1} is changing its status with {2} please wait ...".format(self.variables.get('agent_id',None),
                                                                                             self.variables.get('model',None),
                                                                                             self.convertPostMsg(postmsg)))
            except:
                setDeviceStatusResult = False
            # print(" after send a POST request: {}".format(_f.read().decode('utf-8')))
        else:
            print("The POST message is invalid, check thermostat_mode, heat_setpoint, cool_coolsetpoint setting and try again\n")
        return setDeviceStatusResult

    def isPostmsgValid(self,postmsg):  # check validity of postmsg
        dataValidity = True
        for k,v in postmsg.items():
            if k == 'thermostat_mode':
                if postmsg.get('thermostat_mode') == "HEAT":
                    for k,v in postmsg.items():
                        if k == 'cool_setpoint':
                            dataValidity = False
                            break
                elif postmsg.get('thermostat_mode') == "COOL":
                    for k,v in postmsg.items():
                        if k == 'heat_setpoint':
                            dataValidity = False
                            break
        return dataValidity

    def convertPostMsg(self, postmsg):
        msgToDevice = dict()
        if 'thermostat_mode' not in postmsg:
            if 'heat_setpoint' in postmsg:
                self.set_variable("t_heat",postmsg.get("heat_setpoint"))
                msgToDevice = {"t_heat":self.get_variable("t_heat")}
            elif 'cool_setpoint' in postmsg:
                self.set_variable("t_cool",postmsg.get("cool_setpoint"))
                msgToDevice = {"t_cool":self.get_variable("t_cool")}
            else: pass
        else: pass
        for k,v in postmsg.items():
            if k == 'thermostat_mode':
                if postmsg.get('thermostat_mode') == "HEAT":
                    self.set_variable("tmode",1)
                    self.set_variable("t_heat",postmsg.get("heat_setpoint"))
                    msgToDevice = {"tmode":self.get_variable("tmode"),"t_heat":self.get_variable("t_heat")}
                elif postmsg.get('thermostat_mode') == "COOL":
                    self.set_variable("tmode",2)
                    self.set_variable("t_cool",postmsg.get("cool_setpoint"))
                    msgToDevice = {"tmode":self.get_variable("tmode"),"t_cool":self.get_variable("t_cool")}
                elif postmsg.get('thermostat_mode') == "OFF":
                    self.set_variable("tmode",0)
                    msgToDevice = {"tmode":self.get_variable("tmode")}
                elif postmsg.get('thermostat_mode') == "AUTO":
                    self.set_variable("tmode",3)
                    msgToDevice = {"tmode":self.get_variable("tmode")}
                else:
                    msgToDevice = {}
            if k == 'fan_mode':
                if postmsg.get('fan_mode') == "AUTO":
                    msgToDevice['fmode']=0
                elif postmsg.get('fan_mode') == "CIRCULATE":
                    msgToDevice['fmode']=1
                elif postmsg.get('fan_mode') == "ON":
                    msgToDevice['fmode']=2
                else:
                    print("invalid argument for fan_mode")
            if k == 'thermostat_state':
                if postmsg.get('thermostat_state') == "OFF":
                    msgToDevice['tstate']=0
                elif postmsg.get('thermostat_state') == "HEAT":
                    msgToDevice['tstate']=1
                elif postmsg.get('thermostat_state') == "COOL":
                    msgToDevice['tstate']=2
                else:
                    print("invalid argument for thermostat_state")
            if k == 'fan_state':
                if postmsg.get('fan_state') == "OFF":
                    msgToDevice['fstate']=0
                elif postmsg.get('fan_state') == "ON":
                    msgToDevice['fstate']=1
                else:
                    print("invalid argument for fan_state")
            if k == 'hold':
                if postmsg.get('hold') == 2:
                    msgToDevice['hold'] = 1
                else:
                    msgToDevice['hold'] = 0
        if 'hold' in postmsg.keys():
            if postmsg.get('hold') == 0:
                schedule_setpoint = self.getScheduleSetpoint(datetime.datetime.now())
                if postmsg.get('thermostat_mode') == "HEAT":
                    self.set_variable("t_heat",schedule_setpoint[1])
                    msgToDevice['t_heat'] = schedule_setpoint[1]
                elif postmsg.get('thermostat_mode') == "COOL":
                    self.set_variable("t_cool",schedule_setpoint[0])
                    msgToDevice['t_heat'] = schedule_setpoint[0]
        return msgToDevice

    def setDeviceSchedule(self, scheduleData):
        _urlData = self.get_variable("address")+'/tstat'
        if scheduleData['Enabled'] == False:
            msg = {"hold":1}
            _request = urllib2.Request(_urlData)
            _request.get_method = lambda: 'POST'
            try:
                f = urllib2.urlopen(_request, msg, timeout=20)
                if f.getcode() == 200:
                    print "Thermostat " + self.variables.get("agent_id") + " is on hold now!"
                else:
                    print "Thermostat " + self.variables.get("agent_id") + " setting HOLD failed! "
            except Exception as er:
                print er
                print("Failure setting schedule HOLD @ RadioThermostat API")
        else:
            url_coolset = self.get_variable("address")+'/tstat/program/cool'
            url_heatset = self.get_variable("address")+'/tstat/program/heat'
            cool_sch = dict()
            heat_sch = dict()
            Days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            keys = ["0","1","2","3","4","5","6"]
            day = 0
            for item in Days:
                day_list = scheduleData[item]
                cool_list = list()
                heat_list = list()
                for period in day_list:
                    cool_list.append(period[1])
                    heat_list.append(period[1])
                    cool_list.append(period[2])
                    heat_list.append(period[3])
                if len(cool_list) < 8:
                    while len(cool_list)<8:
                        add1 = cool_list[-2]
                        add2 = cool_list[-1]
                        cool_list.append(add1)
                        cool_list.append(add2)
                if len(heat_list) < 8:
                    while len(heat_list)<8:
                        add1 = heat_list[-2]
                        add2 = heat_list[-1]
                        heat_list.append(add1)
                        heat_list.append(add2)
                cool_sch[keys[day]] = cool_list
                heat_sch[keys[day]] = heat_list

                day += 1

            _request = urllib2.Request(url_coolset)
            _request.get_method = lambda: 'POST'
            cool_sch_str = str(cool_sch)
            cool_sch_str = cool_sch_str.replace('\'','"')
            try:
                f = urllib2.urlopen(_request, cool_sch_str, timeout=20)
                if f.getcode() == 200:
                    print('Cool schedule updated!')
                else:
                    print('Cool schedule updated failed!')
            except Exception as er:
                print er
                print("Failure setting cool schedule @ RadioThermostat API")

            _request = urllib2.Request(url_heatset)
            _request.get_method = lambda: 'POST'
            heat_sch_str = str(heat_sch)
            heat_sch_str = heat_sch_str.replace('\'','"')
            try:
                f = urllib2.urlopen(_request, heat_sch_str, timeout=20)
                if f.getcode() == 200:
                    print('Heat schedule updated!')
                else:
                    print('Heat schedule updated failed!')
            except Exception as er:
                print er
                print("Failure setting heat schedule @ RadioThermostat API")

    # Identify this device
    def identifyDevice(self):
        identifyDeviceResult = False
        _data = json.dumps({'energy_led': 2})
        _data = _data.encode(encoding='utf_8')
        _request = urllib2.Request(self.get_variable('address')+"/tstat/led")
        _request.add_header('Content-Type','application/json')
        try:
            _f = urllib2.urlopen(_request, _data, timeout=20) #when include data this become a POST command
            print(" after send a POST request: {}".format(_f.read().decode('utf-8')))
        except:
            print("ERROR: classAPI_RadioThermostat connection failure! @ identifyDevice")
        print(" {0}Agent for {1} is identifying itself by changing LED light to yellow for 10 seconds "
              "then back to green please wait ...".format(self.variables.get('device_type', None),
                                                          self.variables.get('model', None)))
        _data = json.dumps({'energy_led': 1})
        _data = _data.encode(encoding='utf_8')
        _request = urllib2.Request(self.get_variable('address')+"/tstat/led")
        _request.add_header('Content-Type','application/json')
        try:
            self.timeDelay(10)
            _f = urllib2.urlopen(_request, _data, timeout=20) #when include data this become a POST command
            print(" after send a POST request: {}".format(_f.read().decode('utf-8')))
            identifyDeviceResult = True
        except:
            print("ERROR: classAPI_RadioThermostat connection failure! @ identifyDevice")
        return identifyDeviceResult

    # time delay
    def timeDelay(self,time_iden): #specify time_iden for how long to delay the process
        t0 = time.time()
        self.seconds = time_iden
        while time.time() - t0 <= time_iden:
            self.seconds = self.seconds - 1
            print("wait: {} sec".format(self.seconds))
            time.sleep(1)


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
                setPoints = [int(entries[2]),int(entries[3])]
            else:
                break
        return setPoints

# This main method will not be executed when this class is used as a module
def main():
    # Step1: create an object with initialized data from DeviceDiscovery Agent
    # requirements for instantiation1. model, 2.type, 3.api, 4. address
    CT50Thermostat = API(model='CT50',agent_id='wifithermostat1',api='API1',address='192.168.10.160')
    print("{0}agent is initialzed for {1} using API={2} at {3}".format(CT50Thermostat.get_variable('agent_id'),CT50Thermostat.get_variable('model'),CT50Thermostat.get_variable('api'),CT50Thermostat.get_variable('address')))
    #CT50Thermostat.getDeviceModel()
    CT50Thermostat.getDeviceSchedule()
    CT50Thermostat.setDeviceStatus({"thermostat_mode":"HEAT","heat_setpoint":78,"hold":1})
    #CT50Thermostat.getDeviceStatus()
    # CT50Thermostat.identifyDevice()
    # scheduleData = {'Enabled': True, 'monday':[['Morning', 50, 83, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]], 'tuesday':[['Morning', 360 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],'wednesday':[['Morning', 300 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],'thursday':[['Morning', 360 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],'friday':[['Morning', 360 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],'saturday':[['Morning', 360 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],'sunday':[['Morning', 360 , 70, 80],['Day',480, 72, 82],['Evening',960, 71, 84],['Night',1000, 69, 72]],}
    # CT50Thermostat.setDeviceSchedule(scheduleData)

if __name__ == "__main__": main()