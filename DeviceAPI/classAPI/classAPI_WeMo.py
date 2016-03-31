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
devices that compatible with WeMo API'''

import re
import requests
from xml.dom import minidom
import time
import json
import datetime
import socket
from bemoss_lib.utils.find_own_ip import getIPs
import threading
import random
from DeviceAPI.discoverAPI import WiFi


def keepListening(threadingLock, address, port, callback):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(600)
    sock.bind((address,port))
    sock.listen(10)
    state =-1
    power = -1
    # print 'accepting connection:'
    while 1:
        try:
            conn, addr =  sock.accept()
            conn.setblocking(1)
            while 1:
                kk = conn.recv(1024)
                if not kk:
                    break
                conn.send('HTTP/1.1 200 OK\n\n')
                #print 'HTTP/1.1 200 OK\n\n'
                x=re.search('<BinaryState>([0-9])(\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*)\|([0-9]*))?</BinaryState>',kk)
                if not x == None:
                    s = x.group(1)
                    p = x.group(9)
                    if (state != int(s)): #if the new state is different than old state, we got new data
                        power = p
                        state = s
                        if not power == None: #if Power data also available report back
                            callback({'status':int(state), 'power':float(power)/1000})
                        else: #if not just the status
                            callback({'status':int(state)})
                    elif p != None and p!=power: #if power is different report back
                        power = p
                        state = s
                        callback({'status':int(state), 'power':float(power)/1000})

                        #print 'power',float(power)/1000

                    #print kk
        except Exception as er:
            kk = None
            state = -1
            print er

class API:
    # 1. constructor : gets call every time when create a new class
    # requirements for instantiation1. model, 2.api, 3. address
    def __init__(self,**kwargs):  # default color is white
        # Initialized common attributes
        self.variables = kwargs
        self.debug = False
        self.set_variable('connection_renew_interval',600)
        self.listeningThread = None
        self.set_variable('offline_count',0)


    # Attributes from Attributes table
    '''
    Attributes:
     ------------------------------------------------------------------------------------------
    WeMo Plug
    status       GET    POST      Smart plug ON/OFF status
    power        GET    POST      WeMo Insigth power consumption (float point in Watt)
     ------------------------------------------------------------------------------------------

    '''

    #Capabilites (methods) from Capabilities table
    '''
    API3 available methods:
    1. getDeviceStatus() GET
    2. setDeviceStatus(postmsg) PUT
    3. identifyDevice()
    '''

    # These set and get methods allow scalability
    def startListeningEvents(self,threadingLock,callback):

        def common_start(sa, sb):
            """ returns the longest common substring from the beginning of sa and sb """
            def _iter():
                for a, b in zip(sa, sb):
                    if a == b:
                        yield a
                    else:
                        return

            return ''.join(_iter())

        _address = self.get_variable('address')
        _address = _address.replace('http://', '')
        _address = _address.replace('https://', '')
        ips = getIPs()
        #if no good match, use the last ip
        myaddress = ips[-1]
        maxmatch = ''
        for ip in ips:
            tempmatch = common_start(ip,_address)
            if len(tempmatch)>len(maxmatch):
                myaddress = ip #If bemoss machine has multiple IP, use that IP most similar to address of WEMO device
                maxmatch=tempmatch

        if self.listeningThread is None: #if this is firt time, and no thread present
            self.port = random.randint(10000,60000)
            self.listeningThread = threading.Thread(target=keepListening,args=(threadingLock,myaddress,self.port, callback))
            self.listeningThread.start()
            time.sleep(1)

        message = {
            'CALLBACK': '<http://'+myaddress+':'+str(self.port)+'>',
            'NT': 'upnp:event',
            'TIMEOUT': 'Second-800',
            'HOST': _address}
        self.reqresult = requests.request('SUBSCRIBE',self.get_variable('address')+'/upnp/event/basicevent1',headers=message)
        if self.reqresult.status_code != 200:
            print "Subscription error."
            print str(self.reqresult)
            return

        self.sid = self.reqresult.headers['sid']
        self.myaddress = myaddress
        self._address = _address
        self.callback = callback

    def renewConnection(self):
        message2 = {
        'SID': self.sid,
        'TIMEOUT': 'Second-800',
        'HOST': self._address}
        try:
            k2 = requests.request('SUBSCRIBE',self.get_variable('address')+'/upnp/event/basicevent1', headers=message2)
            if k2.status_code != 200:
                print "Connection error"
                self.rediscover()
                return
        except requests.ConnectionError as er:
            print er, 'Problem subscribing. Rediscovering...'
            self.rediscover()
            return

        print 'subscription renewed'

    def set_variable(self,k,v):  # k=key, v=value
        self.variables[k] = v

    def get_variable(self,k):
        return self.variables.get(k, None)  # default of get_variable is none


    def rediscover(self):
        addresses= WiFi.discover('WeMo',timeout=5,retries=3) #rediscover addresses and find oneself again using mac
        new_address = None
        for address in addresses:
            macaddress = WiFi.getMACaddress('WeMo', address)
            if macaddress == self.get_variable('macaddress'):
                new_address = address
                break

        if new_address != None:
            new_address = new_address.replace('/setup.xml','')
            self.set_variable('address',new_address)
            self.startListeningEvents(None,None) #no need to start new listening thread so passing none arguments
            with open(self.variables['config_path'],'r') as f:
                k = json.loads(f.read())
            k['address'] = new_address
            with open(self.variables['config_path'], 'w') as outfile:
                json.dump(k, outfile, indent=4, sort_keys=True)

    #GET device status by XML read
    def getDeviceStatus(self):
        print "----------------------------------------------------------------"
        print "{0}Agent is querying its current status at {1} please wait ...".format(self.variables.get('agent_id',None),
                                                                                      datetime.datetime.now())
        getDeviceStatusResult = True
        if self.get_variable("model") == "Insight":
            SOAPACTION = '"urn:Belkin:service:insight:1#GetInsightParams"'
            body="<?xml version='1.0' encoding='utf-8'?><s:Envelope xmlns:s='http://schemas.xmlsoap.org/soap/envelope/' s:encodingStyle='http://schemas.xmlsoap.org/soap/encoding/'><s:Body><u:GetInsightParams xmlns:u='urn:Belkin:service:insight:1'></u:GetInsightParams></s:Body></s:Envelope>"
            controlUrl=self.get_variable('address')+'/upnp/control/insight1'
        elif self.get_variable("model") == "Socket" or self.get_variable("model") == "LightSwitch":
            SOAPACTION = '"urn:Belkin:service:basicevent:1#GetBinaryState"'
            body="<?xml version='1.0' encoding='utf-8'?><s:Envelope xmlns:s='http://schemas.xmlsoap.org/soap/envelope/' s:encodingStyle='http://schemas.xmlsoap.org/soap/encoding/'><s:Body><u:GetBinaryState xmlns:u='urn:Belkin:service:basicevent:1'></u:GetBinaryState></s:Body></s:Envelope>"
            controlUrl=self.get_variable('address')+'/upnp/control/basicevent1'

        else:
            "{0}Agent : currently Wemo device model {1} is not supported by BEMOSS".format(self.variables.get('agent_id',None),self.get_variable("model"))
            return

        header = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': SOAPACTION
            #old
            #'SOAPACTION': '"urn:Belkin:service:basicevent:1#GetBinaryState"'
        }
        try:
            response = requests.post(controlUrl, body, headers=header, timeout=10)
            if self.debug: print str(response.content)
            else: pass
            dom = minidom.parseString(response.content)
            if self.get_variable("model") == "Insight":
                if self.debug: print str(dom.getElementsByTagName('InsightParams')[0].firstChild.data)
                else: pass
                reading_data = str(dom.getElementsByTagName('InsightParams')[0].firstChild.data).split('|')
                print "State|Seconds of last state change|last on seconds|Seconds on today|unknown|Total Seconds|unknown|Power(mW)|" \
                      "Energy used today (mW*min)|Energy used total (mW*min)|unknown"
                print "reading_data = {}".format(reading_data)
                if int(reading_data[0]) == 0 | False: self.set_variable('status', "OFF")
                else: self.set_variable('status', "ON")
                if float(reading_data[7]) is not None: self.set_variable('power', float(reading_data[7])/1000)
                else: pass
            elif self.get_variable("model") == "Socket" or self.get_variable("model") == "LightSwitch":
                if int(dom.getElementsByTagName('BinaryState')[0].firstChild.data) == 0|False:
                    self.set_variable('status',"OFF")
                elif int(dom.getElementsByTagName('BinaryState')[0].firstChild.data) == 1|True:
                    self.set_variable('status',"ON")

            else:
                "{0}Agent : currently Wemo device model {1} is not supported by BEMOSS".format(self.variables.get('agent_id',None),self.get_variable("model"))
            if self.debug: self.printDeviceStatus()
        except requests.ConnectionError as er:
            getDeviceStatusResult = False
            print("ERROR: classAPI_WeMo connection failure! @ getDeviceStatus")
            print er
            self.rediscover()

        if getDeviceStatusResult==True:
            self.set_variable('offline_count',0)
        else:
            self.set_variable('offline_count',self.get_variable('offline_count')+1)

    def printDeviceStatus(self):
        print(" The current Wemo status is as follows:")
        print(" status = {}".format(self.get_variable('status')))
        if self.get_variable('power') is not None: print " power = {}".format(self.get_variable('power'))
        else: pass

    #POST Change status
    def setDeviceStatus(self, newstatus):
        setDeviceStatusResult = True
        header = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPACTION': '"urn:Belkin:service:basicevent:1#SetBinaryState"'
            }
        # Data conversion before passing to the device
        _data = json.dumps(newstatus)
        _data = json.loads(_data)

        if _data['status'] == "OFF":
            newstatus = 0
        elif _data['status'] == "ON":
            newstatus = 1

        body="<?xml version='1.0' encoding='utf-8'?><s:Envelope xmlns:s='http://schemas.xmlsoap.org/soap/envelope/' " \
             "s:encodingStyle='http://schemas.xmlsoap.org/soap/encoding/'><s:Body><u:SetBinaryState " \
             "xmlns:u='urn:Belkin:service:basicevent:1'><BinaryState>"+str(int(newstatus))\
             +"</BinaryState></u:SetBinaryState></s:Body></s:Envelope>"

        controlUrl=self.get_variable('address')+'/upnp/control/basicevent1'
        try:
            response = requests.post(controlUrl, body, headers=header)
            dom = minidom.parseString(response.content)
            responsestatus = dom.getElementsByTagName('BinaryState')[0].firstChild.data
            if responsestatus!='Error':
                pass
            else:
                print("ERROR: classAPI_WeMo action failure! @ setDeviceStatus")
                # self.set_variable('status',int(responsestatus))
        except:
            print("ERROR: classAPI_WeMo connection failure! @ setDeviceStatus")
            setDeviceStatusResult = False
        self.getDeviceStatus()
        self.set_variable('status', self.get_variable('status'))
        return setDeviceStatusResult
            
    #Identify Device by Toggling device status twice
    def identifyDevice(self):
        identifyDeviceResult = False
        try:
            self.getDeviceStatus()
            self.toggleDeviceStatus()
            print(self.get_variable("model")+" is being identified with starting status "+str(self.get_variable('status')))
            self.timeDelay(5)
            self.toggleDeviceStatus()
            print("Identification for "+self.get_variable("model")+" is done with status "+str(self.get_variable('status')))
            identifyDeviceResult = True
        except:
            print("ERROR: classAPI_WeMo connection failure! @ identifyDevice")
        return identifyDeviceResult

    # ------------ Helper Methods -------------------------------------
    #GET current status and POST toggled status
    def toggleDeviceStatus(self):
        if self.get_variable('status') == "ON":
            self.setDeviceStatus({"status":"OFF"})
        else:
            self.setDeviceStatus({"status":"ON"})

    # method6: time delay
    def timeDelay(self,time_iden):  # specify time_iden for how long to delay the process
        t0 = time.time()
        self.seconds = time_iden
        while time.time() - t0 <= time_iden:
            self.seconds = self.seconds - 1
            print("wait: {} sec".format(self.seconds))
            time.sleep(1)
    # -----------------------------------------------------------------

# This main method will not be executed when this class is used as a module
def main():
    # Test Codes

    WeMoSwitch = API(model='Insight', api='classAPI_WeMo', address='http://192.168.10.159:49153', agent_id='plugloadagent')
    # Find device Model
    # print WeMoSwitch.getDeviceModel()
    # Get and Print Device Status
    def dummy(status):
        print 'x'
        print status
    k = threading.Lock
    WeMoSwitch.startListeningEvents(k,dummy)
    WeMoSwitch.getDeviceStatus()
    x = WeMoSwitch.get_variable('motion')
    # WeMoSwitch.identifyDevice()
    # WeMoSwitch.setDeviceStatus({"status": "ON"})
    print x

if __name__ == "__main__": main()