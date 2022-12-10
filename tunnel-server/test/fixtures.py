
TEST_CONFIG='''# Sample UDS tunnel configuration

# Pid file, optional
pidfile = {pidfile}
user = {user}

# Log level, valid are DEBUG, INFO, WARN, ERROR. Defaults to ERROR
loglevel = {loglevel}

# Log file, Defaults to stdout
logfile = {logfile}

# Max log size before rotating it. Defaults to 32 MB.
# The value is in MB. You can include or not the M string at end.
logsize = {logsize}

# Number of backup logs to keep. Defaults to 3
lognumber = {lognumber}

# Listen address. Defaults to 0.0.0.0
address = {address}

# Number of workers. Defaults to  0 (means "as much as cores")
workers = {workers}

# Listening port
port = 7777

# SSL Related parameters. 
ssl_certificate = {ssl_certificate}
ssl_certificate_key = {ssl_certificate_key}
# ssl_ciphers and ssl_dhparam are optional.
ssl_ciphers = {ssl_ciphers}
ssl_dhparam = {ssl_dhparam}

# UDS server location. https NEEDS valid certificate if https
# Must point to tunnel ticket dispatcher URL, that is under /uds/rest/tunnel/ on tunnel server
# Valid examples:
#  http://www.example.com/uds/rest/tunnel/ticket
#  https://www.example.com:14333/uds/rest/tunnel/ticket
uds_server = {uds_server}
uds_token = {uds_token}

# Secret to get access to admin commands (Currently only stats commands). No default for this.
# Admin commands and only allowed from "allow" ips
# So, in order to allow this commands, ensure listen address allows connections from localhost
secret = {secret}

# List of af allowed admin commands ips (Currently only stats commands).
# Only use IPs, no networks allowed
# defaults to localhost (change if listen address is different from 0.0.0.0)
allow = {allow}
'''