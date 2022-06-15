#!/usr/bin/env python 
#
#    Version 1.0 2018-09-27
#    Written by: 
#       Alexis Dacquay, ad@arista.com
#
# Installation:
#       pip install dnspython 
#       or http://www.dnspython.org/ + sudo python setup.py install
'''
Examples:
./does_it_livepy -v -t 1 -i 1 8.8.8.8
./does_it_live_v0.14.py -t 1 -i 1 -m dns -d 1.1.1.1 -s 10.0.2.15 www.bbc.co.uk
    
'''

import argparse
import time
import os
import signal
import subprocess
import socket
import sys
import syslog
import signal
import re
import platform
import dns.resolver


def trace2( *msg ):
    # presents messages similarly to 'trace()' but the existence of trace2
    # allows granularity in the debug level. This is aimed at debugging
    if args.veryverbose:
        trace( *msg )

def trace( *msg ):
    # presents outputs in a formatted manner. Supports 1 or 2 strings
    # This is aimed at being informational
    if args.verbose:
        if len( msg ) > 1:
            # If 2 strings were passed for trace print out
            print ( '{:20} {}'.format( msg[ 0 ], msg[ 1 ] ) )
        else:
            # If only 1 message was passed to print
            print ( msg[0] )


def parseArgs():
    parser = argparse.ArgumentParser( description='Checks whether a destination \
                                                    is alive' )

    parser.add_argument( '-v', '--verbose', action='store_true',
                        help='activates verbose output' )
    
    parser.add_argument( '-V', '--veryverbose', action='store_true',
                        help='activates very verbose output' )

    parser.add_argument( '-i', '--interval', type=int, default=5, 
                        help='Interval of polls. Default is 5' )

    parser.add_argument( '-t', '--timeout', type=int, default=5, 
                        help='Amount of seconds to wait for a response' )
    
    parser.add_argument( '-m', '--mode', default='icmp',
                        help='detection mode: ICMP, DNS or SSH. \
                                Default is ICMP' )
    
    parser.add_argument( '-s', '--source',
                        help='source IP address to reach' )
    
    parser.add_argument( '-d', '--dns',
                        help='IP address of the DNS name-server, to be used in\
                                conjunction with the DNS mode and a FQDN' )
    
    parser.add_argument( '-c', '--consecutive', type=int, default=3, 
                        help='Amount consecutive times a target must be failing\
                                before being considered dead' )
    
    parser.add_argument( 'host', nargs='+', 
                        help='FQDN or IP address of the destination(s) to \
                                check' )
    
    args = parser.parse_args()
    if args.veryverbose:
        args.verbose = True
    
    return args


def argsDisplay():
    # For debug purpose or curiosity
    trace( '' )
    trace( '########## Your settings: ##########' )
    trace2( 'Args are:', args )
    trace( 'Verbose:', args.verbose)
    trace( 'VeryVerbose:', args.veryverbose)
    trace( 'Interval:', args.interval)
    trace( 'Timeout:', args.timeout)
    trace( 'Mode:', args.mode)
    trace( 'Source IP:', args.source)
    trace( 'DNS server:', args.dns)
    trace( 'Consecutive times:', args.consecutive)
    trace( 'Target Host:', args.host)
    trace( '####################################' )
    trace( '' )

def checkOS():
    # Different OS have diferring PING options. This fuction standardises
    os = platform.system()
    global timeUnit
    global sourceSetting
    if os == 'Linux':
        # On EOS Linux kernel timeout is in second and IP source as '-I'
        timeUnit = 1
        sourceSetting = '-I'
    elif os == 'Darwin':
        # On MACOS timeout is in msec (want it in sec) and IP source as '-S'
        timeUnit = 1000
        sourceSetting = '-S'
    elif os == 'Windows':
        # on Windows, timout is in msec, IP source as '-S'
        # too many other varation to support at this time
        print ( 'Error - Windows is not supported at this time' )
    else:
        print ( 'Error - Unsupported OS' )

'''
# For potential SSH connectivity testing
def checkSocket( ip, port, timeout ):
    s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
    s.settimeout( timeout )
    try:
        s.connect( ( ip, port ) )
        trace( "{} - Port {} is reachable".format( ip, port ) )
        test_success = True
    except socket.error as e:
        trace( "Error on connect: {}".format( e ) )
        test_success = False
    s.settimeout( None )
    #fileobj = s.makefile( 'rb', 0 )
    s.close()
    return( test_success )
'''

