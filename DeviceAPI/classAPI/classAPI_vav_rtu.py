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
#!/usr/bin/python3
'''
This API class is for an agent that want to communicate/monitor/control
devices that compatible with Prolon VC1000 or M1000
Avijit Saha 10/10/2014
'''

from pymodbus.client.sync import ModbusTcpClient


class API:
    #1. constructor : gets call everytime when create a new class
    #requirements for instantiation1. model, 2.type, 3.api, 4. address
    def __init__(self,**kwargs): #default color is white
        #Initialized common attributes
        self.variables = kwargs
        address_parts = self.get_variable('address').split(':')
        self.set_variable('address',address_parts[0])
        self.set_variable('subordinate_id',int(address_parts[1]))
        self.set_variable('offline_count',0)
        self.set_variable('connection_renew_interval',6000) #nothing to renew


    def renewConnection(self):
        pass

    def set_variable(self,k,v): #k=key, v=value
        self.variables[k] = v

    def get_variable(self,k):
        return self.variables.get(k, None) #default of get_variable is none


    #2. Attributes from Attributes table
    '''
    Attributes:
    ------------------------------------------------------------------------------------------
    temperature               GET           temperature reading (floating point in deg F)
    heat_setpoint             GET    POST   target heat setpoint (floating point in deg F)
    cool_setpoint             GET    POST   target cool setpoint (floating point in deg F)
    supply_temperature        GET           RTU supply temperature (floating point in deg F)
    return_temperature        GET           RTU supply temperature (floating point in deg F)
    flap_override             GET    POST   flap override('ON'/'OFF')
    flap_position             GET    POST   flap position, int
    outside_temperature       GET           outside temperature from RTU sensor (floating point in deg F)
    pressure                  GET           presure
    outside_damper_position   GET    POST   outside damper position, int
    bypass_damper_position    GET    POST   outside damper position, int
    fan_status                GET    POST   RTU fan status('ON'/'OFF')
    cooling_status            GET    POST   RTU cooling status('ON'/'OFF')
    cooling_mode              GET    POST   RTU cooling mode('None'/'STG1'/'STG2')
    ------------------------------------------------------------------------------------------
    '''


    #3. Capabilites (methods) from Capabilities table
    '''
    API available methods:
    1. getDeviceStatus() Read
    2. setDeviceStatus(parameter,value) Write
    3. identifyDevice() Write
    '''

    #method1: GET Open the port and read the data
    def getDeviceStatus(self):
        getDeviceStatusResult = True
        try:
            client = ModbusTcpClient(self.get_variable('address'),port=502)
            client.connect()
            if (self.get_variable('model')=='VC1000'):
                result = client.read_input_registers(0,8,unit=self.get_variable('subordinate_id'))
                if int(result.registers[0])==32767:
                    self.set_variable('temperature',None)
                else:
                    self.set_variable('temperature',float('%.1f' % self.cel2far(float(int(result.registers[0]))/100.0)))
                self.set_variable('heat_setpoint',float('%.1f' % self.cel2far(float(int(result.registers[1]))/100.0)))
                self.set_variable('cool_setpoint',float('%.1f' % self.cel2far(float(int(result.registers[2]))/100.0)))
                if int(result.registers[7])==32767:
                    self.set_variable('supply_temperature',None)
                else:
                    self.set_variable('supply_temperature',float('%.1f' % self.cel2far(float(int(result.registers[7]))/100.0)))
                result = client.read_holding_registers(159,2,unit=self.get_variable('subordinate_id'))
                if (int(result.registers[0])==1):
                    self.set_variable('flap_override','ON')
                else:
                    self.set_variable('flap_override','OFF')
                self.set_variable('flap_position',int(result.registers[1]))
            elif (self.get_variable('model')=='M1000'):
                result = client.read_input_registers(0,26,unit=self.get_variable('subordinate_id'))
                if int(result.registers[18])==32767:
                    self.set_variable('temperature',None)
                else:
                    self.set_variable('temperature',float('%.1f' % self.cel2far(float(int(result.registers[18]))/100.0)))
                self.set_variable('heat_setpoint',float('%.1f' % self.cel2far(float(int(result.registers[19]))/100.0)))
                self.set_variable('cool_setpoint',float('%.1f' % self.cel2far(float(int(result.registers[20]))/100.0)))
                if int(result.registers[0])==32767:
                    self.set_variable('supply_temperature',None)
                else:
                    self.set_variable('supply_temperature',float('%.1f' % self.cel2far(float(int(result.registers[0]))/100.0)))
                if int(result.registers[1])==32767:
                    self.set_variable('return_temperature',None)
                else:
                    self.set_variable('return_temperature',float('%.1f' % self.cel2far(float(int(result.registers[1]))/100.0)))
                if int(result.registers[2])==32767:
                    self.set_variable('outside_temperature',None)
                else:
                    self.set_variable('outside_temperature',float('%.1f' % self.cel2far(float(int(result.registers[2]))/100.0)))
                self.set_variable('pressure',float(int(result.registers[22]))/100.0)
                self.set_variable('outside_damper_position',int(result.registers[17]))
                self.set_variable('bypass_damper_position',int(result.registers[25]))
                cool1=int(result.registers[4])
                cool2=int(result.registers[12])
                cool3=int(result.registers[13])
                cool4=int(result.registers[14])
                if (int(result.registers[15])==1):
                    self.set_variable('fan_status','ON')
                else:
                    self.set_variable('fan_status','OFF')
                result = client.read_holding_registers(129,1,unit=self.get_variable('subordinate_id'))
                if int(result.registers[0]) > 100:
                    self.set_variable('heating',0)
                else:
                    self.set_variable('heating',int(result.registers[0]))
                result = client.read_holding_registers(10,1,unit=self.get_variable('subordinate_id'))
                if int(result.registers[0]) == 0:
                    self.set_variable('cooling_mode','None')
                    self.set_variable('cooling_status','OFF')
                elif int(result.registers[0]) == 1:
                    self.set_variable('cooling_mode','STG1')
                    if cool1 == 0:
                        self.set_variable('cooling_status','OFF')
                    else:
                        self.set_variable('cooling_status','ON')
                elif int(result.registers[0]) == 2:
                    self.set_variable('cooling_mode','STG2')
                    if cool2 == 0:
                        self.set_variable('cooling_status','OFF')
                    else:
                        self.set_variable('cooling_status','ON')
                elif int(result.registers[0]) == 3:
                    self.set_variable('cooling_mode','STG3')
                    if cool3 == 0:
                        self.set_variable('cooling_status','OFF')
                    else:
                        self.set_variable('cooling_status','ON')
                elif int(result.registers[0]) == 4:
                    self.set_variable('cooling_mode','STG4')
                    if cool4 == 0:
                        self.set_variable('cooling_status','OFF')
                    else:
                        self.set_variable('cooling_status','ON')
            client.close()
        except Exception as er:
            print "classAPI_vav_rtu: ERROR: Reading Modbus registers at getDeviceStatus:"
            print er
            getDeviceStatusResult = False

        if getDeviceStatusResult==True:
            self.set_variable('offline_count',0)
        else:
            self.set_variable('offline_count',self.get_variable('offline_count')+1)

    #method2: POST Open the port and Change status
    def setDeviceStatus(self, postmsg):
        setDeviceStatusResult = True

        try:
            client = ModbusTcpClient(self.get_variable('address'),port=502)
            client.connect()
            if (self.get_variable('model')=='VC1000'):
                if 'heat_setpoint' in postmsg.keys():
                    client.write_register(6,int(self.far2cel(float(postmsg.get('heat_setpoint')))*100.0),unit=self.get_variable('subordinate_id'))
                if 'cool_setpoint' in postmsg.keys():
                    client.write_register(6,int(self.far2cel(float(postmsg.get('cool_setpoint')))*100.0),unit=self.get_variable('subordinate_id'))
                if 'flap_override' in postmsg.keys():
                    if postmsg.get('flap_override') == 'ON' or postmsg.get('flap_override') == True:
                        client.write_register(159,1,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('flap_override') == 'OFF' or postmsg.get('flap_override') == False:
                        client.write_register(159,0,unit=self.get_variable('subordinate_id'))
                if 'flap_position' in postmsg.keys():
                    client.write_register(160,int(postmsg.get('flap_position')),unit=self.get_variable('subordinate_id'))
            elif (self.get_variable('model')=='M1000'):
                if 'heat_setpoint' in postmsg.keys():
                    client.write_register(187,int(self.far2cel(float(postmsg.get('heat_setpoint')))*100.0),unit=self.get_variable('subordinate_id'))
                if 'cool_setpoint' in postmsg.keys():
                    client.write_register(188,int(self.far2cel(float(postmsg.get('cool_setpoint')))*100.0),unit=self.get_variable('subordinate_id'))
                if 'outside_damper_position' in postmsg.keys():
                    client.write_register(274,int(postmsg.get('outside_damper_position')),unit=self.get_variable('subordinate_id'))
                if 'bypass_damper_position' in postmsg.keys():
                    client.write_register(275,int(postmsg.get('bypass_damper_position')),unit=self.get_variable('subordinate_id'))
                if 'fan_status' in postmsg.keys():
                    if postmsg.get('fan_status') == 'ON' or postmsg.get('fan_status') == True:
                        client.write_register(130,2,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('fan_status') == 'OFF' or postmsg.get('fan_status') == False:
                        client.write_register(130,1,unit=self.get_variable('subordinate_id'))
                if 'cooling_status' in postmsg.keys():
                    if postmsg.get('cooling_status') == 'ON':
                        client.write_registers(124,[1,2,2,2],unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('cooling_status') == 'OFF':
                        client.write_registers(124,[0,1,1,1],unit=self.get_variable('subordinate_id'))
                if 'cooling_mode' in postmsg.keys():
                    if postmsg.get('cooling_mode') == 'None':
                        client.write_register(10,0,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('cooling_mode') == 'STG1':
                        client.write_register(10,1,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('cooling_mode') == 'STG2':
                        client.write_register(10,2,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('cooling_mode') == 'STG3':
                        client.write_register(10,3,unit=self.get_variable('subordinate_id'))
                    elif postmsg.get('cooling_mode') == 'STG4':
                        client.write_register(10,4,unit=self.get_variable('subordinate_id'))
                if 'heating' in postmsg.keys():
                    client.write_register(129,int(postmsg.get('heating')),unit=self.get_variable('subordinate_id'))
            client.close()

        except:
            try:
                client.close()
            except:
                print('Modbus TCP client was not built successfully at the beginning')
            setDeviceStatusResult=False

        return setDeviceStatusResult


    def cel2far(self,cel_temp):
        return (((cel_temp * 9.0)/5.0)+32.0)

    def far2cel(self,far_temp):
        return (((far_temp -32.0 )/9.0)*5.0)

#This main method will not be executed when this class is used as a module
def main():
    #Utilization: test methods
    #Step1: create an object with initialized data from DeviceDiscovery Agent
    #requirements for instantiation1. model, 2.type, 3.api, 4. address,
    Prolon = API(model='VC1000',type='VAV',api='API',address='192.168.10.228:7')

    #Step2: Get data from device
    Prolon.getDeviceStatus()
    print Prolon.variables

    #Step3: change device operating set points
    #Prolon.setDeviceStatus({'flap_override':'ON','flap_position':20})
    #Prolon.setDeviceStatus({'fan_status':'ON'})

    Prolon.getDeviceStatus()
    print Prolon.variables


if __name__ == "__main__": main()