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
import re

def BACnetreadproperty(address,objecttype,propertyno):
    if objecttype==8:
        bacnetcmd=os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2/bin/bacrp "+str(address)+" "+str(objecttype)+" "+str(address)+" "+str(propertyno)
    else:
        bacnetcmd=os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2/bin/bacrp "+str(address)+" "+str(objecttype)+" "+str(propertyno)+" 85"

    bacnetreaddata = list()
    bacnetreadindex=0
    while bacnetreadindex < 3:
        bacerrorflag=0
        while bacerrorflag!=2:
            os.system('export BACNET_IFACE=$(cat ${HOME}/workspace/bemoss_os/machine_ip.txt)')
            BACnetreply = subprocess.check_output(bacnetcmd,shell=True)
            BACnetreply = BACnetreply.split('\n')
            for line in BACnetreply:
                if line != '' or line is not None:
                    if line[0] != ' ':
                        break
                    else:
                        pass
                else:
                    pass
            try:
                match = re.search('Error',line)
                if match:
                    bacerrorflag+=1
                else:
                    propertyvalue=line.rstrip()
                    break
            except:
                bacerrorflag+=1
        if bacerrorflag==2:
            propertyvalue = None
        bacnetreaddata.append(propertyvalue)
        bacnetreadindex += 1

    if (bacnetreaddata[0] == bacnetreaddata[1]) and (bacnetreaddata[1] == bacnetreaddata[2]):
        returnvalue = bacnetreaddata[0]
    else:
        returnvalue = None

    return returnvalue


def BACnetwriteproperty(address,objecttype,propertyno,value):
    bacnetcmd=os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2/bin/bacwp "+str(address)+" "+str(objecttype)+" "+str(propertyno)+" 85 1 -1"
    if objecttype==1 or objecttype==2:
        bacnetcmd+=" 4 "
    elif objecttype==4 or objecttype==5:
        bacnetcmd+=" 9 "

    bacnetcmd+=str(value)

    bacerrorflag=0
    while bacerrorflag!=2:
        os.system('export BACNET_IFACE=$(cat ${HOME}/workspace/bemoss_os/machine_ip.txt)')
        BACnetreply = subprocess.check_output(bacnetcmd,shell=True)
        BACnetreply = BACnetreply.split('\n')
        for line in BACnetreply:
            if line != '' or line is not None:
                if line[0] != ' ':
                    break
                else:
                    pass
            else:
                pass
        try:
            match = re.search('Error',line)
            if match:
                bacerrorflag+=1
            else:
                issuccess=True
                break
        except:
            bacerrorflag+=1
    if bacerrorflag==2:
        issuccess = False

    return issuccess

def BACnetreadproprietary(address,objecttype,propertyno):
    bacnetcmd=os.path.expanduser("~")+"/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2/bin/bacrp "+str(address)+" "+str(objecttype)+" "+str(propertyno)+" 8600"

    bacerrorflag=0
    while bacerrorflag!=2:
        os.system('export BACNET_IFACE=$(cat ${HOME}/workspace/bemoss_os/machine_ip.txt)')
        BACnetreply = subprocess.check_output(bacnetcmd,shell=True)
        BACnetreply = BACnetreply.split('\n')
        for line in BACnetreply:
            if line != '' or line is not None:
                if line[0] != ' ':
                    break
                else:
                    pass
            else:
                pass
        try:
            match = re.search('Error',line)
            if match:
                bacerrorflag+=1
            else:
                propertyvalue=line.rstrip()
                break
        except:
            bacerrorflag+=1
    if bacerrorflag==2:
        propertyvalue = None

    return propertyvalue