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

import socket
import httplib
import StringIO
import os
import re
import json
import urllib2
from xml.dom import minidom
from bemoss_lib.utils import find_own_ip
import sys

sys.path.append(os.path.expanduser("~")+"/workspace")
import settings

db_database = settings.DATABASES['default']['NAME']
db_host = settings.DATABASES['default']['HOST']
db_port = settings.DATABASES['default']['PORT']
db_user = settings.DATABASES['default']['USER']
db_password = settings.DATABASES['default']['PASSWORD']
db_table_supported_devices = settings.DATABASES['default']['TABLE_supported_devices']

debug = True
 
class SSDPResponse(object):
    class _FakeSocket(StringIO.StringIO):
        def makefile(self, *args, **kw):
            return self
    def __init__(self, response):
        r = httplib.HTTPResponse(self._FakeSocket(response))
        r.begin()
        self.location = r.getheader("location")
    def __repr__(self):
        return self.location
    
class SSDPResponseLocation(object):
    def __init__(self, response):
        tokens=response.split('\r\n')
        self.location = 'dummy'
        for token in tokens:
            if re.search('LOCATION: ',token):
                self.location=token.replace('LOCATION: ','')
                break
    def __repr__(self): #will be auto-used when someone tries to convert this object to strng. eg str(obj)
        return self.location
    
def parseJSONresponse(data,key):
    theJSON = json.loads(data)
    return theJSON[key]


def discover(type, timeout=2, retries=1):

    group = ("239.255.255.250", 1900)
    if type=='thermostat':
        message="TYPE: WM-DISCOVER\r\nVERSION: 1.0\r\n\r\nservices: com.marvell.wm.system*\r\n\r\n"
    else:
        message = "\r\n".join([
            'M-SEARCH * HTTP/1.1',
            'HOST: {0}:{1}',
            'MAN: "ssdp:discover"',
            'ST: {st}','MX: 3','',''])
        if type=='WeMo':
            service="upnp:rootdevice"
            message=message.format(*group, st=service)
        elif type=='Philips':
            service="urn:schemas-upnp-org:device:Basic:1"
            message=message.format(*group, st=service)

    socket.setdefaulttimeout(timeout)
    responses = list()
    IPs = find_own_ip.getIPs()
    for IP in IPs:
        for _ in range(retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind((IP, 1900))
            try:
                sock.sendto(message, group)
            except:
                print("[Errno 101] Network is unreachable")

            while True:
                try:
                    raw = sock.recv(1024)
                    response = str(SSDPResponseLocation(raw))
                    if debug: print response
                    else: pass
                    if type=="thermostat":
                        if "/sys" in response and response not in responses:
                            responses.append(response)
                    elif type=="WeMo":
                        if (':49153/setup.xml' in response or ':49154/setup.xml' in response or '/setup.xml' in response) and response not in responses:
                            responses.append(response)
                    elif type=="Philips":
                        if ":80/description.xml" in response and response not in responses:
                            print "response {}".format(response)
                            responses.append(response)
                except socket.timeout:
                    break


    return responses


def getMACaddress(type,ipaddress):

    if type == "thermostat":
        try:
            deviceuuidUrl = urllib2.urlopen(ipaddress, timeout=5)
            deviceuuid=parseJSONresponse(deviceuuidUrl.read().decode("utf-8"),"uuid")
            deviceuuidUrl.close()
            return deviceuuid
        except socket.timeout, e:
            print "There was an error getting MAC address due to: %r" % e
    elif type=="Philips":
        print "ipaddress {}".format(ipaddress)
        deviceUrl = urllib2.urlopen(ipaddress)
        dom=minidom.parse(deviceUrl)
        serialid=dom.getElementsByTagName('serialNumber')[0].firstChild.data
        deviceUrl.close()
        return serialid
    elif type=="WeMo":
        deviceUrl = urllib2.urlopen(ipaddress)
        dom=minidom.parse(deviceUrl)
        macid=dom.getElementsByTagName('serialNumber')[0].firstChild.data
        deviceUrl.close()
        return macid
    else:
        print "This device: {} is not supported by the WiFi discovery module".format(type)

def getmodelvendor(type,ipaddress):

    if type=="thermostat":
        modeladdress=ipaddress.replace('/sys','/tstat/model')
        deviceModelUrl = urllib2.urlopen(modeladdress)
        if (deviceModelUrl.getcode()==200):
            deviceModel = parseJSONresponse(deviceModelUrl.read().decode("utf-8"),"model")
        deviceVendor = "RadioThermostat"
        deviceModelUrl.close()
        return {'model':deviceModel,'vendor':deviceVendor}
    elif type=="Philips":
        deviceUrl = urllib2.urlopen(ipaddress)
        dom=minidom.parse(deviceUrl)
        deviceModel=dom.getElementsByTagName('modelName')[0].firstChild.data
        deviceVendor=dom.getElementsByTagName('manufacturer')[0].firstChild.data
        deviceUrl.close()
        return {'model':deviceModel,'vendor':deviceVendor}
    elif type=="WeMo":
        deviceUrl = urllib2.urlopen(ipaddress)
        dom=minidom.parse(deviceUrl)
        deviceModel=dom.getElementsByTagName('modelName')[0].firstChild.data
        deviceVendor=dom.getElementsByTagName('manufacturer')[0].firstChild.data
        nickname = dom.getElementsByTagName('friendlyName')[0].firstChild.data
        if str(deviceModel).lower() == 'socket':
            deviceType = dom.getElementsByTagName('deviceType')[0].firstChild.data
            deviceType = re.search('urn:Belkin:device:([A-Za-z]*):1',deviceType).groups()[0]
            if (deviceType.lower() == 'controllee'):
                deviceModel = deviceModel
            else:
                deviceModel = 'Unknown'
        deviceUrl.close()
        return {'model':deviceModel,'vendor':deviceVendor,'nickname':nickname}


# This main method will not be executed when this class is used as a module
def main():
    print discover('WeMo')
    # print discover('thermostat')
    # print getMACaddress('Philips','http://192.168.1.102:80/description.xml')
    # print type(getMACaddress('Philips','http://192.168.102.:80'))
    # print getmodelvendor('Philips','http://192.168.1.102:80/description.xml')

if __name__ == "__main__": main()
