#!/bin/bash

if [ "${INIT_ACCOUNT}" = "true" ]; then
    echo "Creating account"
    python create_account.py $@
fi

python upload.py & python download.py