class checkDNS:
    # Verify that a FQDN resolves via a specified DNS server, returns the IP
    def __init__( self, dnsServer, source, target ):
        self.dnsServer = dnsServer
        self.source = source
        self.target = target

    def isAlive( self ):
        results = self.resolve()
        ip = ''
        if results:
            # There might be multiple IP address but the 1st suffice
            ip = results[ 0 ]
            result = True
        else:
            result = False
        return result, ip

    def resolve( self ):
        queryType = 'A'
        results = ''
        resolver = dns.resolver.Resolver( configure = False )
        resolver.nameservers = [ self.dnsServer ]
        resolver.timeout = args.timeout
        resolver.lifetime = args.timeout
        try:
            trace2( 'Info:', 'DNS query attempt' )
            results = resolver.query( self.target, queryType, \
                source = self.source )
        except dns.resolver.NoAnswer:
            trace( 'Error:', 'No response to the DNS query' )
            pass
        except dns.resolver.NXDOMAIN:
            trace( 'Error:', 'DNS query name does no exist' )
            pass
        except dns.exception.Timeout:
            trace( 'Error:', 'The DNS query timed out' )
            pass
        # Debugging - list all the IP addresses resolved
        for result in results:
            trace2( 'Result DNS IP address:', result.address )  
        return results


class checkICMP:
    # Verifies a reachability by ICMP and records the response latency
    def __init__( self, host ):
        self.host = host

    def getLatency( self, output ):
        # Must get an output first, check with isAlive()
        outputLines = output.split('\n')
        lastNonEmpty = [ i for i in outputLines if i ][ -1 ]
        trace2( 'Ping result:', lastNonEmpty)
        timingData = lastNonEmpty.split( '=' )[1]
        timingStats = timingData.split( '/' )
        pingAvg = timingStats[ 1 ]
        return pingAvg + ' ms'

    def isAlive( self ):
        result = ''
        output = ''
        latency = 0
        pythonVersion = sys.version_info[ 0 ]
        trace2( 'Python version:', pythonVersion )

        src_exists = True if args.source else False
        command = [ 'ping' ] + \
                  [ '-n' ] + \
                  [ '-c 1' ] + \
                  [ '-W ' + str( args.timeout * timeUnit ) ] + \
                  [ sourceSetting + str( args.source ) ] * src_exists + \
                  [ self.host ]
        trace2( 'The command is:', str( command ) )

        # Python 2 compatibility
        if sys.version_info[ 0 ] < 3:
            proc = subprocess.Popen( command, \
                    stdout = subprocess.PIPE, stderr = subprocess.PIPE )
            returncode = proc.wait()
            if returncode == 0:
                rawOutput = proc.communicate()
                output = rawOutput[0].decode( 'ascii' )
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
                result = True
            else:
                # if proc.returncode != 0 it means an error occured
                # get a clean line for the error message
                error = proc.stderr.decode( 'ascii' ).split('\n')[0]
                if error == '':
                    error = 'The ICMP check did not succeed'
                trace( 'Error:', error )
                result = False
        if output:
            trace2( 'The output is:', output )
            latency = self.getLatency( output )
        return result, latency


class notice():
    # Sends messages out by Syslog or potentially other future methods
    def __init__( self ):
        pass

    def snmp():
        #To be defined
        pass
    
    def syslog( self, msg ):
        NAME = 'does_it_live'
        syslog.openlog( NAME, 0, syslog.LOG_LOCAL4 )
        syslog.syslog( '%%CHECK-6-LOG: Log msg: %s' % msg )
        #syslog.syslog( syslog.LOG_NOTICE, msg )
        #syslog.syslog( syslog.LOG_NOTICE|syslog.LOG_DAEMON, msg)


def main():
    global args
    consecutive = 0
    # Signal handling used to quit by Ctrl+C without tracekack
    signal.signal( signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit( 0 ) )
    args = parseArgs()
    argsDisplay()
    checkOS()

    while True:
        if args.mode == 'icmp':
            check = checkICMP( args.host[ 0 ] )
        if args.mode == 'dns':
            check = checkDNS( args.dns, args.source, args.host[ 0 ] )

        alive, response = check.isAlive()
        # 'alive' is a boolean
        # 'reponse' can vary: it's a latency if ICMP, or an IP in DNS resolution
        
        if alive:
            trace( 'Target alive. The response is:', response)
            if consecutive >= args.consecutive:
                # Resurected (was dead, is now back to life)
                send.syslog( 'Target {} is back to life - {} check'.format( \
                            args.host[ 0 ], args.mode ) )
            # reinitialise the consecutivity counter
            consecutive = 0
        else:
            consecutive += 1
            if consecutive >= args.consecutive:
                trace( 'Error:', 'Target is dead')
                send = notice()
                send.syslog( 'Target {} is dead - {} check'.format( \
                            args.host[ 0 ], args.mode ) )
        trace2('')
        time.sleep( args.interval )


if __name__ == '__main__':
    main()
