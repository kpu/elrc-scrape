#!/bin/bash
for ((i=0;i<5000;++i)); do if [ ! -s $i.json ]; then echo wget -O $i.json https://www.elrc-share.eu/repository/export_json/$i/; fi; done |parallel
