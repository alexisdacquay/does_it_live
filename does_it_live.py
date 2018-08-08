#!/usr/bin/env python 
#
#    Version 1.0 2018-08-08
#    Written by: 
#       Alexis Dacquay

import optparse
import time
import os
import signal
#import syslog
#import sys
#import datetime
#import socket
import subprocess


def setProcName(newname):
    # This function allow tracking this script by name from bash/kernel
    libc = cdll.LoadLibrary( 'libc.so.6' )
    buff = create_string_buffer( len( newname ) + 1 )
    buff.value = newname    
    libc.prctl( 15, byref( buff ), 0, 0, 0)

def MyOptionParser():
    usage = 'usage: %prog [options]'
    op = optparse.OptionParser(usage=usage)

    op.add_option( '-x', '--debug', dest='debug', action='store_true',
                   help='print debug info' )
    
    op.add_option( '-i', '--interval', dest='interval', action='store',
                   help='Interval of polls. Default is 5', type='int',
                   default='5')
    
    op.add_option( '-m', '--mode', dest='mode', action='store_true',
                   help='detection mode: ICMP, DNS, etc. Default is ICMP', type='string', 
                   default='icmp')
    
    op.add_option( '-d', '--destination', dest='dest', action='store',
                   help='IP address of the destination to reach', type='string')
    
    op.add_option( '-n', '--servername', dest='servername', action='store',
                   help='FQDN of the server to check by DNS', type='string')

    op.add_option( '-s', '--source', dest='source', action='store',
                   help='source IP address to reach', type='string')

    op.add_option( '-S', '--dns', dest='dns', action='store',
                   help='IP address of the DNS server, to be used in \
                   conjunction with the DNS mode and a FQDN', type='string')

    opts, _ = op.parse_args()
    
    debug = opts.debug
    interval = opts.interval
    mode  = opts.mode
    dest = opts.dest
    source = opts.source

def main():
    signal.signal(signal.SIGINT, lambda sig_number, current_stack_frame: sys.exit(0))
    setProcName( 'does_it_live' )

if __name__ == '__main__':
    main()