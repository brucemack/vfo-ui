import socket
import network
import time 
import uerrno
import sys
from select import select
import gc
import machine 

freq = 7040000
version = 1


def format_khz(f):
  kh = int(f / 1000)
  frac = int(f % 1000)
  return "{0:,d}".format(kh) + "." + "{0:03d}".format(frac)


def root_page():
  global freq
  html = """
  <html>
  <head> 
  <title>VFO Control</title> 
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <link href="static/main.css" rel="stylesheet"/>
  </head>
  <body> 
  <p class="freq">VFO: """ + format_khz(freq) + """
  </p>
  <form action="/" method="get">
  <input type="text" name="freq"/>
  <button type="submit" name="cmd" value="edit">Edit</button>
  <span class="ctl">|</span>
  <button type="submit" name="cmd" value="dn1000">Dn 1.0K</button>
  <button type="submit" name="cmd" value="dn500">Dn 0.5K</button>
  <button type="submit" name="cmd" value="dn100">Dn 0.1K</button>
  <span class="ctl">|</span>
  <button type="submit" name="cmd" value="up100">Up 0.1K</button>
  <button type="submit" name="cmd" value="up500">Up 0.5K</button>
  <button type="submit" name="cmd" value="up1000">Up 1.0K</button>
  </form>
  </body>
  </html>
  """
  return html

def setup_page():
  global freq
  html = """
  <html>
  <head> 
  <title>VFO Control Setup</title> 
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <link href="static/main.css" rel="stylesheet"/>
  </head>
  <body> 
  <h1>WIFI Configuration</h1>
  <form action="/setup" method="get">
  <label>ESSID:</lable>
  <input type="text" size="40" name="essid"/>
  <label>Password:</lable>
  <input type="text" name="password"/>
  <button type="submit">Save</button>
  </form>
  </body>
  </html>
  """
  return html

def save_wifi_credentials(essid, password):
  """ Saves the WIFI credentials on the local filesystem """
  try:
    f = open("wifi_credentials.txt","w")
    f.write(essid)
    f.write("\n")
    f.write(password)
    f.write("\n")
    f.close()
  except:
    print("# Unable to save WIFI credentials")


def send_response(content, content_type, conn):
  conn.send(bytes("HTTP/1.1 200 OK\r\n", "utf8"))
  conn.send(bytes("Content-Type: " + content_type + "\r\n", "utf8"))
  conn.send(bytes("Connection: close\r\n", "utf8"))
  conn.send(bytes("\r\n", "utf8"))
  conn.sendall(bytes(content, "utf8"))


def detect_content_type(name):
  if name.endswith(".css"):
    return "text/css"
  elif name.endswith(".ico"):
    return "image/x-icon"
  else:
    return "application/octet-stream"


def send_all_blocking(conn, buf):
  """ Performs a blocking write for a buffer.
      Works even if the underlying socket is non-blocking. """
  # TODO: Timeout is needed to prevent hang
  while len(buf) > 0:
    # TODO: ADD SELECT FOR EFFICIENCY
    try:
      rc = conn.send(buf)
      if rc > 0:
        # Progress, reduce size of buffer
        buf = buf[rc:]
      else:
        # No spin
        time.sleep_ms(1)
    except OSError as ex:
      if ex.args[0] == uerrno.EAGAIN:
        # No spin
        time.sleep_ms(1)
      else:
        print("# static file error", ex.args[0])
        break

