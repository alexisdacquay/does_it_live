#!/usr/bin/env python
#
#    Version 1.0 2018-10-15
#    Written by:
#       Alexis Dacquay, ad@arista.com
#
'''
 # Introduction #
 
 This script verifies the reachability to a target by ICMP or DNS
 The script is intended to be installed on a switch (or host).

 # Requirements

 This script was developped on Linux and Arista EOS 4.21.
 Both python2 and python3 were tested on Linux
 DNS python is required


 # Instructions #

 ## 1 - Get the script on the host
 https://github.com/alexisdacquay/does_it_live

 ## 2 - Instal DNSPython
 ### Online
 If the switch/host has got a public access:
 pip install dnspython

 ### Offline
 or download the package at http://www.dnspython.org/ and then 
 "sudo python setup.py install"


 ## 3 - Syntax

 ./does_it_live.py  [-h] [-v] [-V] [-i <time>] [-t <time>] 
                    [-m icmp | dns [-d <dns ip>]] [-s <ip add>]
                    [-D <count>] host

 -v (--verbose) aims at providing basic information to verify the functionality
                of the script. Someone would typically use this option before
                Leaving it to run silently

 -V (--veryVerbose) would be used for troubleshooting the software developement
                or the operation of the script

 -i (--interval) time in seconds between each health check

 -t (--timeout) time in seconds before declaring a single health check as 
                failed

 -m (--mode)    operating mode of the health check. ICMP and DNS are 
                supported. If running in ICMP mode, which is the default, then 
                only the host is required. When using DNS mode, then the DNS 
                server is additionally required.

 -s (--source)  the source IP address of the IP query can be specified

 -D (--dampening) amount of consecutive checks before switching the target from
                one state to another, either alive->dead or dead->alive. 
                The dampening count applies for both direction of change.
                The default dampening count is 3. In example of a default count 
                (-D3), if a target is alive and get a single check failure, the 
                target will not be declared dead yet. It will take
                3 consecutive checks to fail before switch the target to 
                'dead'. If after 1 or 2 failures the target becomes responsive 
                again then the dampening is reset, meaning the 1 or 2 failures 
                are ignored and 3 entirely new failures will be needed to 
                change the target status.


Dampening example - target is considered still alive:
    Success Success Fail Success Fail Fail Success
                                                 ^ 
                                                 Never 'died' yet

Dampening example - target becomes considered as dead:
    Success Fail Fail Fail Success Fail Success Success Fail
                          ^                                 ^
                          Declared dead                      Still dead
                
Dampening example - target recovers from dead to alive (resurects):
    Success Fail Fail Fail Success Fail Success Success Success
                                                              ^ target is back alive 


 ## 4 - Usage examples:

 ### Example 1 - ICMP
 The following tries an ICMP reach to 8.8.8.8 every seconds and shows basic ouput
 ./does_it_live.py -v -t 1 -i 1 8.8.8.8

Logs on the Arista switch:
Oct 12 08:48:29 localhost does_it_live: %DOES_IT_LIVE-5-LOG: Log msg: Target 1.1.1.1 is dead - icmp check
Oct 12 08:48:49 localhost does_it_live: %DOES_IT_LIVE-5-LOG: Log msg: Target 1.1.1.1 is back to life - icmp check

Script output:
[vagrant@localhost scripts]$ ./does_it_live_v0.22.py -v -t1 -i1  1.1.1.1
INFO
INFO     ########### Your settings: ###########
INFO     Verbose:                    True
INFO     VeryVerbose:                False
INFO     Interval:                   1
INFO     Timeout:                    1
INFO     Mode:                       icmp
INFO     Source IP:                  None
INFO     DNS server:                 None
INFO     Dampening amount:           3
INFO     Target Host:                ['1.1.1.1']
INFO     #######################################
INFO
INFO     Target alive. Response:     6.105 ms
INFO     Target alive. Response:     6.797 ms
INFO     The ICMP check did not succeed
INFO     The ICMP check did not succeed
INFO     The ICMP check did not succeed
ERROR    Warning:                    Target is dead    <=== host reclared dead
INFO     The ICMP check did not succeed
INFO     Target alive. Response:     7.157 ms
INFO     Dampening in progress
INFO     Target alive. Response:     144.862 ms
INFO     Dampening in progress
INFO     The ICMP check did not succeed  <=== Dampening prevented recovery
INFO     The ICMP check did not succeed
INFO     The ICMP check did not succeed
INFO     Target alive. Response:     8.201 ms
INFO     Dampening in progress
INFO     Target alive. Response:     5.272 ms
INFO     Dampening in progress
INFO     Target alive. Response:     42.607 ms
INFO     Dampening in progress
INFO     Target alive. Response:     5.250 ms
ERROR    Target resurected!      <=== After dampening 3x the target has recovered


### Example 2 - DNS

 The following tests resolving www.bbc.co.uk agains the DNS server 1.1.1.1

[vagrant@localhost scripts]$ ./does_it_live.py -t1 -i1 -m dns -d 1.1.1.1 -s 10.0.2.15 www.w3.org
ERROR    Warning:                    Target is dead
ERROR    Target resurected!

Logs on the Arista switch:
Oct 12 08:52:40 localhost does_it_live: %DOES_IT_LIVE-5-LOG: Log msg: Target www.w3.org is dead - dns check
Oct 12 08:52:50 localhost does_it_live: %DOES_IT_LIVE-5-LOG: Log msg: Target www.w3.org is back to life - dns check

### Example 3 - Python 3
Try python3 on your host in such fashion:
python3 does_it_live.py -v -t1 -i1 -m dns -d 1.1.1.1  www.w3.org
'''

