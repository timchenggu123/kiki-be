#!/bin/bash
if [ ! -e ~/ssl_initialized ]; then
	certbot --nginx --non-interactive --agree-tos --email 2013tim.g@gmail.com -d kikiserver.timgu.me
	touch ~/ssl_initialized
fi

