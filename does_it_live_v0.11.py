#!/usr/bin/env python 
#
#    Version 1.0 2018-08-08
#    Written by: 
#       Alexis Dacquay
#
# Installation:
#       pip install dnspython 
#       or http://www.dnspython.org/ + sudo python setup.py install
# 

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


def trace( *msg ):
    if args.debug:
        if len( msg ) > 1:
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

def argsDisplay():
    # For debug purpose
    #trace( 'Args are:', args )
    trace( 'Your settings:' )
    trace( '##############' )
    trace( 'Debug:', args.debug)
    trace( 'Interval:', args.interval)
    trace( 'Timeout:', args.timeout)
    trace( 'Mode:', args.mode)
    trace( 'Source IP:', args.source)
    trace( 'DNS server:', args.dns)
    trace( 'Target Host:', args.host)

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


def checkDNS( nameServer, sourceIP):
    resolver = dns.resolver.Resolver( configure = False )
    #nameServer = '1.1.1.1'
    #sourceIP = 
    resolver.nameservers = [ nameServer ]
    result = resolver.query( target, source = sourceIP )
    r = dns.resolver.query('example.org', 'a')

'''
    socket.getaddrinfo( targetName, port, proto)
    ip = socket.gethostbyname(host)
    print("{} resolves to {}".format(host, ip))
print socket.gethostbyname('localhost') # result from hosts file
print socket.gethostbyname('google.com') # your os sends out a dns query

#http://www.dnspython.org/docs/1.15.0/



# 8.8.8.8 is Google's public DNS server


answer = my_resolver.query('google.com')
---------------------------
import dns.resolver

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8']

answers = dns.resolver.query(<addr>, 'PTR')
for rdata in answers:
    print(rdata)

--------------------
from dns import resolver

res = resolver.Resolver()
res.nameservers = ['8.8.8.8']

answers = res.query('stackexchange.com')

for rdata in answers:
    print (rdata.address)
-------------------
'''

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
        output = ''
        latency = 0
        pythonVersion = sys.version_info[ 0 ]
        trace( 'Python version:', pythonVersion )

        src_exists = True if args.source else False
        command = [ 'ping' ] + \
                  [ '-n' ] + \
                  [ '-c 1' ] + \
                  [ '-W ' + str( args.timeout * timeUnit ) ] + \
                  [ sourceSetting + str( args.source ) ] * src_exists + \
                  [ self.host ]
        trace( 'The command is:', str( command ) )

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
                error = proc.stderr.decode( 'ascii' )
                if error == '':
                    error = 'The ICMP check did not succeed'
                trace( 'Error:', error )
                result = False
        if output:
            trace( 'The output is:', output )
            latency = self.getLatency( output )
        return result, latency

'''
# sending information

def sendTrap()
    #https://gist.github.com/phil-dileo/7c28c5a50bef26f8c2490a10cd360546

def logging()
syslog.openlog('ansible-%s' % os.path.basename(__file__))
syslog.syslog(syslog.LOG_NOTICE, 'Invoked with %s' % " ".join(sys.argv[1:]))

    # LOG_LOCAL4 is visible with CLI "show logging".
    syslog.openlog( 'does_it_live', 0, syslog.LOG_LOCAL4)


    syslog.syslog( syslog.LOG_INFO, msg)
    syslog.syslog(severity, string)
'''
def notice():
    #syslog.syslog(syslog.LOG_NOTICE, msg)
    message = 'test_001'
    syslog.openlog( 'does_it_live', 0, syslog.LOG_LOCAL4 )
    syslog.syslog(syslog.LOG_NOTICE|syslog.LOG_DAEMON, message)


def main():
    global args
    # Signal handling used to quit by Ctrl+C without tracekack
    signal.signal( signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit( 0 ) )
    args = parseArgs()
    argsDisplay()
    checkOS()
    
    check = checkICMP( args.host[ 0 ] )
    while True:
        life = check.isAlive()
        if life[ 0 ]:
            trace( 'Target is alive' )
            trace( 'The latency is:', life[ 1 ])
            notice()
        time.sleep( 5 )

if __name__ == '__main__':
    main()
