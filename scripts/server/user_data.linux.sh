#!/bin/bash

sed -i --expression 's|#auth-token-verifier="https://127.0.0.1:8444"|auth-token-verifier="$AUTHENTICATOR_URL"|' /etc/dcv/dcv.conf
sed -i --expression 's|#create-session = true|create-session = true|' /etc/dcv/dcv.conf

systemctl restart dcvserver.service