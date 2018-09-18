#!/usr/bin/env python 
#
#    Version 1.0 2018-08-08
#    Written by: 
#       Alexis Dacquay

import argparse
import time
import os
import signal
import subprocess
import socket
import sys
import signal
import re

#import syslog
#import sys
#import datetime
#from ctypes import cdll, byref, create_string_buffer

def trace( *msg ):
    if args.debug:
        if len(msg) > 1:
            # If 2 strings were passed for trace print out
            print ( '{:20} {}'.format( msg[ 0 ], msg[ 1 ] ) )
        else:
            # If only 1 message was passed to print
            print ( msg[0] )


def parseArgs():
    parser = argparse.ArgumentParser( description='Checks whether a destination \
                                                    is alive' )

    parser.add_argument( '-x', '--debug', action='store_true',
                        help='activates debug output' )
    
    parser.add_argument( '-i', '--interval', type=int, default=5, 
                        help='Interval of polls. Default is 5' )

    parser.add_argument( '-t', '--timeout', type=int, default=5, 
                        help='Amount of  seconds to wait for a response' )
    
    parser.add_argument( '-m', '--mode', default='icmp',
                        help='detection mode: ICMP, DNS or SSH. \
                                Default is ICMP' )
    
    parser.add_argument( '-s', '--source',
                        help='source IP address to reach' )
    
    parser.add_argument( '-d', '--dns',
                        help='IP address of the DNS name-server, to be used in\
                                conjunction with the DNS mode and a FQDN' )
    
    parser.add_argument( 'host', nargs='+', 
                        help='FQDN or IP address of the destination(s) to \
                                check' )

    args = parser.parse_args()
    return args

def checkSocket( ip, port, timeout ):
    s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
    s.settimeout( timeout )
    try:
        s.connect( ( ip, port ) )
        trace( "{} - Port {} is reachable".format( ip, port ) )
        test_success = True
    except socket.error as e:
        trace( "Error on connect: {}".format( e ))
        test_success = False
    s.settimeout( None )
    #fileobj = s.makefile( 'rb', 0 )
    s.close()
    return( test_success )

class checkICMP:
    def __init__( self, host ):
        self.host = host

    def getLatency( self, output ):
        # Must get an output first, check with isAlive()
        outputLines = output.split('\n')
        lastNonEmpty = [ i for i in outputLines if i ][ -1 ]
        trace( 'Ping result:', lastNonEmpty)
        timingData = lastNonEmpty.split( '=' )[1]
        timingStats = timingData.split( '/' )

        #pingMin = float( timingStats[ 0 ] )
        pingAvg = float( timingStats[ 1 ] )
        #pingMax = float( timingStats[ 2 ] )
        
        return pingAvg

    def isAlive( self ):
        result = ''
        pythonVersion = sys.version_info[ 0 ]
        trace( 'Python version:', pythonVersion )

        src_exists = True if args.source else False
        command = [ 'ping' ] + \
                  [ '-c 1' ] + \
                  [ '-t ' + str( args.timeout ) ] + \
                  [ '-S ' + str( args.source ) ] * src_exists + \
                  [ self.host ]
        trace( 'The command is:', str( command ) )

        # Python 2 compatibility
        if sys.version_info[ 0 ] < 3:
            proc = subprocess.Popen( [ 'ping', '-n', '-c3', '-W1', self.host ], \
            stdout = subprocess.PIPE, stderr = subprocess.PIPE )
            returncode = proc.wait()
            if returncode == 0:
                rawOutput = proc.communicate()
                output = rawOutput[0].decode( 'ascii' )
                trace( 'The latency is:', self.getLatency( output ) )
                result = True
            else:
                error = 'The ICMP check did not succeed'
                trace( 'Error:', error )
                result = False

        # Python 3
        if sys.version_info[ 0 ] >= 3:
            proc = subprocess.run( command, capture_output = True )
 
            if proc.returncode == 0:
                output = proc.stdout.decode( 'ascii' )
                trace( 'The latency is:', self.getLatency( output ) )
                result = True
            else:
                # if proc.returncode != 0 it means an error occured
                error = proc.stderr.decode( 'ascii' )
                trace( 'Error:', error )
                result = False
        return result

def main():
    global args
    # Signal handling used to quit by Ctrl+C without tracekack
    signal.signal( signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit( 0 ) )
    args = parseArgs()
    trace( 'Args are:', args )
    check = checkICMP( args.host[ 0 ] )
    while True:
        if check.isAlive():
            print( "Target is alive" )
        time.sleep( XXX )

if __name__ == '__main__':
    main()