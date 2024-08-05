#!/bin/bash

function logcheck() {
  max_log_size_m=4
  cd /opt/scripts/ora2json_webserv/logs/
  du -sm ./* | while read ln; do
      fsize=`echo $ln | awk '{print $1}'`
      fname=`echo $ln | awk '{print $2}'`
      [[ ${fsize} -gt ${max_log_size_m} ]] && tail -100 ${fname} > tmp.log && mv tmp.log ${fname}
  done
}



while : ; do
	sleep 5
	logcheck
  cd /opt/scripts/ora2json_webserv/
	config_port=`cat config.py | grep http_server_port | cut -d' ' -f3`
	#service_name=`netstat -apn | egrep "tcp.*:${config_port}.*0.0.0.0.*LISTEN.*python" | awk '{print $7}'`
	#service_pid=`echo $service_name | cut -d'/' -f1`

	curl http://127.0.0.1:${config_port}/test 2>&1  | grep REC_COUNT >/dev/null
	web_srv_avaible=$?

	#if [[ ${#service_name} -eq 0 ]] || [[ ${web_srv_avaible} -eq 0 ]] ; then
	if [[ ${web_srv_avaible} -ne 0 ]] ; then
	  bash run.sh start &
	  exit 0
	fi
	
done

