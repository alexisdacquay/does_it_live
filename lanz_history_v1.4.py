#!/usr/bin/env python 
#
# Copyright (c) 2014, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#  - Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#  - Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#  - Neither the name of Arista Networks nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# LANZ history
#
#    Version 1.0 2013-04-16
#    Written by: 
#       Alexis Dacquay, Arista Networks
#
#    Revision history:
#       1.0 - initial release
#       1.1 - Added minimal y range (2:) to the gnuplot configs. Changed default to -ld.
#				  Added auto-scroll even without new records

'''
   DESCRIPTION
      The LANZ History visually presents local LANZ historical data in ASCII graphs
      with GNUplot
      
   SYNOPSIS
      lh 				is the EOS CLI command (alias) providing visual outputs
      lanz_history.sh	is the python script collecting and presenting data
      gnuplot.swix		is the standard GNU package providing graph plotting
      
   INSTALLATION
      In order to install LANZ History:
      
      1) Copy 'lanz_history.sh' to /mnt/flash.
         Example:
         Arista#copy scp user@192.168.0.1:lanz_history.sh flash:
      
      2) Copy the extension gnuport.swix in the extension: partition
         Example:
         Arista#copy scp user@192.168.0.1:gnuport.swix extension:
      
      3) Verify availability of the extension (Status A but NI)
         Arista#show extension
         Name                 Version/Release           Status RPMs
         -------------------- ------------------------- ------ ----
         gnuplot.swix         4.4.0/5.fc14              A, NI    46
      
      4) Install the extension
         Arista#extension gnuplot.swix
      
      5) Verify correct installation (Status A and I)
         Arista#show extension
         Name                 Version/Release           Status RPMs
         -------------------- ------------------------- ------ ----
         gnuplot.swix         4.4.0/5.fc14              A, I     46

      6) Configure background data collection 
      LANZ History relies on local data collection, which can then be started using:
         (bash:root)# /mnt/flash/lanz_history [<options>] &
      and you can use 'nohup' utility in order to make this persistent
      over ssh:
         (bash:root)# nohup /mnt/flash/lanz_history [<options>] &      

      See: 
         (bash:root)# /mnt/flash/lanz_history --help
      for details about the command-line options.

      In order to run LANZ History as a daemon (persistent after reboot),
      add the following to the startup-config:

         event-handler lanz_monitor
            trigger on-boot
            action bash sudo /usr/bin/daemonize 
               /mnt/flash/lanz_history [<options>] &
               
      The LANZ History process name is 'lanz_history', so standard Linux
      tools can be used to stop and restart it with different
      command-line options:

      e.g.
         (bash:root)# pkill lanz_history
         (bash:root)# /mnt/flash/lanz_history [<new-options>] &

      Note that in order to make sure the LANZ History does not
      restart on reboot / starts with a different config on reboot,
      the startup-config has to be changed accordingly.

      In order to uninstall LANZ History , use:
         (bash:root)# pkill lanz_history
         (bash:root)# rm /mnt/flash/lanz_history.sh

   
   CONFIGURATION/DEBUGGING
      The configuration of the script can be found in the highlighted
      section below.

      In order to enable debugging output to stdout, use the '--debug'
      command line option.
      e.g.
         (bash:root)# /mnt/flash/lanz_history -d &

   COMPATIBILITY
      Version 1.0 has been developed and tested against
      EOS-4.13.3F. Please reach out to support@aristanetworks.com if
      you want to run this against a different EOS release.

  LIMITATIONS
      None known.
'''

#import jsonrpclib
from __future__ import print_function
import jsonrpclib
import optparse
import datetime
import io
import socket
import time
import os
from ctypes import cdll, byref, create_string_buffer
# sys and signal are used to quit by Ctrl+C without tracekack
import sys
import signal

#-------------------Configuration------------------------
EAPI_USERNAME = 'admin'
EAPI_PASSWORD = ''
EAPI_ENABLE_PASSWORD = ''

# http or https method
EAPI_METHOD = 'http'

# How often to poll for information (seconds)
EAPI_POLL_INTERVAL = 1       # in seconds

ENTRY_TYPE = {
    1 : 'START',
    2 : 'UDPATE',
    3 : 'END' }

VERSION_ID = '_v1.2'			# default (for release) should be ''

# - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# ASCII datastore of the LANZ statistics for GNUplot
DATA_FILE = '/tmp/lanz_history' + VERSION_ID + '.dat'
DATA_FILE_DROPS = '/tmp/lanz_history_drops' + VERSION_ID + '.dat'
DATA_FILE_LATENCY = '/tmp/lanz_history_latency' + VERSION_ID + '.dat'

# config script file for gnuplot
CONFIG_FILE = '/tmp/lanz_history' + VERSION_ID + '.conf'
CONFIG_FILE_DROPS = '/tmp/lanz_history_drops' + VERSION_ID + '.conf'
CONFIG_FILE_LATENCY = '/tmp/lanz_history_latency' + VERSION_ID + '.conf'

# bash script for dynamic alias, selecting different graphs from a single alias with args
LAUNCHER_FILE = '/tmp/lanz_history_launcher.sh'

# EOS CLI alias to call the LANZ history
ALIAS = 'lh'

#--------------------------------------------------------

errors = {}

def getTimeFromTS(ts):
    return datetime.datetime.fromtimestamp(ts / 100000).strftime('%H:%M:%S(%Y-%m-%d)')

def setProcName(newname):
    # This function allow tracking this script by name from bash/kernel
    libc = cdll.LoadLibrary( 'libc.so.6' )
    buff = create_string_buffer( len( newname ) + 1 )
    buff.value = newname    
    libc.prctl( 15, byref( buff ), 0, 0, 0)

def buildGnuplotConf():
    # This function writes config files for gnuplot, called from watch
    # Congestion (default) gnuplot config file
    with open(CONFIG_FILE, 'w') as f:
		f.write( 'set style data histogram' + '\n')
		f.write( 'set terminal dumb' + '\n')
		#f.write( 'set yrange [2:]' + '\n')
		f.write( 'plot \'%s\' using 1:xtic(2)' % ( DATA_FILE ) + '\n')

    # Drops gnuplot config file
    if drops:
		with open(CONFIG_FILE_DROPS, 'w') as f:
			f.write( 'set style data histogram' + '\n')
			f.write( 'set terminal dumb' + '\n')
			f.write( 'set yrange [2:]' + '\n')
			f.write( 'plot \'%s\' using 1 with line' % ( DATA_FILE_DROPS ) + '\n')
    
    # Latency gnuplot config file
    if latency:
		with open(CONFIG_FILE_LATENCY, 'w') as f:
			f.write( 'set style data histogram' + '\n')
			f.write( 'set terminal dumb' + '\n')
			f.write( 'set yrange [2:]' + '\n')
			f.write( 'plot \'%s\' using 1 with line' % ( DATA_FILE_LATENCY ) + '\n')

def configureAlias():
    eapi = EApiClient()
    response = eapi.runEnableCmds([ 
        'configure',
           'alias %s bash %s' % ( ALIAS, LAUNCHER_FILE) ] )
           
# Previous version of the alias, without launcher. Now employing dynamic launcher.
#           'alias %s bash watch -n %d gnuplot %s' % \
#               ( ALIAS, EAPI_POLL_INTERVAL, CONFIG_FILE ) ] )

class EApiClient( object ):

    def __init__( self ):
        url = '%s://%s:%s@localhost/command-api' % \
              ( EAPI_METHOD, EAPI_USERNAME, EAPI_PASSWORD )
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
            return [ x.values()[ 0 ] for x in result ]
        else:
            return result
            
    def lanzCongestion( self ):
        global old_response
        global sleep_count
        response = self.runEnableCmds( [ 'show queue-monitor length %s limit %d ' \
            'samples' % (intf, qty) ] )
        #except Exception as e: 
        #   print( 'DEBUG ! This is an error: %s' % e )
        #   import pdb; pdb.set_trace()
        
        entryList = response[0]['entryList']
        entryList.reverse();							# We want the oldest first
        with open(DATA_FILE, 'w') as f:
        		if (not old_response):
					# comparator does not yet exist (normally the very initial poll)
        			old_response = entryList
        			
        		elif (entryList == old_response):
        			# If no new data was added since last poll, we simulate time-based scroll
        			sleep_count += 1
        			if debug:
        				print('No new record detected. Scrolling older data by %d column(s) ' \
        					% (sleep_count) )
        			entryList = entryList[sleep_count - 1:]	# slicing out the beginning
        			        			#i = sleep_count
        			#while i:
        			#	i -= 1
        			#	obj=entryList[0]
        			#	entryList.remove(obj)
        			#	f.write( '0\t0\n' )
        				
        		else:
        			# If new records exist we capture the dataset to compare at the next poll
        			old_response = entryList
        			
        		if debug:
        			print('The original data is scrolled/truncated to %d' % (len(entryList)))
        		for entry in entryList:
        			f.write( str(entry[ 'queueLength' ]) + '\t' + \
        			str(entry[ 'entryType' ]) + '\n')
        		i = sleep_count
        		while i:
        			i -= 1
        			f.write( '0\t.\n' )
        			
    def lanzLatency( self ):
        response = self.runEnableCmds( [ 'show queue-monitor length %s limit %d ' \
            'samples tx-latency' % (intf, qty) ] )
        entryList = response[0]['entryList']
        with open(DATA_FILE_LATENCY, 'w') as f:
            for entry in entryList:
                f.write( str(entry[ 'txLatency' ]) + '\n')
                
    def lanzDrops( self ):
        response = self.runEnableCmds( [ 'show queue-monitor length %s limit %d ' \
            'samples drops' % (intf, qty) ] )
        entryList = response[0]['entryList']
        with open(DATA_FILE_DROPS, 'w') as f:
            for entry in entryList:
                f.write( str(entry[ 'txDrops' ]) + '\n')