def send_static_file(fn, conn):
  """ Sends a static file from the local filesystem
  """ 
  content_type = detect_content_type(fn)
  try:
    with open(fn, "b") as f:
      conn.send(bytes("HTTP/1.1 200 OK\r\n", "utf8"))
      conn.send(bytes("Content-Type: " + content_type + "\r\n", "utf8"))
      # Enable caching for static assets
      conn.send(bytes("Cache-Control: public, max-age=604800, immutable\r\n", "utf8"))
      conn.send(bytes("Connection: close\r\n", "utf8"))
      conn.send(bytes("\r\n", "utf8"))
      # Transfer in small chunks to avoid memory issues
      while True:
        chunk = f.read(512)
        if len(chunk) == 0:
          break
        send_all_blocking(conn, chunk)
  except Exception as ex:
    print("# static file error", ex.args[0])
    conn.send(bytes("HTTP/1.1 401 NOTFOUND\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n", "utf8"))
    conn.send(bytes("\r\n", "utf8"))


def process_get(url, query_parameters, headers, conn):
  global freq
  # Static artifacts
  if url.startswith("/static/"):
    send_static_file(url, conn)
  # The shortcut icon
  elif url == "/favicon.ico":
    send_static_file("/static/favicon.ico", conn)
  # The setup url
  elif url == "/setup":
    if "essid" in query_parameters and "password" in query_parameters:
      save_wifi_credentials(query_parameters["essid"], query_parameters["password"])
      # Reboot
      machine.reset()
    # Re-render
    send_response(setup_page(), "text/html", conn)
  # The main page
  elif url == "/":
    # Process form actions if any
    if "cmd" in query_parameters:
      if query_parameters["cmd"] == "up1000":
        freq = freq + 1000
      elif query_parameters["cmd"] == "up500":
        freq = freq + 500
      elif query_parameters["cmd"] == "up100":
        freq = freq + 100
      elif query_parameters["cmd"] == "dn1000":
        freq = freq - 1000
      elif query_parameters["cmd"] == "dn500":
        freq = freq - 500
      elif query_parameters["cmd"] == "dn100":
        freq = freq - 100
      elif query_parameters["cmd"] == "edit" and query_parameters["freq"] != "":
        freq = int(query_parameters["freq"]) * 1000
    # Re-render
    send_response(root_page(), "text/html", conn)
    # Report frequency
    print("f " + str(int(freq)))
  else:
    conn.send(bytes("HTTP/1.1 401 NOTFOUND\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n\r\n", "utf8"))


def urldecode(s):
  """ Reverses URL encoding. 
      NOTE: This needs a lot of work. 
  """
  return s.replace("+"," ")


# This is the function that processes the data received from 
# the HTTP client. 
def process_received_data(buffer, conn):
  # It is possible that multiple requests are contained in the 
  # same request so we keep on cycling until the entire buffer
  # is consumed.
  while True:
    if len(buffer) == 0:
      return ""
    else:
      # Check to see if we've got a blank line that indicates the 
      # end of the HTTP request.
      i = buffer.find("\r\n\r\n")
      if i == -1:
        return buffer
      else:
        # Pull off the complete request
        request = buffer[0:i]
        # Parse the request 
        request_line, headers_raw = request.split("\r\n", 1)  
        # First line (space delimited): METHOD URL PROTOCOL
        request_method, request_url, request_proto = request_line.split(" ")

        # Pull out the query parameters and put them into a dictionary
        query_parameters = {}
        request_url_components = request_url.split("?")
        request_url = request_url_components[0]
        if len(request_url_components) > 1:
          query_parameter_parts = request_url_components[1].split("&")
          for query_parameter_part in query_parameter_parts:
              tokens = query_parameter_part.split("=")
              if len(tokens) >= 2:
                name = tokens[0]
                value = urldecode(tokens[1])
                query_parameters[name] = value

        # Pull out the headers and put them in a dictioary
        headers = {}
        header_lines = headers_raw.split("\r\n")
        for header_line in header_lines:
            tokens = header_line.split(":")
            if len(tokens) >= 2:
              name = tokens[0]
              value = tokens[1]
              headers[name.strip()] = value.strip()

        # Process the GET request
        process_get(request_url, query_parameters, headers, conn)

        # Discard the part of the buffer that was successfully processed
        buffer = buffer[i+4:]

# Main setup
print("# Starting server")
gc.collect()

