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
	config_port=`cat config/config.py | grep http_server_port | cut -d' ' -f3`
	use_ssl=`cat config/config.py | grep '^use_ssl' | cut -d'=' -f2 | tr -d ' '`
	if [[ "$use_ssl" == "True" ]]; then
	  health_url="https://127.0.0.1:${config_port}/health"
	  curl_opts="-ksf"
	else
	  health_url="http://127.0.0.1:${config_port}/health"
	  curl_opts="-sf"
	fi
	#service_name=`netstat -apn | egrep "tcp.*:${config_port}.*0.0.0.0.*LISTEN.*python" | awk '{print $7}'`
	#service_pid=`echo $service_name | cut -d'/' -f1`

	curl ${curl_opts} "${health_url}" 2>&1 | grep '"status": "ok"' >/dev/null
	web_srv_avaible=$?

	#if [[ ${#service_name} -eq 0 ]] || [[ ${web_srv_avaible} -eq 0 ]] ; then
	if [[ ${web_srv_avaible} -ne 0 ]] ; then
	  bash run.sh start &
	  exit 0
	fi
	
done
