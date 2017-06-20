#!/usr/bin/python
import pip
try:
    pip.main(['install','boto3'])
except Exception as e:
    print "boto3 is already installed"
import os
from distutils.dir_util import copy_tree
import subprocess
import sys
import shutil
import fileinput
import boto
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
import subprocess
import re
import json
import signal
import psutil
from localinstance_class import *
__author__ = 'Shimmi Harel'


start_time = time.time()
my_instance = LocalInstance()
instanceId= my_instance.id # set the instance id
try:
    env = my_instance.tags['env']
except Exception as e:
    env = "prod"
bucket_name =" "
key = "stable/com.sundaysky.renderer/"
version = ""
instanceType = "renderer"
client =""
filename= "version_managment.txt"
propertiesFile = "renderer.properties"
log4j = "log4j.xml"
workDir = "/sundaysky/prod/"
jarname = "sundaysky-renderer-service.jar"
bucket =""
log_path="/sundaysky/prod/init/logs/"
kinesisAgnt="/etc/aws-kinesis/agent.json"
startKinesisAgent = "service aws-kinesis-agent start"
startSplunkForwarder = "/opt/splunkforwarder/bin/splunk start"
process = "java"
print "starting at: "+str(start_time)

# # Setting Logger
logging.basicConfig(filename='/sundaysky/prod/init/logs/RaaS_init.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')
logging.info('Starting RaaS Deployment')
logging.info('InstanceId = {}'.format(instanceId))
respons1 = urllib2.urlopen('http://169.254.169.254/latest/user-data')
userdata=respons1.read()
with open ('userdata.txt', 'w') as fid:
    fid.write(userdata)
with open ('userdata.txt', 'r') as udata:
    for line in udata:
        print line
        if "vpc.client" in line:
            client = line.split("=",1)[1]
            client = client.strip()
            print "vpc.client found in user data"
            print "vpc.client = {}".format(client)
            logging.info("vpc.client found in user data")
            logging.info("Client = {}".format(client))
        elif "vpc.instance.type" in line:
            instanceType = line.split("=",1)[1]
            instanceType = instanceType.strip()
            print "Instance Type =",instanceType
            logging.info("Instance type = {}".format(instanceType))
        elif "vpc.env" in line:
            env = line.split("=",1)[1]
            env = env.strip()
            print "Environment =",env
            logging.info("Environment = {}".format(env))
print "user data = "+userdata
logging.info ('User Data:')
logging.info(userdata)

def updateKinesisAgent(fileName,region,vpc):
    print "Updateing Kinesis agent.json"
    logging.info("Updateing Kinesis configuration {}".format(fileName))
    with open(fileName, 'r') as f:
        try:
            json_data = json.load(f)
            json_data['firehose.endpoint'] = "firehose."+region+".amazonaws.com"
            json_data['flows'][0]['deliveryStream'] = vpc.upper()+"-RAAS"
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
    
# Modify Splunk inputs file
def SplunkInit(instanceType,region,instance,env):
    print "SplunkInit function called"
    meta_fields = "vpc::{} env::{}".format(my_instance.vpc_name,env.lower())
    respons2 = urllib2.urlopen('http://169.254.169.254/latest/meta-data/iam/info')
    iamInfo = respons2.read()
    with open ('iamInfo.json', 'w') as fid:
        fid.write(iamInfo)
    with open('iamInfo.json', 'r') as f:
        json_data = json.load(f)
        instanceProf = json_data["InstanceProfileArn"]
        accnt =  instanceProf.split(":")
        accountId = accnt[4]
        print instanceProf
        print accountId
    if accountId=="651241207884":
        envName = "dev"
    elif accountId=="383543149372":
        envName = "prod"
    elif accountId=="470093043463":
        envName = "ps"

    logging.info("====== SplunkInit started ======")
    serverName = "aws::"+envName+"::"+region+"::"+instanceType+"::"+instance.id
    logging.info("Server name = {}".format(serverName))
    inputsFile = "/opt/splunkforwarder/etc/system/local/inputs.conf"
    # Removing old inputs file if exist
    try:
        logging.info("Calling the silentremove function")
        silentremove(inputsFile)
    except Exception as e:
        print " removing old inputs file failed!"
        print e
    # open a new inputs.conf file
    try:
        logging.info("Creating new inputs.conf file")
        inputs = open(inputsFile, "wb" )
    except Exception as e:
        print "creating a new inputs file failed!"
        print e
    # writing configuration to inputs file
    try:
        logging.info("Writing server name into inputs.conf file")
        inputs.write ("[default]\nhost = "+serverName+"\n_meta = "+meta_fields)
    except Exception as e:
        print "Writing server name to inputs file failed!"
        print e
    # closing open file
    inputs.close()

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

