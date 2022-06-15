#!/usr/bin/env python
# Copyrighted Arista Networks, 2015
# By Alexis Dacquay, 2015-10-27
# Version: Draft 1

from __future__ import print_function
import os
import sys,signal
import subprocess
import socket
from jsonrpclib import Server


#-------------------Configuration------------------------
EAPI_USERNAME = 'eapi'
EAPI_PASSWORD = 'eapi'
EAPI_ENABLE_PASSWORD = ''

# http/https
EAPI_METHOD = 'https'

# Optional Emailing recipient
EMAIL_TO = 'test@xyz.com'

# Temporary workfile if sending data by email is requested
WORKFILE = '/tmp/multiple_lldp.tmp'

SWITCH_IP = '127.0.0.1'

CONFIG_STRING = 'switchport trunk allowed vlan 111'
#CONFIG_STRING = 'switchport tool group GROUP1'
DEBUG = 1
PORT1 = '1'
PORT2 = '2'

ip_primary = '172.16.0.12'
ip_secondary = '172.16.0.13'

#--------------------------------------------------------

test_success = 1
previous_test_success = 1

signal.signal(signal.SIGINT, lambda x,y: sys.exit(0))

with open(os.devnull, "wb") as limbo:
   while (1):
      # ICMP pre-check - DEBUG
      if ( DEBUG ):
         p1 = subprocess.Popen(['ping', '-n', '-c3', '-W1', ip_primary], stdout=limbo, stderr=limbo)
         p2 = subprocess.Popen(['ping', '-n', '-c3', '-W1', ip_secondary], stdout=limbo, stderr=limbo)
         #for potential extra debugging outputs
         response1 = p1.wait()
         output1 = p1.communicate()
         response2 = p2.wait()
         output2 = p2.communicate()
         if ( response1 == 0 ):       # primary up
            print ( ip_primary, 'is up' )
            #test_success = 1
         elif ( response2 == 0 ):
             print ( ip_primary, 'is down! Will be using Backup' )
             #test_success = 0
         else:
            print ( 'Oh No! ', ip_secondary, 'is down too! What to do ??' )
            #test_success = 2
      
      # Normal test : SSH socket reachability      
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.settimeout(3)
      try:
         s.connect(( ip_primary, 22 ))
         print ( '%s - Port 22 reachable' % ip_primary)
         test_success = 1
      except socket.error as e:
         print ( "Error on connect: %s" % e )
         test_success = 0
      s.settimeout(None)
      fileobj = s.makefile('rb', 0)
      s.close()

      change = 0
      if (previous_test_success != test_success):
         change = 1
      if ( DEBUG ):
         print ( 'previous_test_success: %d' % previous_test_success)  # Debug
         print ( 'test_success: %d' % test_success)  # Debug
         print ( 'change: %d' % change)  # Debug

      if ( change ):
         switch = Server( '%s://%s:%s@%s/command-api' %
                     ( EAPI_METHOD, EAPI_USERNAME, EAPI_PASSWORD, SWITCH_IP ) )
         print ( 'Connection established')  # Debug
         Config1 = ''
         Config2 = ''
         if ( test_success == 0 ):               # primary failed, remove config
            Config1 = 'no '+CONFIG_STRING
            Config2 = CONFIG_STRING
         if ( test_success == 1 ):
            Config1 = CONFIG_STRING
            Config2 = 'no '+CONFIG_STRING
         if ( DEBUG ):
            print ( 'Config1 to be applied: %s' % Config1 )
            print ( 'Config2 to be applied: %s' % Config2 )
         result = switch.runCmds( 1, [ 'enable',
                           'configure',
                           'interface Ethernet %s' % PORT1,
                           '%s' % Config1,
                           'interface Ethernet %s' % PORT2,
                           '%s' % Config2 ] )
         print ( 'Arista Tap Aggregator has been re-configured' )	
      previous_test_success = test_success
      