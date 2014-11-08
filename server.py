#!/usr/bin/env python
'''
Modified on 2014-11-07

Created on 2009-11-15

@original_author: olivier@olihb.com
'''

from twisted.internet import gtk2reactor
gtk2reactor.install(True)

from twisted.internet import reactor, defer
from twisted.internet.protocol import ReconnectingClientFactory
from starpy.manager import AMIProtocol,AMIFactory
from twisted.internet import task
import logging
import logging.handlers
import yaml

from pyslack import SlackClient

#asterisk AMI login
server="ASTRISKSERVERNAME"
port=5038
username="USERNAME"
secret="PASSWORD"
extensions={"SIP/200":"YOU",
            "SIP/201":"Someone else"}

log = logging.getLogger("server")

timeouttask=None
timeoutping=5
timeoutloop=120

slack_api_token = 'ENTERTOKEN'

client = SlackClient(slack_api_token)

def sendToSlack(msg):
    client.chat_post_message('#phone', msg, username='askerisk')

class callMeFactory(AMIFactory):
    cbconnect=None
    def __init__(self):
        AMIFactory.__init__(self, username, secret)
    def connect(self):
        print 'connecting'
        df = self.login(server, port)
        if self.cbconnect!=None:
            df.addCallback(self.cbconnect)
    def clientConnectionLost(self,connector,reason):
        log.info("connection lost - connecting again")
        reactor.callLater(1,self.connect)
    def clientConnectionFailed(self,connector,reason):
        log.info("connection failed - connecting again")
        reactor.callLater(1,self.connect)

def onDial(protocol,event):
    print '#got event:'
    print yaml.safe_dump(event, default_flow_style=False, explicit_end=True)
    if 'destination' in event:
        destination=event['destination']
        for s in extensions.keys():
            if destination.startswith(s):
              cid=event['callerid'] #if using asterisk 1.6, use calleridnum instead
              cidname=event['calleridname']
              extname = event['destination']
              if s in extensions:
                extname=extensions[s]
              sendToSlack("Incoming call for %(extname)s from %(cidname)s\n%(cid)s call-start" % locals())

def checknetlink(protocol):

    def ontimeout():
        log.info("timeout")
        if dc.active():
            dc.cancel()
        timeouttask.stop()
        protocol.transport.loseConnection()

    def canceltimeout(*val):
        if dc.active():
            dc.cancel()

        log.info("cancel timeout")
        log.info(val)

    def success(val):
        pass

    log.info("setting timeout")
    dc = reactor.callLater(timeoutping,ontimeout)
    df = protocol.ping()
    df.addBoth(canceltimeout)
    df.addCallback(success)
    df.addErrback(ontimeout)

def onLogin(protocol):
    print 'login'
    df = protocol.registerEvent("Dial",onDial)
    global timeouttask
    timeouttask = task.LoopingCall(checknetlink,protocol)
    timeouttask.start(timeoutloop);
    return df

def main():
    cm = callMeFactory()
    cm.cbconnect=onLogin
    cm.connect()

def killapp(*args):
    reactor.stop()
    return True

if __name__ == '__main__':
    #manager.log.setLevel( logging.DEBUG )
    #log.setLevel(logging.INFO)
    logging.basicConfig()

    reactor.callWhenRunning(main)
    reactor.run()
