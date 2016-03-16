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

import time
import urllib2
import json
from bemoss_lib.utils import rgb_cie
class API:
    # 1. constructor : gets call every time when create a new class
    # requirements for instantiation1. model, 2.type, 3.api, 4. address
    def __init__(self,**kwargs):  # default color is white
        # Initialized common attributes
        self.variables = kwargs
        self.debug = False
        self.set_variable('offline_count',0)
        self.set_variable('connection_renew_interval',6000) #nothing to renew, right now
    def renewConnection(self):
        pass

    def set_variable(self,k,v):  # k=key, v=value
        self.variables[k] = v

    def get_variable(self,k):
        return self.variables.get(k, None)  # default of get_variable is none

    # 2. Attributes from Attributes table
    '''
    Attributes: 
    ''' 

    # 3. Capabilites (methods) from Capabilities table
    '''
    API3 available methods:
    1. getDeviceStatus() GET
    2. setDeviceStatus(postmsg) PUT
    3. identifyDevice()
    '''    

    # ----------------------------------------------------------------------
    # getDeviceStatus(), getDeviceStatusJson(data), printDeviceStatus()
    def getDeviceStatus(self):
        getDeviceStatusResult = True
        _hue_username = self.get_variable("username")
        _url_append = '/api/'+_hue_username+'/groups/0/'
        _urlData = self.get_variable("address").replace(':80', _url_append)
        try:
            _deviceUrl = urllib2.urlopen(_urlData, timeout=20)
            print(" {0}Agent is querying its current status (status:{1}) please wait ...".
                  format(self.variables.get('agent_id', None), _deviceUrl.getcode()))
            if (_deviceUrl.getcode() == 200):
                self.getDeviceStatusJson(_deviceUrl.read().decode("utf-8")) #convert string data to JSON object then interpret it
                if self.debug is True:
                    self.printDeviceStatus()
            else:
                print (" Received an error from server, cannot retrieve results " + str(_deviceUrl.getcode()))
                getDeviceStatusResult = False
            # Check the connectivity
            if getDeviceStatusResult==True:
                self.set_variable('offline_count', 0)
            else:
                self.set_variable('offline_count', self.get_variable('offline_count')+1)
        except:
            print('ERROR: classAPI_PhilipsHue failed to getDeviceStatus')
            self.set_variable('offline_count',self.get_variable('offline_count')+1)

    def getDeviceStatusJson(self,data):  
        # Use the json module to load the string data into a dictionary
        _theJSON = json.loads(data)
        # 1. status
        if _theJSON["action"]["on"] == True:
            self.set_variable('status',"ON")
        else:
            self.set_variable('status',"OFF")
        # 2. brightness convert to %
        self.set_variable('brightness',int(round(float(_theJSON["action"]["bri"])*100/255,0)))
        # 3. color convert to RGB 0-255
        self.set_variable('hue', _theJSON["action"]["hue"])
        self.set_variable('xy', _theJSON["action"]["xy"])
        self.set_variable('ct', _theJSON["action"]["ct"])
        x=_theJSON["action"]["xy"][0]
        y=_theJSON["action"]["xy"][1]
        self.set_variable('color', rgb_cie.ColorHelper.getRGBFromXYAndBrightness(x,y,_theJSON["action"]["bri"]))
        self.set_variable('hexcolor', '#%02x%02x%02x' % self.get_variable('color'))
        # 4. saturation convert to %
        self.set_variable('saturation',int(round(float(_theJSON["action"]["sat"])*100/255,0)))
        self.set_variable('effect',_theJSON["action"]["effect"])
        self.set_variable('colormode',_theJSON["action"]["colormode"])
        for k in _theJSON["lights"]:
            self.set_variable("lights{}".format(k), k)
        self.set_variable('number_lights', len(_theJSON["lights"]))
        self.set_variable('name',_theJSON["name"])
        
    def printDeviceStatus(self):
        # now we can access the contents of the JSON like any other Python object
        print(" the current status is as follows:")
        print(" name = {}".format(self.get_variable('name')))
        print(" number_lights = {}".format(self.get_variable('number_lights')))
        print(" status = {}".format(self.get_variable('status')))
        print(" brightness = {}".format(self.get_variable('brightness')))
        print(" hue = {}".format(self.get_variable('hue')))
        print(" color = {}".format(self.get_variable('color')))
        print(" saturation = {}".format(self.get_variable('saturation')))
        print(" xy= {}".format(self.get_variable('xy')))
        print(" ct = {}".format(self.get_variable('ct')))
        print(" effect = {}".format(self.get_variable('effect')))
        print(" colormode = {}\n".format(self.get_variable('colormode')))
    # ----------------------------------------------------------------------
    # setDeviceStatus(postmsg), isPostmsgValid(postmsg), convertPostMsg(postmsg)
    def setDeviceStatus(self, postmsg):
        setDeviceStatusResult = True
        #Ex. postmsg = {"on":True,"bri":100,"hue":50260,"sat":200}
        _hue_username = self.get_variable("username")
        _url_append = '/api/'+_hue_username+'/groups/0/'
        _urlData = self.get_variable("address").replace(':80', _url_append)
        if self.isPostMsgValid(postmsg) == True: #check if the data is valid
            _data = json.dumps(self.convertPostMsg(postmsg))
            _data = _data.encode(encoding='utf_8')
            _request = urllib2.Request(_urlData+'action')
            _request.add_header('Content-Type','application/json')
            _request.get_method = lambda: 'PUT'
            try:
                _f = urllib2.urlopen(_request, _data, timeout=20) #when include data this become a POST command
                print(" {0}Agent for {1} is changing its status with {2} please wait ..."
                .format(self.variables.get('agent_id', None), self.variables.get('model', None), postmsg))
                print(" after send a POST request: {}".format(_f.read().decode('utf-8')))
            except:
                print("ERROR: classAPI_PhilipsHue connection failure! @ setDeviceStatus")
                setDeviceStatusResult = False
        else:
            print("The POST message is invalid, try again\n")
        return setDeviceStatusResult
            
    def isPostMsgValid(self,postmsg): #check validity of postmsg
        dataValidity = True
        #TODO algo to check whether postmsg is valid 
        return dataValidity
    

    def convertPostMsg(self,postmsg):
        msgToDevice = {}
        datacontainsRGB=False
        if 'color' in postmsg.keys():
            datacontainsRGB=True
            
        for k,v in postmsg.items():
            if k == 'status':
                if postmsg.get('status') == "ON":
                    msgToDevice['on'] = True
                elif postmsg.get('status') == "OFF":
                    msgToDevice['on'] = False
            elif k == 'brightness':
                msgToDevice['bri'] = int(round(float(postmsg.get('brightness'))*255.0/100.0,0))
            elif k == 'color':
                print(type(postmsg['color']))
                _red = postmsg['color'][0]
                _green = postmsg['color'][1]
                _blue = postmsg['color'][2]
                _xyY = rgb_cie.ColorHelper.getXYPointFromRGB(_red, _green, _blue)
                msgToDevice['xy'] = [_xyY.x, _xyY.y]
                #msgToDevice['bri']= int(round(_xyY.y*255,0))
            elif k == 'hue':
                if datacontainsRGB==False:
                    msgToDevice['hue'] = postmsg.get('hue')
            elif k == 'saturation':
                if datacontainsRGB==False:
                    msgToDevice['sat'] = int(round(float(postmsg.get('saturation'))*255.0/100.0,0))
            else:
                msgToDevice[k] = v
        return msgToDevice
    # ----------------------------------------------------------------------
    # method3: Identify this lights (Physically)
    def identifyDevice(self):
        identifyDeviceResult = False
        print(" {0}Agent for {1} is identifying itself by doing colorloop. Please observe your lights"
              .format(self.variables.get('agent_id',None), self.variables.get('model',None)))
        try:
            devicewasoff=0
            if self.get_variable('status')=="OFF":
                devicewasoff=1
                self.setDeviceStatus({"status":"ON"})
            self.setDeviceStatus({"effect": "colorloop"})
            time_iden = 10 #time to do identification
            t0 = time.time()
            self.seconds = time_iden
            while time.time() - t0 <= time_iden:
                self.seconds = self.seconds - 1
                print("wait: {} sec".format(self.seconds))
                time.sleep(1)
            self.setDeviceStatus({"effect": "none"})
            if devicewasoff==1:
                self.setDeviceStatus({"status":"OFF"})
            identifyDeviceResult = True
        except:
            print("ERROR: classAPI_PhilipsHue connection failure! @ identifyDevice")
        return identifyDeviceResult
    # ----------------------------------------------------------------------

# This main method will not be executed when this class is used as a module
def main():
    # create an object with initialized data from DeviceDiscovery Agent
    # requirements for instantiation1. model, 2.type, 3.api, 4. address
    PhilipsHue = API(model='Philips Hue',type='wifiLight',api='API3',address='http://192.168.10.14:80',username='acquired username',agent_id='LightingAgent')
    print("{0}agent is initialzed for {1} using API={2} at {3}".format(PhilipsHue.get_variable('type'),PhilipsHue.get_variable('model'),PhilipsHue.get_variable('api'),PhilipsHue.get_variable('address')))

    PhilipsHue.setDeviceStatus({"status":"ON","color":(155,113,255)})
    PhilipsHue.identifyDevice()


if __name__ == "__main__": main()