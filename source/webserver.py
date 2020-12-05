import socket
import network
import time 
import uerrno
import sys
from select import select

freq = 7040000
version = 1


def format_khz(f):
  kh = int(f / 1000)
  frac = int(f % 1000)
  return "{0:,d}".format(kh) + "." + "{0:03d}".format(frac)


def web_page():
  global freq
  html = """
  <html>
  <head> 
  <title>VFO Control</title> 
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <link href="main.css" rel="stylesheet"/>
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

def send_response(content, content_type, conn):
  conn.send(bytes("HTTP/1.1 200 OK\r\n", "utf8"))
  conn.send(bytes("Content-Type: " + content_type + "\r\n", "utf8"))
  conn.send(bytes("Connection: close\r\n", "utf8"))
  conn.send(bytes("\r\n", "utf8"))
  conn.sendall(bytes(content, "utf8"))


def send_static(fn, conn):
  # Open file and send
  # TODO: ERROR
  f = open(fn)
  # This reads everything apparently
  content = f.read()
  f.close()
  # TODO: AUTO MAPPING
  content_type = "text/css"
  send_response(content, content_type, conn)


def process_get(url, query_parameters, headers, conn):
  global freq
  if url == "/main.css":
    send_static("/main.css", conn)
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
    response = web_page()
    send_response(response, "text/html", conn)
    # Report frequency
    print("f " + str(int(freq)))
  else:
    conn.send(bytes("HTTP/1.1 401 NOTFOUND\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n\r\n", "utf8"))


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
              if len(tokens) > 1:
                name = tokens[0]
                value = tokens[1]
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
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)

print("# Starting server")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 8080))
s.listen(5)
s.setblocking(False)

select_timeout = 0.250
# This is the list of items that select will watch for
select_list = []
# Flag to keep things going
run_flag = True


def report_network_status():
  if sta_if.isconnected():
    print("n 1", sta_if.ifconfig()[0])
  else:
    print("n 0")


def do_stdin_read(item):
  global run_flag
  global version
  global frequency 

  r = item[0].read(1)
  if r == "x":
    run_flag = False
  elif r == "q":
    print("q " + str(version) + " " + str(freq))
  elif r == "n":
    report_network_status()
  else:
    print("# stdin got",r)    


def do_client_read(item):
  conn = item[0]
  try:
    # Read some data off the socket
    rdata = conn.recv(1024)
    # If there is no data then the client has disconnected
    if len(rdata) == 0:
      print("# Closing client (1)")
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