# Read the WIFI credentials from the local filesystem
wifi_essid = None
wifi_password = None

try:
  f = open("wifi_credentials.txt")
  content = f.readlines()
  f.close()
  if len(content) >= 2:
    wifi_essid = content[0].strip()
    wifi_password = content[1].strip()
except:
  print("# Unable to read WIFI credentials")
  pass

# If possible, connect to the local WIFI network
if not wifi_essid is None:
  print("# Connecting to", wifi_essid)
  sta_nic = network.WLAN(network.STA_IF)
  sta_nic.active(True)
  sta_nic.connect(wifi_essid, wifi_password)
  # TODO: Timeout on this 
  #while not sta_nic.isconnected():
  #  pass
else:
  sta_nic = None

# Make sure we are listening as an Access Point to support configuration
ap_nic = network.WLAN(network.AP_IF)
ap_nic.active(True)
# TODO: Timeout on this
while ap_nic.active() == False:
  pass
ap_nic.config(essid="KC1FSZ-VFO")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 80))
s.listen(5)
s.setblocking(False)

select_timeout = 0.250
# This is the list of items that select will watch for
select_list = []
# Flag to keep things going
run_flag = True


def report_network_status():
  if not sta_nic is None and sta_nic.isconnected():
    print("n 1", sta_nic.ifconfig()[0])
  else:
    print("n 0")


def print_status():
  global version
  global frequency 
  print("q " + str(version) + " " + str(freq) + " " + str(gc.mem_free()))

def do_stdin_read(item):
  global run_flag

  r = item[0].read(1)
  if r == "x":
    run_flag = False
  elif r == "q":
    print_status()
  elif r == "n":
    report_network_status()
  elif r == "r":
    machine.reset()
  else:
    print("# stdin got",r)    


def do_client_read(item):
  conn = item[0]
  try:
    # Read some data off the socket
    rdata = conn.recv(1024)
    # If there is no data then the client has disconnected
    if len(rdata) == 0:
      conn.close()
      # Mark the item has unused
      item[0] = None
    else:
      rdata = rdata.decode("utf8")
      # Here is where we accumlate the data received for a client
      item[2] = item[2] + rdata
      # Anything left over will be left in the accumulator for 
      # later (when the rest of the request is received)
      item[2] = process_received_data(item[2], conn)
      # If there is anything left in the buffer then stand by for 
      # more activity, otherwise we close the connection.
      if len(item[2]) == 0:
        conn.close()
        item[0] = None
  except Exception as ex:
    # Any error should cause the socket to be terminated
    print("# Closing client (error)", ex.args[0])
    conn.close()
    item[0] = None
    

# This function should be called when a server socket is 
# ready to accept a new connection 
def do_socket_accept(item):
  global select_list
  try:
    # Attempt to receive a connection from a web client
    conn, addr = item[0].accept()
    #print("# Connection", str(addr))
    conn.setblocking(False)
    # Schedule read monitoring for the new client
    select_list.append([conn, do_client_read, ""])
  except OSError as ex:
    print("# Accept error", ex.args[0])

report_network_status()

# Schedule monitoring of server socket
select_list.append([s, do_socket_accept])
# Schedule monitoring of stdin
select_list.append([sys.stdin, do_stdin_read])

# Main event loop
while run_flag:

  # Check for activity.  Make a list of all of the files 
  # that we are waiting for read activity on
  poll_list = []
  for select_item in select_list:
    poll_list.append(select_item[0])
  # Here is where the brief blocking happens to see if any 
  # I/O is possible:
  rlist, _, _ = select(poll_list, [], [], select_timeout)
  if rlist:
    # Figure out which item needs attention
    for select_item in select_list:
      if rlist[0] == select_item[0]:
        # Fire callback that was registered
        select_item[1](select_item)
  # Clean out list of any dead items
  select_list = [item for item in select_list if item[0] != None]

s.close()
print("# Shutting down")
