#!/usr/bin/env python3
#
# Delem (Delay Emulator) is a front end to remote 'tc' sessions. 'tc' (traffic control) has a very
# arcane syntax. Delem makes it easier to control delay and packet loss for demonstrations and Proof of
# Concepts.
#
# The command like help looks like this...
#
#sherk@MBP:[~/unixdir/src/python/FBI/tcs] ./delem.py -h
#usage: delem.py [-h] [-c CONF] [--debug] node
#
#Control impairments on remote devices.
#
#positional arguments:
#  node                  Specifiy the node to change the delay
#
#optional arguments:
#  -h, --help            show this help message and exit
#  -c CONF, --conf CONF  A different config file
#  --debug, -d
#
#
# Config file: Delem will look for the config file in the following places:
#    1) the command line '--conf'
#    2) An Environment Variable with the path to the config file.
#    3) A file in the user's home directory (~/.delem.conf)
#    4) A file (./delem.conf) in the cwd.
#
# The syntax of the config file is
# [name of node ]                                                               
# addr = IP address of node                                                     
# user = login name                                                             
# passwd = login password                                                       
# defInt = Default Interface                                                    
# IntList = Interface List, the list of interfaces where you add delay
#
import argparse
import re
import paramiko
import configparser
import io
import cmd
import os, sys

# Init several global variables. 
delay = False
loss = False
Int = ''
client=False
node=''
config=''
conf=''
#----
# Read the command line for the arguments
#
def ParseArgs():
    parser = argparse.ArgumentParser(description="Control impairments on remote devices.")

    parser.add_argument("node", help="Specifiy the node to change the delay")
    parser.add_argument('-c', "--conf", help="A different config file")
    parser.add_argument('--debug', '-d', action='count', default=0)
    args = parser.parse_args()
    if ( debug ):
        print("Node: ", node)
        print("Conf: ", conf)
        print("Debug: ", debug)

    return(args.node, args.conf, args.debug)
#----

#----
# Look for the config file and parse it 
def ParseConf():
    if (conf != None):
        conf_file = conf
    elif (os.getenv('DELEMCONF')):
        conf_file = os.getenv('DELEMCONF')
    elif os.path.expanduser('~/.delem.conf'):
        conf_file = '~/.delem.conf'
    elif os.path.exits('./delem.conf'):
        conf_file = './delem.conf'
    else:
        print('Config file not found!')
        exit()

    if (debug):
        print(f'conf_file: {conf_file}')

    with open("delem.conf") as f:
        configData = f.read()

    config = configparser.RawConfigParser(allow_no_value=True)
    config.read_file(io.StringIO(configData))    

    return(config)
#----
# Set the queue depth for an interface. Delayed packets will use this space
def SetTClimit(client, Int, value):
    cmd = f"tc qdisc show dev {Int}"
    execTC(client, Int, cmd)

#----
# Get the status of an interface. Look for existing delay and loss values. They are persistant
def GetTCstatus(client, Int):
    global delay, loss
    cmd = f"tc qdisc show dev {Int}"

    if (debug):
        print(f'GetTCstatus: Int: {Int} Delay: {delay} Loss: {loss} CMD: {cmd}')

    stdin, stdout, stderr = execTC(client, Int, cmd)
    string = stdout.read().decode()

    if (debug):
        print(f'[{string}]')
        
    tc = re.match(r'qdisc pfifo_fast \d+: root refcnt', string)
    if tc:
        delay = False
        loss = False
        print(f'{Int}: no impairments')
        return

    tc = re.match(r'qdisc netem \d{4}: root refcnt \d+ limit (\d+)', string)
    if tc:
        print(f'{Int}: Limit: {tc.group(1)}', end=' ')

        delay = False
        loss = False

        tc = re.search(r'delay (\d+)\.0ms', string)
        if tc:
            delay = tc.group(1)
            print(f'Delay: {delay}.0ms', end=' ')

        tc = re.search(r'loss (\d+)\%', string)
        if tc:
            loss = tc.group(1)
            print(f'Loss: {loss}%', end=' ')
        print()
        if (debug):
            print(f'GetTCstatus 2: Int: {Int} Delay: {delay} Loss: {loss}')        
        return
    else:
        print("Bad Parse of 'tc' output!")
        exit()

#----
# Clear any imparements from an interface
def clearTC(client, Int):
    cmd = f"tc qdisc delete dev {Int} root"
    execTC(client, Int, cmd)
    GetTCstatus(client, Int)

#----
# Set delay on an interface
def setTCdelay(client, Int, value):
# There are 3 cases
# Add, Change, Change/Loss
    
    if (debug):
        print(f'setTCdelay: Int: {Int} Delay: {delay} Loss: {loss}')

    if ((not delay) and (not loss)):
        cmd = f"tc qdisc add dev {Int} root netem delay {value}ms"
    elif (not loss):
        cmd = f"tc qdisc change dev {Int} root netem delay {value}ms"
    else:
        cmd = f"tc qdisc change dev {Int} root netem delay {value}ms loss {loss}"

    execTC(client, Int, cmd)
    GetTCstatus(client, Int)