def splitWords(s):
    words = []
    inword = 0
    print s
    for c in s:
        if c in " \r\n\t": # whitespace
            inword = 0
        elif not inword:
            words = words + [c]
            inword = 1
        else:
            words[-1] = words[-1] + c
    return words

def prepareServer():
    ls = 'ls -ltr /sundaysky/prod/native/ >natives.txt'
    last =""
    os.system(ls)
    with open('natives.txt','r')as f:
        for i, line in enumerate(f):
            if i==1:
                latest = splitWords(line)
                last = latest[8]
    print 'Latest native folder is: '+last
    print 'About to copy .so files to renderer_natives folder'
    logging.info('Latest native folder is: {}'.format(last))
    logging.info('About to copy .so files to renderer_natives folder')
    cp = ' cp -rf /sundaysky/prod/native/'+last+'/renderer_natives/bin/natives/*  /lib64/'
    try:
        os.system(cp)
    except Exception as e:
        print "Error copying .so files"
        print e
        logging.error('Failed to copy .so files')
        logging.error(e)

# Getting the version number to install    
def get_version(filename,key,vpc,env,bucket):
    print "get_version function called"
    print "filename: ",filename
    print "key: ",key
    print "vpc: ",vpc
    print "bucket: ",bucket
    logging.info("get_version function called")
    if key == "stable/com.sundaysky.renderer/":
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
def get_properties(filename,key,vpc,env,client,bucket):
    logging.info("Downloading configuration file {}".format(filename))
    print "Downloading configuration file {}".format(filename)
    print "get_properties client argument passed = {}".format(client) 
    if client:
        s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/"+client+"/"+filename
        print "s3 location = {}".format(s3loc)
    else:
        s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/"+filename
        print "s3 location = {}".format(s3loc)
    aws = "aws s3 cp s3://"+s3loc+" /sundaysky/prod/conf/raas/"
    try:    
        os.system(aws)
    except Exception as e:
        logging.error("Failed downloading configuration file {} to work directory".format(filename))
        logging.error(e)
        print "failed downloading configuration file {}".format(filename)
        print e
                    
#get log4j file
def get_log4j(filename,key,vpc,env,client,bucket):
    aws =""
    try:
        logging.info("Downloading log4j configuration file {}".format(filename))
        print "Downloading log4j configuration file {}".format(filename)
        if client:
            s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/"+client+"/"+filename
            print "s3 location = {}".format(s3loc)
            logging.info("{} location is {}".format(filename,s3loc))
        else:
            s3loc=bucket+"/"+key+"/"+vpc+"/"+env+"/log4j.xml"
            logging.info("{} location is {}".format(filename,s3loc))
        aws = "aws s3 cp s3://"+s3loc+" /sundaysky/prod/conf/raas/"
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
        

region = my_instance.region
# determain which bucket acording to region
if region:
    bucket_name ='repo-{}-sundaysky-com'.format(region)
    key = 'renderer'
else:
    bucket_name = bucket_name
logging.info("Bucket name: {}".format(bucket_name))
print "Bucket name: ",bucket_name

vpc = my_instance.vpc_name
print "vpc = ",vpc
logging.info("VPC NAME = {}".format(vpc))

print "Connecting to S3"
try:
    conn = boto.s3.connect_to_region(region, calling_format='boto.s3.connection.OrdinaryCallingFormat')
    print "Conn = ",conn
    bucket = conn.get_bucket(bucket_name)
    print "bucket = ",bucket
except Exception as e:
    print "S3 connection Error: ", e
    logging.error(e)
    logging.error('Could not establish S3 connection')
else:
    logging.info('S3 connection - OK')
    print "S3 Connection - OK"
updateKinesisAgent(kinesisAgnt,region,vpc)
stopProcess("splunkd")
SplunkInit(instanceType,region,my_instance,env)
os.system(startSplunkForwarder)
get_properties(propertiesFile,key,vpc,env,client,bucket_name)
try:
    get_properties("renderer_settings.xml",key,vpc,env,client,bucket_name)
except Exception as e:
    print "Failed fetching renderer_settings.xml"
    logging.error("Failed fetching file renderer_settings.xml")
    logging.error(e)
try:
    get_log4j(log4j,key,vpc,env,client,bucket_name)
except Exception as e:
    print "Failed fetching log4j.xml"
    logging.error("Failed fetching log4j.xml")
    logging.error(e)
   
 
