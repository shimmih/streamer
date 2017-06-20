from asg_class import *
from localinstance_class import *
import urllib2
import json
import time
import os

def getInstanceIP(instance):
	'''
	input instance id
	return: public ip
	'''
	ec2_client = boto3.client('ec2')
	return ec2_client.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]['PublicIpAddress']

def getKwArgs(arguments):
	'''
	input: sys.argv
	retun: dictionary with all keword arguments (x=y)
	'''
	args = {}
	for i in arguments:
		try:
			k,v = i.split('=')
			args[k] = v
		except Exception as e:
			pass
	return args

def get_version(filename,key,vpc,env,bucket):
	print "get_version function called"
	print "filename: ",filename
	print "key: ",key
	print "vpc: ",vpc
	print "bucket: ",bucket
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

asg_name = "VID2S3-RaaS-init-test-Cluster-1RMIUAXT50RO2"
properties_file = "init_test.props"
my_asg = AutoScalingGroup(asg_name)

filename = "version_managment.txt"
region = "us-east-1"
bucket = "repo-"+region+"-sundaysky-com"
key = "renderer"
vpc = my_asg.tags['VPC']
vpc = vpc.lower()
env = my_asg.tags['env']
# print variables
print "INFO: AutoScaling Group: " + str(asg_name)
print "INFO: increasing desired capacity by 1"
print my_asg.addInstances(1)

poll_cycles = 0
new_instances = []

print "INFO: Start Polling ASG"
# Wait for new instance and get it's id
while len(new_instances)==0:
	print "waiting 30 seconds..."
	time.sleep(30)
	my_asg = AutoScalingGroup(asg_name)
	new_instances = my_asg.findInstances(state='LISTEN')
	poll_cycles+=1
	print "poll " + str(poll_cycles)
	if poll_cycles > 6:
		print "ERROR: no instances with new version found, stop polling"
		my_asg.setCapacity(0)
		sys.exit(1)
else:
	print "INFO: polling successfull:"
	print new_instances

# Get the first new instance and it's IP
new_instance = new_instances.pop(0)
print "new instance: " + str(new_instance)
new_instance_ip = getInstanceIP(new_instance)
print "new instance IP: " + str(new_instance_ip)
infoUrl = 'http://'+new_instance_ip+':8080/info'
print 'infoUrl = '+ infoUrl
s3version = get_version(filename,key,vpc,env,bucket)
print "RaaS version should be - {}".format(s3version)
info_cycle = 5
while info_cycle > 0: 
        print "polling info ",info_cycle
	time.sleep(30)
	try:
		response = urllib2.urlopen(infoUrl)
	except Exception as e:
		print "sleep 30 seconds"
                info_cycle = info_cycle - 1
	
                if info_cycle == 0 :
                        print "ERROR: can't retrieve info from RaaS, stop polling"
                        my_asg.setCapacity(0)
                        sys.exit(4)
        else:
                info_cycle = 0
                print "INFO: RaaS info retrived successfully:"	
                data = response.read()
                info = json.loads(data)
                instanceRaasVer = info['versionInfo']['version']
                instanceState = info['state']


# Check Kinesis Agent and SplunkForwarder status
#
# Need to figure out the correct method to use here - maybe Run Command...
#

# Write properties file
os.system("echo asg={} >> {}".format(asg_name,properties_file))
os.system("echo ip={} >> {}".format(new_instance_ip,properties_file))
os.system("echo actual version={} >> {}".format(instanceRaasVer,properties_file))
os.system("echo intended version={} >> {}".format(s3version,properties_file))

if s3version == instanceRaasVer:
	if instanceState != "LISTEN":
		os.system("echo Error! Instance stuck in {} state >> {}".format(instanceState,properties_file))
		sys.exit(2)
	else:
		os.system("echo Instance RaaS version match intended version and state is {}  >> {}".format(instanceState,properties_file))
		print "echo Instance RaaS version match intended version and state is {}  >> {}".format(instanceState,properties_file)
else:
	os.system("echo Error! Wrong RaaS version {}, should be {} >> {}".format(instanceRaasVer,s3version,properties_file))
	sys.exit(3)

print "Done successfully"
print "Terminating instance"
my_asg.setCapacity(0)