#----
def setTCloss(client, Int, value):
# There are 3 cases
# Add, Change, Change/Loss
    
    if (debug):
        print(f'setTCloss: Int: {Int} Delay: {delay} Loss: {loss}')

    if ((not delay) and (not loss)):
        cmd = f"tc qdisc add dev {Int} root netem loss {value}"

    elif (not delay):
        cmd = f"tc qdisc change dev {Int} root netem loss {value}"
    else:
        cmd = f"tc qdisc change dev {Int} root netem delay {delay}ms loss {value}"

    if (debug):
        print(cmd)
        
    execTC(client, Int, cmd)
    GetTCstatus(client, Int)

#---
# Send a 'tc' command to the remote node
def execTC(client, Int, cmd):

    stdin, stdout, stderr = client.exec_command(cmd)
    error = stderr.read().decode()
    if error:
        print(f"[{error}]")
        exit()

    return stdin, stdout, stderr

#-----
# The CMD class provides a simple CLI shell. Please see:
# https://docs.python.org/3/library/cmd.html

class DelemCmd(cmd.Cmd):
    """Simple shell command processor for delem."""
    global Int, IntList, client

    def preloop(self):
        # Put the current interface in the prompt.
        self.prompt = f"Delem({Int}): "
        
    def do_interface(self, arg):
        "Set the interface to use."
        Int = arg
        GetTCstatus(client, Int)
        self.prompt = f"Delem({Int}): "

    def complete_interface(self, text, line, begidx, endidx):
        if not text:
            completions = IntList
        else:
            completions = [ f for f in IntList if f.startswith(text)]
        return completions

    def do_node(self, arg):
        "Change the node we are connected to."
        if (debug):
            print(f'Change node to {arg}')
        Int, IntList = SetTCnode(client, config, arg)
        for i in IntList:
            GetTCstatus(client, i)
        
    def complete_node(self, text, line, begidx, endidx):
        if not text:
            completions = NodeList
        else:
            completions = [ f for f in NodeList if f.startswith(text)]
            
    def do_clear(self, arg):
        "Set the interface back to normal."
        if (arg == 'all'):
            for i in IntList:
                clearTC(client, i)
        else: 
            clearTC(client, arg)
            
    def do_status(self, arg):
        "Show the current status."
        if (arg == 'all'):
            for i in IntList:
                GetTCstatus(client, i)
        else:
            GetTCstatus(client, Int)

    def do_delay(self, arg):
        "Set the delay to use in ms."
        setTCdelay(client, Int, arg)

    def do_loss(self, arg):
        "Set the loss percentage."
        setTCloss(client, Int, arg)
        
    def do_EOF(self, line):
        "Ctrl-D to quit."
        return True

    def do_quit(self, line):
        "Bye-bye!"
        return True
    
    def emptyline(self):
        """Called when an empty line is entered in response to the prompt."""
        if self.lastcmd:
            self.lastcmd = ""
            return self.onecmd('\n')

#----
# Get config info from the config object and connect to the remote node
def SetTCnode(client, config, node):

    print(f'Node: {node}')
    try:
        addr = config.get(node, "addr")
        user = config.get(node, "user")
        passwd = config.get(node, "passwd")
        Int = config.get(node, "defInt")
        IntList = config.get(node, "IntList")
    except:
        print(f"Error reading config for {node}!")
        exit()
    IntList = re.findall(r"[\w+\-]+", IntList)

    if ( debug ):
        print("Node: ", node)
        print("Addr: ", addr)
        print("User: ", user)
        print("DefInt ", Int)
        print("IntList ", IntList)

    client.close()

    try:
        client.connect(addr, username = user, password = passwd)
    except:
        print(f"Cannot connecto to {addr}")
        exit()

    return(Int, IntList)
        
#---- Start of Main...

# Get config info
(node, conf, debug)= ParseArgs()
config = ParseConf()
NodeList = config.sections()

if (debug):
    print(f'NodeList: {NodeList}')

if node not in config.sections():
    print(f"Missing node! Node: {node} not found in config file.")
    exit()

# Create the SSH object
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Open the SSH session to the node
Int, IntList = SetTCnode(client, config, node)

# List each node and any imparments
for i in IntList:
    GetTCstatus(client, i)
    
#---
# Main command loop
DelemCmd().cmdloop()
#---

# Bye bye
client.close()

#Below is the syntax for tc for reference
#tc qdisc add dev eth0 root netem delay 200ms	# add 200ms of delay
#tc qdisc del dev eth0 root           		# delete all impairments
#tc qdisc show dev eth0
#tc qdisc change	dev eth0 root netem delay 100ms 10ms 	#100ms +/- 10ms uniform distribution
#tc qdisc change	dev eth0 root netem delay 100ms 10ms 25%      #100ms +/- 10ms 25 % correlation
#tc qdisc change	dev eth0 root netem delay 100ms	10ms distribution normal      # 
#also pareto and	paretonormal
#tc qdisc add dev eth0 root netem loss 10% 	# 10% packet loss
#tc qdisc change	dev eth0 root netem corrupt 5%	      # corrupt	5% of packets
#tc qdisc change	dev eth0 root netem duplicate 1%      # duplicate 1% of	packets
