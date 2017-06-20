#!/usr/bin/python
import os
from distutils.dir_util import copy_tree
import sys
import shutil
import fileinput
import boto
import boto3
import boto.ec2
import boto.s3.connection
from boto.s3.connection import S3Connection
import tempfile
import errno
from boto.s3.key import Key
from subprocess import call
from subprocess import check_output
import zipfile
import logging
import time
import urllib2
import pip
import subprocess
import re
import json
import datetime
from localinstance_class import *


__author__ = 'Shimmi Harel'
#test line - please ignore

now=datetime.datetime.now()
print now.strftime("%H:%M:%S:%f")
start_time = time.time()

key = "stable/com.sundaysky.streamer/"
my_instance = LocalInstance()
instanceId = my_instance.id
vpc = my_instance.vpc_name
region = my_instance.region
env = my_instance.env
instanceType = "streamer"
filename= "version_managment.txt"
propertiesFile = "streamer.properties"
log4j = "log4j.xml"
workdir = "/sundaysky/prod/"
jarname = "sundaysky-streamer-service.jar"
log_path="/sundaysky/prod/init/logs/"
kinesisAgnt="/etc/aws-kinesis/agent.json"
bucket_name ='repo-'+region+'-sundaysky-com'
now=datetime.datetime.now()
print now.strftime("%H:%M:%S:%f")

# # Setting Logger
logging.basicConfig(filename='/sundaysky/prod/init/logs/streamer_install.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')
logging.info('Starting Streamer Installation and Configuration- {}' .format(now))

# Getting the version number to install    
def get_version(filename,key,vpc,env,bucket):
	print "get_version function called"
	print "filename: ",filename
	print "key: ",key
	print "vpc: ",vpc
	print "bucket: ",bucket
	logging.info("get_version function called")
	if key == "stable/com.sundaysky.streamer/":
		s3loc = bucket+"/"+key+filename
	else:
		s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/"+filename
	print "s3loc: ",s3loc
	mng ="aws s3 cp s3://"+s3loc+" ."
	print "aws cmd: ",mng
	try:
		os.system(mng)
	except Exception as e:
		print e
		
	for line in open(filename):
		version = line.strip()
		print "version = " ,version
		
		if not version.startswith("#"):
			versionnum = version.split('#')
			version_number = versionnum[0].strip()
			break
	# delete temp file
	os.remove(filename)
	print "Version No: ", version_number
	return version_number

#get properties file
def get_properties(filename,key,vpc,env,bucket):
	logging.info("Downloading configuration file {}".format(filename))
	print "Downloading configuration file {}".format(filename)
	s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/"+filename
	print "s3 location = {}".format(s3loc)
	aws = "aws s3 cp s3://"+s3loc+" /sundaysky/prod/conf/streamer/"
	try:    
		os.system(aws)
	except Exception as e:
		logging.error("Failed downloading configuration file {} to work directory".format(filename))
		logging.error(e)
		print "failed downloading configuration file {}".format(filename)
		print e

			   
#get log4j file
def get_log4j(filename,key,vpc,env,bucket):
	aws =""
	try:
		logging.info("Downloading log4j configuration file {}".format(filename))
		print "Downloading log4j configuration file {}".format(filename)
		s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/log4j.xml"
		logging.info("{} location is {}".format(filename,s3loc))
		aws = "aws s3 cp s3://"+s3loc+" /sundaysky/prod/conf/streamer/"
		logging.info("executing command : {}".format(aws))
		try:
			os.system(aws)
		except Exception as e:
			logging.error("Failed downloading configuration file {} to work directory".format(filename))
			logging.error(e)
			print "failed downloading configuration file {}".format(filename)
			print e
	except Exception as e2:
		logging.error("get_log4j() failed: ")
		logging.error(e2)
		
