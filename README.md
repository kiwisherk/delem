# delem
A front end to remote 'tc' sessions.
Delem (Delay Emulator) is a front end to remote 'tc' sessions. 'tc' (traffic control) has a very
 arcane syntax. Delem makes it easier to control delay and packet loss for demonstrations and Proof of
 Concepts.

 The command like help looks like this...

```sherk@MBP:[~/unixdir/src/python/FBI/tcs] ./delem.py -h
usage: delem.py [-h] [-c CONF] [--debug] node

Control impairments on remote devices.

positional arguments:
  node                  Specifiy the node to change the delay

optional arguments:
  -h, --help            show this help message and exit
  -c CONF, --conf CONF  A different config file
  --debug, -d
```

 Config file: Delem will look for the config file in the following places:
 1. the command line '--conf'
 2. An Environment Variable with the path to the config file.
 3. A file in the user's home directory (~/.delem.conf)
 4. A file (./delem.conf) in the cwd.

 The syntax of the config file is
 ```
 [name of node ]                                                               
 addr = IP address of node                                                     
 user = login name                                                             
 passwd = login password                                                       
 defInt = Default Interface                                                    
 IntList = Interface List, the list of interfaces where you add delay
```
