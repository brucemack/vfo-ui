import socket
import network
import time 
import uerrno
import sys
from select import select

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)

# Change name/password of ESP8266's AP:
print("# Starting server")
print("#", sta_if.ifconfig())

freq = 7040000

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
  #conn.send(bytes("Connection: close\r\n\r\n", "utf8"))
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
  #print("URL", url, query_parameters)
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
    print("F " + str(int(freq)))
  else:
    conn.send(bytes("HTTP/1.1 401 NOTFOUND\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n\r\n", "utf8"))


def process_received_data(buffer, conn):
  # Check to see if we've got a blank line yet
  i = buffer.find("\r\n\r\n")
  if i == -1:
    return buffer
  else:
    # Pull off the complete request
    request = buffer[0:i]
    # Parse the request 
    request_line, headers = request.split("\r\n", 1)  
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
    # Header lines
    header_lines = headers.split("\r\n")
    headers = {}
    for header_line in header_lines:
        tokens = header_line.split(":")
        if len(tokens) >= 2:
          name = tokens[0]
          value = tokens[1]
          headers[name.strip()] = value.strip()
    #print("Headers", headers)
    process_get(request_url, query_parameters, headers, conn)
    return buffer[i+4:]


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 8080))
s.listen(5)
s.setblocking(False)
timeout = 0.05

# Main event loop
while True:

  # Check for stdin
  rlist, _, _ = select([sys.stdin, s], [], [], timeout)
  if rlist:
    print("# hit", rlist)
    if rlist[0] == sys.stdin:
      r = sys.stdin.read(1)
      print("# got ",r)

  try:
    # Attempt to receive a connection from a web client
    conn, addr = s.accept()
    print("# Connection", str(addr))
    conn.setblocking(False)
    # This is where we gather the request
    accumulator = ""
    tries = 0
    # Data processing loop
    while True:
      try:
        tries = tries + 1
        rdata = conn.recv(1024)
        if len(rdata) == 0:
          break
        rdata = rdata.decode("utf8")
        accumulator = accumulator + rdata
        accumulator = process_received_data(accumulator, conn)
        # Was a complete message processed?
        if accumulator == "":
          break
        # Still trying to accumulate a request, but don't spin
        time.sleep_ms(50)
      except OSError as e:
        if e.args[0] == uerrno.EAGAIN:
          if tries <= 4:
            # Still waiting for data, but don't spin
            time.sleep_ms(50)
            continue
          else:
            print("# Timeout")
            break
        else:
          print("# Other error")
          break

      """
      """
    conn.close()

  except OSError as e:
    time.sleep_ms(100)

s.close()

