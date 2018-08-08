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
#from ctypes import cdll, byref, create_string_buffer
import sys
import signal

#import syslog
#import sys
#import datetime
#import socket


'''
def setProcName(newname):
    # This function allow tracking this script by name from bash/kernel
    libc = cdll.LoadLibrary( 'libc.so.6' )
    buff = create_string_buffer( len( newname ) + 1 )
    buff.value = newname    
    libc.prctl( 15, byref( buff ), 0, 0, 0)
'''

def parseArgs():
    parser = argparse.ArgumentParser(description='Checks whether a destination \
                                                    is alive')

    parser.add_argument('-x', '--debug', action='store_true',
                        help='activates debug output')
    
    parser.add_argument('-i', '--interval', type=int, 
                        default=5, help='Interval of polls. Default is 5')
    
    parser.add_argument('-m', '--mode', default='icmp',
                        help='detection mode: ICMP, DNS, etc. Default is ICMP')
    
    parser.add_argument('-s', '--source',
                        help='source IP address to reach')
    
    parser.add_argument('-d', '--dns',
                        help='IP address of the DNS name-server, to be used in\
                        conjunction with the DNS mode and a FQDN')
    
    parser.add_argument('host', nargs='+', 
                        help='FQDN or IP address of the destination(s) to check')

    args = parser.parse_args()
    return args


def main():
    # Signal handling used to quit by Ctrl+C without tracekack
    signal.signal(signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit(0))
    #setProcName( 'does_it_live' )
    parseArgs()

if __name__ == '__main__':
    main()