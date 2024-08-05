#!/bin/bash

#Autorun
# cd /etc/init.d/; ln -s /opt/scripts/ora2json_webserv/run.sh

# C R O N 
# git clone ssh://git@bb.com/mon/ora2json_webserv.git  /opt/scripts/ora2json_webserv
# m         h       dom    mon      dow     command
# 0,30      *      *       *       *       cd /opt/scripts/ora2json_webserv && git reset --hard &&  git pull | tee -a /opt/scripts/ora2json_webserv/logs/git.log | grep 'Already up to date.' || (chmod +x ./*sh && . ~/.bashrc &&  bash ./run.sh restart)


###########################################################################################
# F U N C T I O N S
###########################################################################################

function status() {
	echo -n "Check service: "
	[[ ${#service_name} -gt 0 ]] && echo -e "already running on port: $config_port, name: $service_name." || echo "not running."
}


function fstop() {
  date >> logs/server.log
	echo -n "Stop pid: $service_name... " && kill $service_pid >/dev/null && echo "Success" && service_name="" || echo "Error"
	# check service
	service_pid=`ps -ef |grep service_check.sh |grep -v grep | awk '{print $2}'`
  echo -n 'Check service stopping....' && kill -9 $service_pid >/dev/null && echo "Success"  | tee -a logs/server.log
}

function fstart() {
  date >> logs/server.log
	echo  -n "Starting HTTPD service..." | tee -a logs/server.log
	[[ ${#service_name} -gt 0 ]] && echo -e "already running on port: $config_port, name: $service_name." | tee -a logs/server.log && exit 1
	python3 server_JSON.py  >> logs/server.log 2>&1  &
	sleep 2
	service_name=`netstat -apn | egrep "tcp.*:${config_port}.*0.0.0.0.*LISTEN.*python" | awk '{print $7}'`
	if 	[[ ${#service_name} -gt 0 ]]; then
	  echo " Started: $service_name" | tee -a logs/server.log
	  echo "Start check service." | tee -a logs/server.log
	  bash service_check.sh >> logs/server.log 2>&1 &
	else
	  echo " Not started..."
	fi


}






###########################################################################################
# M A I N 
###########################################################################################

cd /opt/scripts/ora2json_webserv/

config_port=`cat config.py | grep http_server_port | cut -d' ' -f3`
service_name=`netstat -apn | egrep "tcp.*:${config_port}.*0.0.0.0.*LISTEN.*python" | awk '{print $7}'`
service_pid=`echo $service_name | cut -d'/' -f1`


if [[ "$1" ==  "restart" ]]; then
	fstop
	fstart
elif [[ "$1" ==  "stop" ]]; then
	fstop
elif [[ "$1" ==  "start" ]]; then
	fstart
else
  echo -e "# Usage: run.sh stop|start|restart|status\n"
	status
fi


