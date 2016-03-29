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

import sys
import json
import logging
import os
import re
from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod
import settings
import requests
import time
import subprocess


utils.setup_logging()  # setup logger for debugging
_log = logging.getLogger(__name__)

# Step1: Agent Initialization
def ApprovalHelperAgent(config_path, **kwargs):
    config = utils.load_config(config_path)  # load the config_path from approvalhelperagent.launch.json
    def get_config(name):
        try:
            kwargs.pop(name)  # from the **kwargs when call this function
        except KeyError:
            return config.get(name, '')

    # 1. @params agent
    agent_id = get_config('agent_id')
    headers = {headers_mod.FROM: agent_id}

    # @paths
    PROJECT_DIR = settings.PROJECT_DIR
    Agents_Launch_DIR = settings.Agents_Launch_DIR

    class Agent(PublishMixin, BaseAgent):

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            sys.path.append(PROJECT_DIR)


        def setup(self):
            super(Agent, self).setup()


        @matching.match_regex('/ui/discoveryagent/([0-9a-zA-Z]+)/approval_status/change')
        def agentLaunchBehavior(self, topic, headers, message, match):
            print "ApprovalHelperAgent got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            messagejson = json.loads(message[0])
            if messagejson['prev_zone'] != messagejson['new_zone']:
                print 'device zone change will be handled by network agent'
                return
            deviceID = ""
            for k in messagejson.keys():
                if k == 'prev_zone' or k == 'new_zone':
                    continue

                deviceID = str(k)

            if str(messagejson['new_zone']) == '999':
                if messagejson[deviceID] == 'APR':
                    if not self.device_agent_still_running(deviceID):
                        self.launch_agent(Agents_Launch_DIR, deviceID)
                        print "Agent has been launched for the approved device :" + deviceID
                else:
                    os.system("volttron-ctl stop --tag "+ deviceID)
                    print deviceID + " has been stopped"
            else:
                if messagejson[deviceID] == 'APR':
                    topic = '/ui/networkagent/'+deviceID+'/'+str(messagejson['new_zone'])+'/'+str(messagejson['new_zone'])+'/change'
                    headers = {
                        'AgentID': 'approvalagent',
                        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,

                        }
                    message = json.dumps("Start the agent in that zone")
                    self.publish(topic,headers,message)
                else:
                    topic = '/ui/networkagent/'+deviceID+'/'+str(messagejson['new_zone'])+'/'+str(messagejson['new_zone'])+'/stop'
                    headers = {
                        'AgentID': 'approvalagent',
                        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,

                        }
                    message = json.dumps("Stop the agent in that zone")
                    self.publish(topic,headers,message)

        def launch_agent(self, dir, launch_file):

            def is_agent_installed(agent_id):
                statusreply = subprocess.check_output('~/workspace/bemoss_os/env/bin/volttron-ctl status',shell=True)
                statusreply = statusreply.split('\n')
                agent_installed = False
                reg_search_term = " "+agent_id+" "
                for line in statusreply:
                    match = re.search(reg_search_term, line)
                    if match:  # The agent for this device is running
                        agent_installed = True
                    else:
                        pass
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

            print "Approval Helper Agent has successfully launched {} located in {}".format(agent_id, dir)

        def device_agent_still_running(self,agent_launch_filename):
            os.system(#". env/bin/activate"
                      "volttron-ctl status > running_agents.txt")
            infile = open('running_agents.txt', 'r')
            agent_still_running = False
            reg_search_term = agent_launch_filename
            for line in infile:
                match = re.search(reg_search_term, line) and re.search('running', line)
                if match:  # The agent for this device is running
                    agent_still_running = True
                else:
                    pass
            infile.close()
            return agent_still_running

        @matching.match_exact('/ui/agent/misc/bemoss/approvalhelper_get_hue_username')
        def get_hue_username(self, topic, headers, message, match):
            print "ApprovalHelperAgent got\nTopic: {topic}".format(topic=topic)
            print "Headers: {headers}".format(headers=headers)
            print "Message: {message}\n".format(message=message)
            messagejson = json.loads(message[0])
            hue_id = messagejson['DeviceId']
            _launch_file = os.path.join(Agents_Launch_DIR, hue_id+".launch.json")
            f = open(_launch_file, 'r')
            data = json.load(f)
            ip_addr = data['address'].replace(":80", "")
            try:
                hue_hub_name = self.query_hue_hub(ip_addr)
                f.close()
                reply = dict()
                if hue_hub_name:
                    data['username'] = hue_hub_name.encode('utf-8')
                    with open(_launch_file, 'w') as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)
                    outfile.close()
                    reply['flag'] = 1
                else:
                    reply['flag'] = 0

                message_reply = json.dumps(reply)
                message_reply = message_reply.encode(encoding='utf_8')
                headers_reply = {'AgentID': 'ApprovalHelperAgent'}
                topic_reply = '/agent/ui/misc/bemoss/approvalhelper_get_hue_username_response'
                self.publish(topic_reply, headers_reply, message_reply)
            except:
                print('Username not acquired.')

        def query_hue_hub(self, ip_addr):
            # newdeveloper is for the old version of Hue hub, might no longer be useful in future version.
            url = ip_addr+'/api/newdeveloper'
            req = requests.get(url)
            result = json.loads(req.content)
            message = json.dumps(result)
            message = message.encode(encoding='utf_8')

            substring = "unauthorized user"
            no_name = substring in message

            if no_name:
                cnt = 60
                while cnt > 0:
                    body = {"devicetype":"my_hue_app#bemoss"}
                    url = ip_addr+'/api'

                    r = requests.post(url, json.dumps(body))
                    print r.content
                    substring = "link button not pressed"
                    if substring in r.content:
                        time.sleep(0.5)
                        cnt -= 1
                        print cnt
                    else:
                        exp = '\"username\":\"(.*?)\"'
                        pattern = re.compile(exp, re.S)
                        result = re.findall(pattern, r.content)
                        hub_name = result[0]
                        break
            else:
                hub_name = 'newdeveloper'

            return hub_name

    Agent.__name__ = 'ApprovalHelperAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(ApprovalHelperAgent, description='Approval Helper agent', argv=argv)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