if os.path.isfile('/sundaysky/prod/conf/raas/log4j.xml'):
    try:
        f = open('/sundaysky/prod/init/scripts/raas_start.py','w')
        f.write('#!/usr/bin/python\nimport os\n')
        f.write('cmd="java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/raas/ -Dlog4j.configuration=file:///sundaysky/prod/conf/raas/log4j.xml -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-renderer-service.jar &"\n')
        java_run_cmd = 'java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/raas/ -Dlog4j.configuration=file:///sundaysky/prod/conf/raas/log4j.xml -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-renderer-service.jar'
        f.write('os.system(cmd)\n')
        f.close()
    except Exception as e:
        print "Failed to create file raas_start.py"
        print e
        logging.error("Failed to create file raas_start.py")
        logging.error(e)
    chmd = "chmod +x /sundaysky/prod/init/scripts/raas_start.py"
    try:
        os.system(chmd)
    except Exception as e:
        print "Failed to change permissions of file raas_start.py"
        print e
        logging.error("Failed to change permissions of file raas_start.py")
        logging.error(e)
else:
    try:
        f = open('/sundaysky/prod/init/scripts/raas_start.py','w')
        f.write('#!/usr/bin/python\nimport os\n')
        f.write ('cmd="java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/raas/ -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-renderer-service.jar &"\n')
        java_run_cmd = 'java -jar -Dserver.port=8080 -Ddvg.home=/sundaysky/prod/ -Ddvg.work=/sundaysky/prod/raas/ -server -XX:MaxNewSize=4096m -XX:+UseConcMarkSweepGC -XX:+UseStringDeduplication -Xmx6144m -Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider /sundaysky/prod/sundaysky-renderer-service.jar'
        f.write ('os.system(cmd)')
        f.close()
    except Exception as e:
        print "Failed to create file raas_start.py"
        print e
        logging.error("Failed to create file raas_start.py")
        logging.error(e)
        exit(1)
    chmd = "chmod +x /sundaysky/prod/init/scripts/raas_start.py"
    try:
        os.system(chmd)
    except Exception as e:
        print "Failed to change permissions of file raas_start.py"
        print e
        logging.error("Failed to change permissions of file raas_start.py")
        logging.error(e)
        exit(1)

        
version = get_version(filename,key,vpc,env,bucket_name)
print "version is: ",version
logging.info("Version = {}" .format(version))
print "Downoading file"
try:
    if bucket_name == 'repo.sundaysky.com':
        url = "s3://repo.sundaysky.com/stable/com.sundaysky.renderer/sundaysky-renderer-service/sundaysky-renderer-service-2.1."+version+".jar"
    else:
        url = "s3://"+bucket_name+"/"+key+"/versions/sundaysky-renderer-service-2.1."+version+".jar"
    print "URL = ",url
    logging.info("URL = {}".format(url))
    #wget.download(url, "sundaysky-renderer-service"+version+".jar"u
    call = "aws s3 cp "+url+" ."
    print "AWS cmd = ",call
    logging.info("AWS cmd = {}".format(call))
    os.system(call)
    
except Exception as e:
    print "Error: "
    print e
    logging.error(e)
    sys.exit(1)

stopProcess("java")
print "about to check if file exist" 
if os.path.isfile("sundaysky-renderer-service-2.1."+version+".jar"):
    print "file sundaysky-renderer-service.2.1."+version+".jar downloaded successfully"
    logging.info("file sundaysky-renderer-service.2.1.{}.jar downloaded successfully".format(version))
    print "moving file to working directory"
    logging.info("moving file to working directory")
    try:
        shutil.move("sundaysky-renderer-service-2.1."+version+".jar", "/sundaysky/prod/sundaysky-renderer-service.jar")
    except Exception as e:
        print "Error moving File: "
        print e
else:
    print "No such file sundaysky-renderer-service-2.1."+version+".jar"
    logging.error("No such file sundaysky-renderer-service-{}.jar".format(version))


#os.chdir(workDir)
#print "Current Folder: ",os.getcwd()
try:
    print "opening the jar in a different proccess for the first time" 
    pid = subprocess.Popen([sys.executable, "/sundaysky/prod/init/scripts/raas_start.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    print pid.pid
 
except Exception as e:
    print "Error!"
    print e
    logging.error(e)
time.sleep(30)
prepareServer()
stopProcess("java")
time.sleep(30)
stopProcess("java")
os.system(startKinesisAgent)

# make the Upstart service file
raas_upstart_file = "/etc/init/raas.conf"
os.system('echo #upstart >> {}'.format(raas_upstart_file))
try:
    f = open(raas_upstart_file,'w')
    f.write("#upstart-job\nexec "+java_run_cmd+"\nrespawn\n")
    f.close()
except Exception as e:
    print "Failed to create file raas_start.py"
    print e
os.system('initctl reload-configuration')
# Start the proccess for the second time
try:
    print "opening the jar in a different proccess for the second time"
    logging.info("calling upstart to open in a new process")
    os.system('start raas')
    logging.info("raas started")
except Exception as e:
    print "Error!"
    print e
    logging.error(e)
logging.info("Script Executed in -- %s seconds --" % (time.time() - start_time))

sys.exit()