def checkLanz():
	eapi = EApiClient()

	while True:
		trace( 'Collecting latency' )
		eapi.lanzLatency()
		trace( 'Collecting Drops' )
		eapi.lanzDrops()
		trace( 'Collecting Congestion' )
		eapi.lanzCongestion()
		
		time.sleep(EAPI_POLL_INTERVAL)

def trace( msg ):
    if debug:
        print (msg)


# Variable initialisation
debug = None
drops = True
intf=''
latency = True
noscaling = None
qty = 70
maxqty = 100
iAmHere = (os.path.realpath(__file__))
old_response = ''
sleep_count = 0

def main():
    global debug
    global drops
    global intf
    global latency
    global qty
    global maxqty
    global old_response
    signal.signal(signal.SIGINT, lambda x,y: sys.exit(0))
    setProcName( 'lanz_history' )
    old_response = ''
    
    # Create help string and parse cmd line
    usage = 'usage: %prog [options]'
    op = optparse.OptionParser(usage=usage)
    op.add_option( '-x', '--debug', dest='debug', action='store_true',
                   help='print debug info' )
	 # Change of default: We now unconditionally track LANZ drops
    #op.add_option( '-d', '--drops', dest='drops', action='store_true',
    #               help='show drops data' )
    op.add_option( '-i', '--intf', dest='intf', action='store',
                   help='selection of interfaces', type='string',
                   default='')
	 # Change of default: We now unconditionally track LANZ TX-latency
	 #op.add_option( '-l', '--latency', dest='latency', action='store_true',
    #               help='show latency data' )
    op.add_option( '-n', '--noscaling', dest='noscaling', action='store_true',
                   help='by default autoscale fits all the historical data in the graph' )
    op.add_option( '-q', '--quantity', dest='qty', action='store',
                   help='quantity of entries looked at and stored', type='int',
                   default=70)
    opts, _ = op.parse_args()
    
    debug = opts.debug
    #drops = opts.drops
    intf = opts.intf
    #latency = opts.latency
    noscaling  = opts.noscaling
    qty = opts.qty
        
    if debug:
        print('This script is located here:\n%s' % (iAmHere) )
        print('')
        print('Review of the options selected:')
        print('debug:\t\t' + str(debug))
        print('drops:\t\t' + str(drops))
        print('intf:\t\t' + str(intf))
        print('latency:\t' + str(latency))
        print('qty:\t\t' + str(qty))
        print('Filenames - DATA file:\t\t' + str(DATA_FILE))
        print('')
    if qty > maxqty:
        print( 'Note: The maximum amount of entries is %d' % maxqty)
        qty = maxqty    
    # Now commented as default is now to have congestion+drops+latency collected
    #if drops and latency:
    #    print( 'Warning: Only one mode is supported, either drops or latency.' \
    #        'Defaulting to neither with queue depth mode' )
    #    drops = latency = None
    
    # In case of parsing mistyping we could show:
    #parser.print_help()
    #exit(-1)
    #syslog.openlog( 'lanzhistory', 0, syslog.LOG_LOCAL4 )
    
    buildGnuplotConf()
    configureAlias()
    checkLanz()

if __name__ == '__main__':
   main()


