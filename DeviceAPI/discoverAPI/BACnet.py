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

import os
import subprocess
from bemoss_lib.protocols.BACnet.BACnetReadWrite import BACnetreadproperty, BACnetreadproprietary


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def discover(type):

    os.system('export BACNET_IFACE=$(cat ${HOME}/workspace/bemoss_os/machine_ip.txt)')
    BACnetreply = subprocess.check_output(os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2/bin/bacwi -1",shell=True)
    BACnetreply = BACnetreply.split('\n')

    responses=list()
    for line in BACnetreply:
        print line
        if line == '' or line is None:
            break
        if line[0]!=';':
            string=line.split()[0] #create a list object
            if is_number(string)==True:
                if float(string) != 260001: #virtual server
                    if float(string) != 0:
                        try:
                            DeviceModel=BACnetreadproperty(string,8,70)
                            modelname=DeviceModel.strip('\"')

                            if modelname == "LMBC-300":
                                connected_devices = BACnetreadproperty(string,8,8602)
                                connected_devices = ((connected_devices.replace("{","")).replace("}","")).split(',')

                                i=0
                                while i<len(connected_devices):
                                    if int(connected_devices[i+2]) >=2 and int(connected_devices[i+2]) <=6:
                                        if (connected_devices[i]!='') and (connected_devices[i] is not None):
                                            devicemodel=''
                                            infile2 = open(os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/WattStopper_model_names.txt", 'r')
                                            for line in infile2:
                                                if " "+connected_devices[i+1] in line:
                                                    devicemodel=(line.replace(" "+connected_devices[i+1],"")).rstrip()
                                                    break
                                            infile2.close()
                                            if devicemodel == 'LMRC-212':
                                                for propertyindex in range(1,10,2):
                                                    deviceuuid=BACnetreadproprietary(string,1,propertyindex)
                                                    if deviceuuid == connected_devices[i]:
                                                        responses.append(string+'i'+connected_devices[i]+'n'+str(propertyindex))
                                                        responses.append(string+'i'+connected_devices[i]+'n'+str(propertyindex+1))
                                                        break
                                            else:
                                                responses.append(string+'i'+connected_devices[i])
                                    i = i+5
                            else:
                                responses.append(string)
                        except:
                            pass

    return responses


def getmodelvendor(type,macaddress):
    try:
        if type == 'WattStopper':
            deviceuuid = macaddress.split('i')[1].split('n')[0]
            macaddress = macaddress.split('i')[0]
            connected_devices=BACnetreadproperty(macaddress,8,8602)
            connected_devices = ((connected_devices.replace("{","")).replace("}","")).split(',')
            i=0
            while i<len(connected_devices):
                if connected_devices[i] == deviceuuid:
                    infile = open(os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/WattStopper_model_names.txt", 'r')
                    for line in infile:
                        if " "+connected_devices[i+1] in line:
                            devicemodel=(line.replace(" "+connected_devices[i+1],"")).rstrip()
                            break
                    infile.close()
                    break
                i = i+5
        else:
            modelname=BACnetreadproperty(macaddress,8,70)
            devicemodel = modelname.strip('\"')
        vendorname = BACnetreadproperty(macaddress,8,121)
        devicevendor = vendorname.strip('\"')

        return {'model':devicemodel,'vendor':devicevendor}
    except:
        print "ERROR: Reading model info property at discoverAPI"
        return None