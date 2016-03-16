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
from __future__ import division

import time
from bemoss_lib.protocols.BACnet.BACnetReadWrite import BACnetreadproperty, BACnetwriteproperty


class API:
    #constructor : gets call everytime when create a new class
    def __init__(self,**kwargs):
        #Initialized common attributes 
        self.variables = kwargs
        address = self.variables['address'].split('i')[0]
        if self.get_variable('model')=='LMRC-212':
            self.variables['dim_property_no'] = int(self.variables['address'].split('i')[1].split('n')[1])
        self.variables['address']= address

        self.set_variable('offline_count',0)

    #These set and get methods allow scalability 
    def set_variable(self,k,v): #k=key, v=value
        self.variables[k] = v

    def get_variable(self,k):
        return self.variables.get(k, None) #default of get_variable is none
            
        
    #Attributes from Attributes table
    '''
    Attributes: 
    ------------------------------------------------------------------------------------------
    Dimmer       GET    POST   Dim level percent (0-100) : 0 means OFF
    Current	     GET	       Current consumption
    ------------------------------------------------------------------------------------------ 
    ''' 

    #Capabilites (methods) from Capabilities table
    '''
    API available methods:
    1. getDeviceStatus() Read
    2. setDeviceStatus(parameter,value) Write
    3. identifyDevice() Write
    '''    

    #GET: read the data
    def getDeviceStatus(self):
        getDeviceStatusResult = True
        address = self.get_variable('address')
        try:
            if self.get_variable('model')=='LMRC-212':
                rp_dim_level=(BACnetreadproperty(address,1,self.get_variable('dim_property_no')))
                if (rp_dim_level is not None) or (rp_dim_level !=''):
                    dim_level=int(float(rp_dim_level))
                    self.set_variable('brightness',dim_level)
                    if dim_level==0:
                        self.set_variable('status',"OFF")
                    else:
                        self.set_variable('status',"ON")
                else:
                    getDeviceStatusResult = False
                rp_power=BACnetreadproperty(address,2,int((self.get_variable('dim_property_no')+1)/2))
                if (rp_power is not None) or (rp_power !=''):
                    self.set_variable('power',float(rp_power))
                else:
                    getDeviceStatusResult = False
            elif self.get_variable('model')=='LMPL-201':
                status=(BACnetreadproperty(address,4,1))
                if (status is not None) or (status !=''):
                    if status=='inactive':
                        self.set_variable('status',"OFF")
                    elif status=='active':
                        self.set_variable('status',"ON")
                else:
                    getDeviceStatusResult = False
                rp_power=BACnetreadproperty(address,2,2)
                if (rp_power is not None) or (rp_power !=''):
                    self.set_variable('power',float(rp_power))
                else:
                    getDeviceStatusResult = False
            elif self.get_variable('model')=='LMLS-400':
                rp_illuminance=BACnetreadproperty(address,0,4001)
                if (rp_illuminance is not None) or (rp_illuminance !=''):
                    self.set_variable('illuminance',int(float(rp_illuminance)/0.09290304))
                else:
                    getDeviceStatusResult = False
            elif self.get_variable('model')=='LMPC-100':
                occupancy=BACnetreadproperty(address,3,1)
                if (occupancy is not None) or (occupancy !=''):
                    if occupancy=='inactive':
                        self.set_variable('space_occupied',False)
                    elif occupancy=='active':
                        self.set_variable('space_occupied',True)
                else:
                    getDeviceStatusResult = False

            if getDeviceStatusResult==True:
                self.set_variable('offline_count',0)
            else:
                self.set_variable('offline_count',self.get_variable('offline_count')+1)

        except Exception as er:
            print "classAPI_BACnet_WattStopper: ERROR: Reading BACnet property at getDeviceStatus. Error: "+str(er)
            self.set_variable('offline_count',self.get_variable('offline_count')+1)

    #POST: Change status
    def setDeviceStatus(self, postmsg):
        setDeviceStatusResult = True
        address = self.get_variable('address')

        try:
            if self.get_variable('model')=='LMRC-212':
                if 'status' in postmsg.keys():
                    if postmsg.get('status') == "OFF":
                        ret=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),0)
                    elif postmsg.get('status') == "ON":
                        if 'brightness' in postmsg.keys():
                            ret=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),int(postmsg.get('brightness')))
                        else:
                            ret=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),100)
                    setDeviceStatusResult=ret
                elif 'brightness' in postmsg.keys():
                    ret=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),int(postmsg.get('brightness')))
                    setDeviceStatusResult=ret
            elif self.get_variable('model')=='LMPL-201':
                if 'status' in postmsg.keys():
                    if postmsg.get('status') == "OFF":
                        setDeviceStatusResult=BACnetwriteproperty(address,4,1,0)
                    elif postmsg.get('status') == "ON":
                        setDeviceStatusResult=BACnetwriteproperty(address,4,1,1)
        except:
            print "ERROR: Writing BACnet property at setDeviceStatus"
            setDeviceStatusResult=False
 
        return setDeviceStatusResult
            
    #Identify Device by toggling status twice
    def identifyDevice(self):
        identifyDeviceResult = False
        address = self.get_variable('address')
        try:
            if self.get_variable('model')=='LMRC-212':
                prev_dim_level=int(float(BACnetreadproperty(address,1,self.get_variable('dim_property_no'))))

                if prev_dim_level==0:
                    ret1=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),100)
                else:
                    ret1=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),0)
                if ret1:
                    self.timeDelay(5)
                    ret2=BACnetwriteproperty(address,1,self.get_variable('dim_property_no'),prev_dim_level)
                    identifyDeviceResult = ret2
            elif self.get_variable('model')=='LMPL-201':
                prev_status = (BACnetreadproperty(address,4,1))
                if prev_status=='inactive':
                    ret1=BACnetwriteproperty(address,4,1,1)
                    if (ret1):
                        self.timeDelay(5)
                        ret2=BACnetwriteproperty(address,4,1,0)
                        identifyDeviceResult = ret2
                elif prev_status=='active':
                    ret1=BACnetwriteproperty(address,4,1,0)
                    if (ret1):
                        self.timeDelay(5)
                        ret2=BACnetwriteproperty(address,4,1,1)
                        identifyDeviceResult = ret2
                    self.set_variable('status',"ON")
        except:
            print "ERROR: Reading/Writing BACnet property at identifyDevice"

        return identifyDeviceResult

    #time delay
    def timeDelay(self,time_iden): #specify time_iden for how long to delay the process
        t0 = time.time()
        self.seconds = time_iden
        while time.time() - t0 <= time_iden:
            self.seconds = self.seconds - 1
            print("wait: {} sec".format(self.seconds))
            time.sleep(1)

#This main method will not be executed when this class is used as a module
def main():
    #Utilization: test methods
    #Step1: create an object with initialized data from DeviceDiscovery Agent
    BACnetWattStopper = API(model='LMRC-212',type='lighting',api='API',address='830568i469810079n1')

    #Step2: Get data from device
    BACnetWattStopper.getDeviceStatus()
    print BACnetWattStopper.variables
    
    #Step3: change device operating set points
    BACnetWattStopper.setDeviceStatus({'brightness':20})
    # BACnetWattStopper.setDeviceStatus({'status':'ON'})

    #Step4: Identify Device
    BACnetWattStopper.identifyDevice()

if __name__ == "__main__": main()