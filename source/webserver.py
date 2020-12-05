import socket
import network
import time 
import uerrno

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
print(sta_if.ifconfig())

# Change name/password of ESP8266's AP:
print("Starting server ...")

freq = 70400000

def web_page():
  html = """
  <html>
  <head> 
  <title>VFO Control</title> 
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
  html {
    font-family: Helvetica; 
    display: inline-block; 
    margin: 0px auto; 
  }
  </style>
  </head>
  <body> 
  <p>""" + "{:,}".format(freq) + """
  </p>
  <form action="/" method="get">
  <button type="submit" name="a" value="up">Up</button>
  <button type="submit" name="a" value="down">Down</button>
  </form>
  </body>
  </html>
  """
  return html


def process_get(url, query_parameters, headers, conn):
  print("URL", url, query_parameters)
  if url == "/":
    response = web_page()
    conn.send(bytes("HTTP/1.1 200 OK\r\n", "utf8"))
    conn.send(bytes("Content-Type: text/html\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n\r\n", "utf8"))
    conn.sendall(bytes(response, "utf8"))
  else:
    conn.send(bytes("HTTP/1.1 401 NOTFOUND\r\n", "utf8"))
    conn.send(bytes("Connection: close\r\n\r\n", "utf8"))


def process_received_data(buffer, conn):
  # Check to see if we've got a blank line yet
  i = buffer.index("\r\n\r\n")
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

while True:
  conn, addr = s.accept()
  print('Got a connection from %s' % str(addr))
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
      time.sleep_ms(250)
    except OSError as e:
      if e.args[0] == uerrno.EAGAIN:
        if tries <= 4:
          # Still waiting for data, but don't spin
          time.sleep_ms(250)
          continue
        else:
          print("Timeout")
          break
      else:
        print("Other error")
        break

    """
    """
  conn.close()

s.close()