import argparse
import logging
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import syslog
import time
# dns.resolver requires installing DNSPython (see install instructions)
import dns.resolver

# Global configuration settings
# logStr is a formatting pattern used by str.format() to align outputs
logStr = '{:27} {}'
# syslogFormat can be customised to match syslog preference
syslogFormat = '%DOES_IT_LIVE-5-LOG'

def setLogging(args):
    # The log level sets the amount of information displayed (error<info<debug)
    logLevel = logging.ERROR
    if args.verbose:
        logLevel = logging.INFO
    if args.veryverbose:
        logLevel = logging.DEBUG
    logging.basicConfig(level=logLevel,
                        format='%(levelname)-8s %(message)s')


def parseArgs():
    parser = argparse.ArgumentParser(
        description='Checks whether a destination is alive')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='activates verbose output')

    parser.add_argument('-V', '--veryverbose', action='store_true',
                        help='activates very verbose output')

    parser.add_argument('-i', '--interval', type=int, default=5,
                        help='Interval of polls. Default is 5')

    parser.add_argument('-t', '--timeout', type=int, default=5,
                        help='Amount of seconds to wait for a response')

    parser.add_argument('-m', '--mode', default='icmp',
                        help='detection mode: ICMP, DNS or SSH. \
                                Default is ICMP')

    parser.add_argument('-s', '--source',
                        help='source IP address to reach')

    parser.add_argument('-d', '--dns',
                        help='IP address of the DNS name-server, to be used in\
                                conjunction with the DNS mode and a FQDN')

    parser.add_argument('-D', '--dampening', type=int, default=3,
                        help='Dampening amount of fail/success for target to\
                                be considered switching status')

    parser.add_argument('host', nargs='+',
                        help='FQDN or IP address of the destination(s) to \
                                check')

    args = parser.parse_args()
    if args.veryverbose:
        args.verbose = True

    return args


def argsDisplay(args):
    # For debug purpose or curiosity
    logging.info('')
    logging.info('########### Your settings: ###########')
    logging.debug(logStr.format('Args are:', args))
    logging.info(logStr.format('Verbose:', args.verbose))
    logging.info(logStr.format('VeryVerbose:', args.veryverbose))
    logging.info(logStr.format('Interval:', args.interval))
    logging.info(logStr.format('Timeout:', args.timeout))
    logging.info(logStr.format('Mode:', args.mode))
    logging.info(logStr.format('Source IP:', args.source))
    logging.info(logStr.format('DNS server:', args.dns))
    logging.info(logStr.format('Dampening amount:', args.dampening))
    logging.info(logStr.format('Target Host:', args.host))
    logging.info('#######################################')
    logging.info('')


def checkOS():
    # Different OS have diferring PING options. This fuction standardises
    os = platform.system()
    osSettings = {}
    timeUnit = 1
    sourceSetting = '-I'
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
        logging.error('Error - Windows is not supported at this time')
    else:
        logging.error('Error - Unsupported OS')
    osSettings['timeUnit'] = timeUnit
    osSettings['sourceSetting'] = sourceSetting
    return osSettings
    

'''
# For potential SSH connectivity testing
def checkSocket(ip, port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        logging.error("{} - Port {} is reachable".format(ip, port))
        test_success = True
    except socket.error as e:
        logging.error("Error on connect: {}".format(e))
        test_success = False
    s.settimeout(None)
    #fileobj = s.makefile('rb', 0)
    s.close()
    return(test_success)
'''


class CheckDNS:
    # Verify that a host resolves via a specified DNS server, returns the IP
    def __init__(self, dnsServer, source, target):
        self.dnsServer = dnsServer
        self.source = source
        self.target = target

    def isAlive(self):
        results = self.resolve()
        ip = ''
        if results:
            # There might be multiple IP address but the 1st suffice
            ip = results[0]
            result = True
        else:
            result = False
        return result, ip

    def resolve(self):
        queryType = 'A'
        results = ''
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [self.dnsServer]
        resolver.timeout = args.timeout
        resolver.lifetime = args.timeout
        try:
            logging.debug(logStr.format('Info:', 'DNS query attempt'))
            results = resolver.query(self.target, queryType,
                                     source=self.source)
        except dns.resolver.NoAnswer:
            logging.info('No response to the DNS query')
            pass
        except dns.resolver.NXDOMAIN:
            logging.info('DNS query name does no exist')
            pass
        except dns.exception.Timeout:
            logging.info('The DNS query timed out')
            pass
        for result in results:
            # Debugging - list all the IP addresses resolved
            logging.debug(logStr.format('Result DNS IP address:', result.address))
        return results