def updateKinesisAgent(fileName,region,vpc,env):
	print "Updateing Kinesis agent.json"
	logging.info("Updateing Kinesis configuration {}".format(fileName))
	with open(fileName, 'r') as f:
		try:
			json_data = json.load(f)
			json_data['firehose.endpoint'] = "https://firehose."+region+".amazonaws.com"
			json_data['kinesis.endpoint'] = "https://kinesis."+region+".amazonaws.com"
			json_data['flows'][0]['deliveryStream'] = "Streamer-"+vpc.upper()
			json_data['flows'][0]['filePattern'] = "/sundaysky/prod/logs/streamer/server_main.log*"
			del json_data['flows'][0]["kinesisStream"]
			json_data['flows'][1]['kinesisStream'] = "Streamer-"+vpc.upper()+"-"+env+"-Stats"
			json_data['flows'][1]['filePattern'] = "/sundaysky/prod/logs/streamer/stats.log*"
			del json_data['flows'][1]["deliveryStream"]
			json_data['flows'].append({"kinesisStream": "Streamer-"+vpc.upper()+"-"+env+"-Stats", "filePattern": "/sundaysky/prod/logs/renderer/jobs.log*"})

		except Exception as e:
			print "Error with Kinesis json file: ", e
			logging.error("Error with Kinesis json file:")
			logging.error(e)
		
	with open(fileName, 'w') as f:
		try:
			f.write(json.dumps(json_data))
		except Exception as e:
			print "Error while updating Kinesis json file: ", e
			logging.error("Error while updating Kinesis json file:")
			logging.error(e)

#remove versions file is exists
def silentremove(filename):
	print "silentremove function called"
	logging.info("silentremove function called")
	try:
		os.remove(filename)
	except OSError as e: 
		if e.errno != errno.ENOENT:
			logging.error('removing file {} failed'.format(filename))
			logging.error(e.errno)
			print "silentremove error: ",e
		else:
			logging.info('File {} deleted successfully' .format(filename))
			print "File ",filename," deleted successfully"    

# stop process if running
def stopProcess(name):
	logging.info("stopping process {}".format(name))
	try:
		pid = check_output(["pidof","-s",name])
		print pid
	except Exception as e:
		pid = "false"
	if pid == "false":
		print "Service "+name+" not running"
		logging.info("Service {} not running".format(name))
	else:
		print name +" PID = ",pid
		logging.info("Service is running with PID {}".format(pid))
		try:
			os.kill(int(pid),signal.SIGKILL)
		except Exception as e:
			logging.error("Proccess with PID {} failed to stop!".format(pid))
			logging.error(e)
			print "Proccess with PID="+pid+" Failed to stop!"
			print e
		else:
			logging.info ("PID ="+pid+" killed successfully")
			print" Process "+pid+" killed successfully"

