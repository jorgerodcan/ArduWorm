# ArduWorm. Practical worm PoC

 This PoC implements a practical worm for the Arduino Yun
 This worm will first try to gain persistence in the system it is running
 and to get awareness of its environment. After this, the worm
 will execute its payload, which will be to provide a simple backdoor
 by opening port [port_to_choose] and waiting for connections.
 In addition, the worm exfiltrates the shadow file to a external server
 for cracking and uses this password to expand over the network.
