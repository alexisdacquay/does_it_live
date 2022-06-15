#!/usr/bin/env python

# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
# -----------------------------------------------------
# Version 1.0  10-August-2015
# Written by:  Alexis Dacquay, Arista Networks
#
# Developed and tested on vEOS-lab 4.15.1F
# ### Version history ###
# - v1.0 - initial release
# Description:
# Access a list of switches, pull and print all the LLDP information

from __future__ import print_function
import jsonrpclib
import optparse
import socket
import syslog
import sys
import signal
import subprocess
import os


#-------------------Configuration------------------------
EAPI_USERNAME = 'eapi'
EAPI_PASSWORD = 'eapi'
EAPI_ENABLE_PASSWORD = ''

# http/https
EAPI_METHOD = 'https'

# Optional Emailing recipient
EMAIL_TO = 'ad.arista.01@gmail.com'

# Temporary workfile if sending data by email is requested
WORKFILE = '/tmp/multiple_lldp.tmp'

#--------------------------------------------------------

errors = {}

# Variable initialisation
debug = None
email_active = None
switchList = [ "172.16.0.11", 
               "172.16.0.12",
               "172.16.0.13",
               "172.16.0.14",
               "172.16.0.15",
               "172.16.0.16" ]


def trace( msg ):
    if debug:
        print ( msg )

def emailMsg( msg ):
    if email_active:
        bashCommand = 'echo ' + msg + ' |  email -i -s \"[$HOSTNAME] ' + \
                      msg.split(' ')[0] + \
                      '\" ' + \
                      EMAIL_TO
        p = subprocess.Popen( bashCommand , 
                              shell=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE )
        p.wait()

def emailFile( file ):
    if email_active:
        bashCommand = 'cat ' + file + ' |  email -i -s \"Multiple LLDP' + \
                      ', by [$HOSTNAME]\" ' + \
                      EMAIL_TO
        p = subprocess.Popen( bashCommand , 
                              shell=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE )
        p.wait()


class Error( Exception ):
    pass

class ConnectionError( Error ):
    '''
    Raised when connection to a eAPI server cannot
    be established.
    '''
    pass

class EApiClient( object ):

    def __init__( self, switch ):
        url = '%s://%s:%s@%s/command-api' % \
              ( EAPI_METHOD, EAPI_USERNAME, EAPI_PASSWORD, switch )
        self.client = jsonrpclib.Server( url  )

        try:
            self.runEnableCmds( [] )
        except socket.error:
            raise ConnectionError( url )

    def runEnableCmds( self, cmds, mode='json' ):
        result = self.client.runCmds( 
            1, [ { 'cmd': 'enable', 
                   'input': EAPI_ENABLE_PASSWORD } ] +
            cmds, mode)[ 1: ]
        
        if mode == 'text':
            return [ x.values()[ 0 ] for x in result if x.values() ]
        else:
            return result
        
    def lldpNeighbors( self ):
        output = self.runEnableCmds( [ 'show lldp neighbors' ] )
        return output


def checklldp():

   trace( "List of switches:" )
   trace( switchList )

   allNeighbors = {}
   if email_active:   # write LLDP into a file for sending by email
      f = open( WORKFILE, 'w+' )
      f.write( 'List of switches:' + ' '.join( switchList ) + '\n\n' )
      for sw in switchList:
         f.write( '[' + sw + '] \n' )
         eapi = EApiClient( sw )
         rawNeighbors = eapi.lldpNeighbors()
         neighbors = rawNeighbors[0][ 'lldpNeighbors' ]
         f.write( '{0:20} {1:20} {2:20} \n'.format( 'Port', 'Neighbor Device', 'Neighbor Port' ) )
         for n in neighbors:
            f.write( '{0:20} {1:20} {2:20} \n'.format( n[ 'port' ], n[ 'neighborDevice' ], n[ 'neighborPort' ] ) )
         f.write( '\n' )
      f.close()
      emailFile( WORKFILE )
      os.remove( WORKFILE )

   else:              # Print to screen/CLI
      for sw in switchList:
         print ( '[', sw, ']' )
         eapi = EApiClient( sw )
         rawNeighbors = eapi.lldpNeighbors()
         neighbors = rawNeighbors[0][ 'lldpNeighbors' ]
         print( '{0:20} {1:20} {2:20}'.format( 'Port', 'Neighbor Device', 'Neighbor Port' ) )
         for n in neighbors:
            print( '{0:20} {1:20} {2:20}'.format( n[ 'port' ], n[ 'neighborDevice' ], n[ 'neighborPort' ] ) )
         print ( )



def main():
    global debug
    global email_active
    global switchList

    signal.signal(signal.SIGINT, lambda x,y: sys.exit(0))
    #setProcName( 'multilldp' )

    # Create help string and parse cmd line
    usage = 'usage: %prog [options]'
    op = optparse.OptionParser(usage=usage)
    op.add_option( '-d', '--debug', dest='debug', action='store_true',
                   help='print debug info' )
    op.add_option( '-e', '--email', dest='email', action='store_true',
                   help='sends email alerts' )
    opts, _ = op.parse_args()
    
    debug = opts.debug
    email_active = opts.email
    
    syslog.openlog( 'multilldp', 0, syslog.LOG_LOCAL4 )

    checklldp()

if __name__ == '__main__':
   main()