key = 'streamer'
logging.info("Bucket name: {}".format(bucket_name))
print "Bucket name: ",bucket_name
now=datetime.datetime.now()
print now.strftime("%H:%M:%S:%f")
print "vpc = ",vpc
logging.info("VPC NAME = {}".format(vpc))
version = get_version(filename,key,vpc,env,bucket_name)
print "version is: ",version
logging.info("Version = {}" .format(version))
print "Downoading file"
try:
	if not '.' in version:
		# HARD CODED version
		version = "2.1."+version

	if bucket_name == 'repo.sundaysky.com':
		url = "s3://repo.sundaysky.com/stable/com.sundaysky.streamer/sundaysky-streamer-service/sundaysky-streamer-service-"+version+".jar"
	else:
		url = "s3://"+bucket_name+"/"+key+"/versions/sundaysky-streamer-service-"+version+".jar"
	print "URL = ",url
	logging.info("URL = {}".format(url))
	
	call = "aws s3 cp "+url+" "+workdir+jarname
	print "AWS cmd = ",call
	logging.info("AWS cmd = {}".format(call))
	proc = subprocess.Popen(call, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	if proc.poll() != 0:
		e = proc.stdout.read()
		print "Error: " + e
		logging.error(e)
	
except Exception as e:
	print "Error: "
	print e
	logging.error(e)
	sys.exit(1)

get_properties(propertiesFile,key,vpc,env,bucket_name)
try:
	get_properties("streamer_settings.xml",key,vpc,env,bucket_name)
except Exception as e:
	print "Failed fetching streamer_settings.xml"
	logging.error("Failed fetching file streamer_settings.xml")
	logging.error(e)
try:
	get_log4j(log4j,key,vpc,env,bucket_name)
except Exception as e:
	print "Failed fetching log4j.xml"
	logging.error("Failed fetching log4j.xml")
	logging.error(e)
   
if os.path.isfile('/sundaysky/prod/conf/streamer/log4j.xml'):
	java_run_cmd = 'java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/streamer/ -Dlog4j.configuration=file:///sundaysky/prod/conf/streamer/log4j.xml -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-streamer-service.jar'
		
else:
	java_run_cmd = 'java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/streamer/ -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-streamer-service.jar'
				
# make the Upstart service file
streamer_upstart_file = "/etc/init/streamer.conf"
os.system('echo #upstart >> {}'.format(streamer_upstart_file))
try:
	f = open(streamer_upstart_file,'w')
	f.write("#upstart-job\nexec "+java_run_cmd+"\nrespawn\n")
	f.close()
except Exception as e:
	print "Failed to create file streamer_upstart_file"
	print e
os.system('initctl reload-configuration')
try:
	logging.info("calling upstart to open in a new process")
	os.system('start streamer')
	logging.info("streamer started")
except Exception as e:
	print "Error!"
	print e
	logging.error(e)

now=datetime.datetime.now()
print now.strftime("%H:%M:%S:%f")   
logging.info("Streamer Executed in -- %s seconds --" % (time.time() - start_time))

#Kinesis Installation 
try:
	os.system("yum -y install aws-kinesis-agent")
except Exception as e:
	logging.error("Kinesis agent installation failed")
	logging.error(e)
	print "Kinesis agent installation failed:"
	print e
#Kinesis Configuration
updateKinesisAgent(kinesisAgnt,region,vpc,env)

#Kinesis service Start
try:
	os.system("service aws-kinesis-agent start")
except Exception as e:
	logging.error("Kinesis Agent Failed to start:")
	logging.error(e)
	print "Kinesis Agent Failed to start:"
	print e


# SplunkForwrder
logging.info("Installing SplunkForwarder")
try:
	# Install forwarder
	os.system("rpm -i /sundaysky/prod/init/downloads/splunkforwarder.rpm")
except Exception as e:
	logging.error("SplunkForwarder installation failed")
	logging.error(e)
	print "SplunkForwarder installation failed:"
	print e
else:
		logging.info("SplunkForwarder installation Succeeded")
try:
	# Move outputs.conf file
	os.system("mv /sundaysky/prod/init/downloads/outputs.conf /opt/splunkforwarder/etc/system/local/outputs.conf")
except Exception as e:
		logging.error("Splunk configuration error 1: ")
		logging.error(e)
try:
	# Move server.conf file
	os.system("mv /sundaysky/prod/init/downloads/server.conf /opt/splunkforwarder/etc/system/local/server.conf")
except Exception as e:
		logging.error("Splunk configuration error 2: ")
		logging.error(e)
try:
	# Extract forwarder certs from .tar
	os.system("tar xvf /sundaysky/prod/init/downloads/splunk_certs.tar -C /sundaysky/prod/init/downloads/")
except Exception as e:
		logging.error("Splunk configuration error 3: ")
		logging.error(e)
try:
	# Extract raas app
	os.system("tar xvf /sundaysky/prod/init/downloads/ss_dvg_raasinputs.tar -C /sundaysky/prod/init/downloads/")
except Exception as e:
		logging.error("Splunk configuration error 4: ")
		logging.error(e)
try:
	# Move forwarder certs
	os.system("mv /sundaysky/prod/init/downloads/splunk_certs /opt/splunkforwarder/etc/certs")
except Exception as e:
		logging.error("Splunk configuration error 5: ")
		logging.error(e)
try:
	# Move raas app
	os.system("mv /sundaysky/prod/init/downloads/ss_dvg_raasinputs /opt/splunkforwarder/etc/apps/")
except Exception as e:
		logging.error("Splunk configuration error 6: ")
		logging.error(e)

#Splunk - configure & run
my_instance.splunkInit()


now=datetime.datetime.now()
print now.strftime("%H:%M:%S:%f")   
logging.info("Script executed in -- %s seconds --" % (time.time() - start_time))

sys.exit()
