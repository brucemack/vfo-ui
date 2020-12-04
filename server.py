#import socket
#import led

print("Starting ...")

"""
def web_page():
  if led.value() == 1:
    gpio_state="ON"
  else:
    gpio_state="OFF"
  
  html = """<html><head> <title>ESP Web Server</title> <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
  h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
  border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
  .button2{background-color: #4286f4;}</style></head><body> <h1>ESP Web Server</h1> 
  <p>GPIO state: <strong>""" + gpio_state + """</strong></p><p><a href="/?led=on"><button class="button">ON</button></a></p>
  <p><a href="/?led=off"><button class="button button2">OFF</button></a></p></body></html>"""
  return html

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 8080))
s.listen(5)

while True:
  conn, addr = s.accept()
  print('Got a connection from %s' % str(addr))
  request = conn.recv(1024)
  request = request.decode("utf8")
  # Parse the request 
  request_line, headers = request.split("\r\n", 1)  
  # First line (space delimited): METHOD URL PROTOCOL
  request_method, request_url, request_proto = request_line.split(" ")
  # Pull out the query parameters and put them into a dictionary
  query_parameters = {}
  request_url_components = request_url.split("?")
  if len(request_url_components) > 1:
      query_parameter_parts = request_url_components[1].split("&")
      for query_parameter_part in query_parameter_parts:
          name, value = query_parameter_part.split("=", 1)
          query_parameters[name] = value
  print(query_parameters)
  # Header lines
  header_lines = headers.split("\r\n")
  print("Headers", header_lines)
  headers = {}
  for header_line in header_lines:
      ()
  led_on = request.find('/?led=on')
  led_off = request.find('/?led=off')
  if led_on == 6:
    print('LED ON')
    led.value(1)
  if led_off == 6:
    print('LED OFF')
    led.value(0)
  response = web_page()
  conn.send(bytes("HTTP/1.1 200 OK\r\n", "utf8"))
  conn.send(bytes("Content-Type: text/html\r\n", "utf8"))
  conn.send(bytes("Connection: close\r\n\r\n", "utf8"))
  conn.sendall(bytes(response, "utf8"))
  conn.shutdown(socket.SHUT_RDWR)
  conn.close()
  break

s.close()
"""