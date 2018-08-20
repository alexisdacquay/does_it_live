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

def trace2( *msg ):
    if args.debug:
        if len(msg) > 1:
            # If 2 strings were passed for trace print out
            print ( '{:16} {}'.format( msg[ 0 ], msg[ 1 ] ) )
        else:
            # If only 1 message was passed to print
            print ( msg[0] )

def trace( msg ):
    if args.debug:
        print (msg)


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

    def isAlive( self ):
        '''
        ping_str = 'ping -c 1 -t {timeout} {src} {host}'
        ping_str.format( timeout = args.timeout,
                        src = '-S' + args.source if args.source else '',
                        host = self.host )
        '''
        src_exists = True if args.source else False
        command = [ 'ping' ] + \
                  [ '-c 1' ] + \
                  [ '-t ' + str( args.timeout ) ] + \
                  [ '-S ' + str( args.source ) ] * src_exists + \
                  [ self.host ]
        trace( '{:16} {}'.format( 'The command is:', str( command ) ) )
        result = subprocess.run( command, capture_output = True )
        if result.returncode == 0:
            output = result.stdout.decode( 'ascii' )
            trace( '{:16} {}'.format( 'The output is:', output ) )
            pattern = r'time=(.*?) ms\n'
            latency = re.findall( pattern, output )[ 0 ]
            trace( '{:16} {}'.format( 'The Latency is:', latency ) )
        else:
            # if result.returncode != 0 it means an error occured
            error = result.stderr.decode( 'ascii' )
            trace( '{:16} {}'.format( 'Error:', error ) )
        return ( result )

def main():
    global args
    # Signal handling used to quit by Ctrl+C without tracekack
    signal.signal( signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit( 0 ) )
    args = parseArgs()
    trace( 'args are: {}'.format( args ) )
    trace2 ( '111111', '222222')
    trace2 ( '333333')
    check = checkICMP( args.host[ 0 ] )
    check.isAlive()

if __name__ == '__main__':
    main()