class checkICMP:
    # Verifies a reachability by ICMP and records the response latency
    def __init__(self, osSettings, host):
        
        self.timeUnit = osSettings['timeUnit']
        self.sourceSetting = osSettings['sourceSetting']
        self.host = host

    def getLatency(self, output):
        # Must first get an output to parse, used after/with isAlive()
        outputLines = output.split('\n')
        lastNonEmpty = [i for i in outputLines if i][-1]
        logging.debug(logStr.format('Ping result:', lastNonEmpty))
        timingData = lastNonEmpty.split('=')[1]
        timingStats = timingData.split('/')
        pingAvg = timingStats[1]
        return pingAvg + ' ms'

    def isAlive(self):
        result = ''
        output = ''
        latency = 0
        pythonVersion = sys.version_info[0]
        logging.debug(logStr.format('Python version:', pythonVersion))

        src_exists = True if args.source else False
        command = ['ping'] + \
                  ['-n'] + \
                  ['-c 1'] + \
                  ['-W ' + str(args.timeout * self.timeUnit)] + \
                  [self.sourceSetting + str(args.source)] * src_exists + \
                  [self.host]
        logging.debug(logStr.format('The command is:', str(command)))

        # Python 2 compatibility for running on EOS
        if sys.version_info[0] < 3:
            proc = subprocess.Popen(command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            returncode = proc.wait()
            if returncode == 0:
                rawOutput = proc.communicate()
                output = rawOutput[0].decode('ascii')
                result = True
            else:
                error = 'The ICMP check did not succeed'
                logging.info(error)
                result = False

        # Python 3
        if sys.version_info[0] >= 3:
            proc = subprocess.run(command, capture_output=True)
            if proc.returncode == 0:
                output = proc.stdout.decode('ascii')
                result = True
            else:
                # If proc.returncode != 0 it means an error occured.
                # We get a clean line for the error message
                error = proc.stderr.decode('ascii').split('\n')[0]
                if error == '':
                    error = 'The ICMP check did not succeed'
                logging.info(error)
                result = False
        
        if output:
            logging.debug(logStr.format('The output is:', output))
            latency = self.getLatency(output)
        return result, latency


class Notice():
    # Sends messages out by Syslog or potentially other future methods
    def __init__(self):
        pass

    # def snmp():
        # To be defined
    #    pass

    def syslog(self, msg):
        name = 'does_it_live'
        syslog.openlog(name, 0, syslog.LOG_LOCAL4)
        syslog.syslog(syslogFormat + ': Log msg: %s' % msg)


def main():
    global args
    dampeningDead = 0
    dampeningAlive = 0
    wasAlive = True
    
    args = parseArgs()
    setLogging(args)
    argsDisplay(args)
    osSettings = checkOS()

    try:
        while True:
            if args.mode == 'icmp':
                check = checkICMP(osSettings, args.host[0])
            if args.mode == 'dns':
                check = CheckDNS(args.dns, args.source, args.host[0])
            
            # Check alive (True/False) and response (ICMP latency or DNS IP@)
            alive, response = check.isAlive()

            send = Notice()
            if alive:
                logging.info(logStr.format('Target alive. Response:', response))
                # Dead dampening count re-initialising
                dampeningDead = 0
                
                if not wasAlive:
                    # Was dead, is now coming back to life. Dampening kicks in.
                    if (dampeningAlive < args.dampening):
                        dampeningAlive += 1
                        logging.info('Dampening in progress')
                        logging.debug(logStr.format(
                            'Remaining successes before assuming resurection:',
                            dampeningAlive))
                    elif (dampeningAlive == args.dampening):
                        # The dampening is completed, target considered resurected
                        wasAlive = True
                        dampeningAlive = 0
                        logging.error('Target resurected!')
                        send.syslog('Target {} is back to life - {} check'.format(
                                    args.host[0], args.mode))
                
            else:
                # Looks like dead. Dampening in progress
                dampeningDead += 1
                # Alive dampening count re-initialising
                dampeningAlive = 0

                if wasAlive and (dampeningDead >= args.dampening):
                    logging.error(logStr.format('Warning:', 'Target is dead'))
                    send.syslog('Target {} is dead - {} check'.format(
                                args.host[0], args.mode))
                    # Death tracker
                    wasAlive = False
                else:
                    # Either the target is already dead or Dampening is going on
                    # Dampening at failure is silent (intuitive enough?)
                    pass
            logging.debug('')
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(' Interrupted! Exiting...')


if __name__ == '__main__':
    main()
